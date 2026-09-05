import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import cytoscape from 'cytoscape'
import type { Core, EdgeSingular, NodeSingular } from 'cytoscape'
import {
  AlertCircle,
  Check,
  Eraser,
  Info,
  Maximize2,
  Minimize2,
  RotateCcw,
  Scan,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { INFERRED_BELOW, edgeLabel, entityStyle, entityStyles } from '../../lib/entities'
import {
  buildElements,
  clearPositions,
  layoutOptions,
  loadFilters,
  loadPositions,
  pathEdgeIds,
  savePositions,
  saveFilters,
  stylesheet,
  type GraphFilters,
} from '../../lib/graph'
import { chipClass, iconButtonClass, quietButtonClass } from '../../lib/ui'
import type { CaseGraph, Community, GraphEdge, NodeType } from '../../types'
import { EntityIcon } from './EntityIcon'

/** How long each step of a path takes to light up. */
const STEP_MS = 260

interface ConnectionsProps {
  caseId: string
  graph: CaseGraph | undefined
  communities: Community[]
  isLoading: boolean
  isError: boolean
  onRetry: () => void
  /** Ordered node ids from the last answer — §5.3 `highlight_path`. */
  highlightPath: string[]
  /** What produced the path, so the officer knows what they are looking at. */
  highlightLabel: string | null
  onClearPath: () => void
  onSelectNode: (nodeId: string) => void
  selectedNodeId: string | null
  reducedMotion: boolean
  focused: boolean
  onFocusToggle: () => void
}

export function Connections({
  caseId,
  graph,
  communities,
  isLoading,
  isError,
  onRetry,
  highlightPath,
  highlightLabel,
  onClearPath,
  onSelectNode,
  selectedNodeId,
  reducedMotion,
  focused,
  onFocusToggle,
}: ConnectionsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const timersRef = useRef<number[]>([])
  const [filters, setFilters] = useState<GraphFilters>(() => loadFilters(caseId))
  const [search, setSearch] = useState('')
  const [legendOpen, setLegendOpen] = useState(false)
  const [layoutTick, setLayoutTick] = useState(0)
  const [edgePopover, setEdgePopover] = useState<{ id: string; x: number; y: number } | null>(null)

  const edgesById = useMemo(() => {
    const map = new Map<string, GraphEdge>()
    for (const edge of graph?.edges ?? []) map.set(edge.id, edge)
    return map
  }, [graph])

  const nodeLabels = useMemo(() => {
    const map = new Map<string, string>()
    for (const node of graph?.nodes ?? []) map.set(node.id, node.label)
    return map
  }, [graph])

  /**
   * A path may run through a document node, and `/graph` drops those by
   * default because they are hubs that connect everything to everything. When
   * that happens the canvas turns them back on rather than drawing a path with
   * a hole in it — as an override held for as long as the path is shown, not
   * as a write to the officer's saved filters. Clearing the path restores
   * whatever view they had chosen.
   */
  const documentsForced =
    highlightPath.some((id) => id.startsWith('doc:')) && !filters.includeDocuments

  const effectiveFilters = useMemo(
    () => (documentsForced ? { ...filters, includeDocuments: true } : filters),
    [documentsForced, filters],
  )

  const elements = useMemo(
    () => (graph ? buildElements(graph, communities, effectiveFilters) : []),
    [graph, communities, effectiveFilters],
  )

  const pathPlan = useMemo(
    () => pathEdgeIds(highlightPath, graph?.edges ?? []),
    [highlightPath, graph],
  )

  const updateFilters = useCallback(
    (next: GraphFilters) => {
      setFilters(next)
      saveFilters(caseId, next)
    },
    [caseId],
  )

  // ------------------------------------------------------------ cytoscape
  useEffect(() => {
    const container = containerRef.current
    if (!container) return undefined

    const cy = cytoscape({
      container,
      style: stylesheet,
      minZoom: 0.15,
      maxZoom: 3.5,
      boxSelectionEnabled: false,
    })
    cyRef.current = cy

    cy.on('tap', 'node', (event) => {
      setEdgePopover(null)
      onSelectNode((event.target as NodeSingular).id())
    })
    cy.on('tap', 'edge', (event) => {
      const edge = event.target as EdgeSingular
      const point = edge.renderedMidpoint()
      setEdgePopover({ id: edge.id(), x: point.x, y: point.y })
    })
    cy.on('tap', (event) => {
      if (event.target === cy) setEdgePopover(null)
    })
    cy.on('dragfree', 'node', () => {
      const positions: Record<string, { x: number; y: number }> = {}
      cy.nodes().forEach((node) => {
        positions[node.id()] = { ...node.position() }
      })
      savePositions(caseId, positions)
    })

    /**
     * Cytoscape sizes its canvases from the container once, when it is created.
     * This container changes size constantly — the divider drag, focus mode,
     * the tablet tabs — and on first mount it can still be zero-height, which
     * leaves a graph that reports 116 entities and draws none of them.
     */
    let last = { width: 0, height: 0 }
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width === 0 || height === 0) return
      cy.resize()
      if (last.width === 0) {
        if (cy.elements().length > 0) cy.fit(undefined, 42)
      } else {
        // Cytoscape keeps the pan offset through a resize, so a panel that
        // narrows — the entity drawer opening — appears to shove the graph off
        // to one side. Shifting the pan by half the delta keeps whatever was in
        // the middle of the panel in the middle of it, without overriding a
        // zoom or pan the officer chose.
        const pan = cy.pan()
        cy.pan({
          x: pan.x + (width - last.width) / 2,
          y: pan.y + (height - last.height) / 2,
        })
      }
      last = { width, height }
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      cy.destroy()
      cyRef.current = null
    }
  }, [caseId, onSelectNode])

  // Elements, positions and layout. Saved positions win, so a graph the
  // officer has arranged by hand comes back the way they left it.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || elements.length === 0) return

    cy.batch(() => {
      cy.elements().remove()
      cy.add(elements)
    })

    const saved = loadPositions(caseId)
    const nodes = cy.nodes()
    const known = nodes.filter((node) => Boolean(saved[node.id()]))

    if (known.length === nodes.length && nodes.length > 0) {
      nodes.forEach((node) => {
        node.position(saved[node.id()])
      })
      cy.layout({ name: 'preset', fit: true, padding: 42 }).run()
      setLayoutTick((tick) => tick + 1)
      return
    }

    const layout = cy.layout(layoutOptions(elements.length))
    layout.one('layoutstop', () => {
      const positions: Record<string, { x: number; y: number }> = {}
      cy.nodes().forEach((node) => {
        positions[node.id()] = { ...node.position() }
      })
      savePositions(caseId, positions)
      setLayoutTick((tick) => tick + 1)
    })
    layout.run()
  }, [elements, caseId, reducedMotion])

  // ----------------------------------------------------- the highlighted path
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return undefined

    for (const timer of timersRef.current) window.clearTimeout(timer)
    timersRef.current = []
    cy.elements().removeClass('on-path faded')

    if (highlightPath.length === 0) return undefined

    const present = highlightPath.filter((id) => cy.getElementById(id).length > 0)
    if (present.length === 0) return undefined

    const { edgeIds, ordered } = pathEdgeIds(present, graph?.edges ?? [])
    cy.elements().addClass('faded')

    const lightEdge = (edgeId: string | undefined) => {
      if (!edgeId) return
      const edge = cy.getElementById(edgeId)
      if (edge.length > 0) edge.removeClass('faded').addClass('on-path')
    }

    // An ordered path lights each hop as its far node arrives. An unordered
    // set has no hops, so its internal links come up once the entities are all
    // on screen.
    const reveal = (index: number) => {
      cy.getElementById(present[index]).removeClass('faded').addClass('on-path')
      if (ordered && index > 0) lightEdge(edgeIds[index - 1])
    }
    const finish = () => {
      if (!ordered) edgeIds.forEach(lightEdge)
      cy.animate(
        { fit: { eles: cy.elements('.on-path'), padding: 90 } },
        { duration: reducedMotion ? 0 : 320 },
      )
    }

    if (reducedMotion) {
      present.forEach((_, index) => reveal(index))
      finish()
      return undefined
    }

    present.forEach((_, index) => {
      const timer = window.setTimeout(() => {
        reveal(index)
        if (index === present.length - 1) finish()
      }, index * STEP_MS)
      timersRef.current.push(timer)
    })

    return () => {
      for (const timer of timersRef.current) window.clearTimeout(timer)
      timersRef.current = []
    }
  }, [highlightPath, layoutTick, graph, reducedMotion])

  // Selection from elsewhere in the workspace — a citation, a finding, the
  // drawer's own neighbour list — moves the canvas to that entity.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !selectedNodeId) return
    const node = cy.getElementById(selectedNodeId)
    if (node.length === 0) return
    cy.elements().unselect()
    node.select()
    if (highlightPath.length === 0) cy.animate({ center: { eles: node } }, { duration: 220 })
  }, [selectedNodeId, layoutTick, highlightPath.length])

  // Search marks every match and centres the first, so a name typed in the box
  // is found even when it is off screen in a 116-node graph.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().removeClass('search-hit')
    const term = search.trim().toLowerCase()
    if (!term) return
    const hits = cy.nodes().filter((node) => String(node.data('label')).toLowerCase().includes(term))
    hits.addClass('search-hit')
    if (hits.length > 0) cy.animate({ center: { eles: hits[0] } }, { duration: 200 })
  }, [search, layoutTick])

  const activeEdge = edgePopover ? edgesById.get(edgePopover.id) : undefined
  const hiddenCount = (graph?.nodes.length ?? 0) - (elements.filter((el) => el.group === 'nodes').length)

  return (
    <section className="relative flex h-full min-h-0 flex-col bg-[#FCFDFE]" aria-label="Connections">
      <header className="flex flex-wrap items-center gap-2 border-b border-line bg-panel px-4 py-3">
        <h2 className="mr-1 text-sm font-semibold text-ink">Connections</h2>

        <label className="relative min-w-[190px] flex-1">
          <span className="sr-only">Search entities in this case</span>
          <Search
            size={16}
            strokeWidth={1.8}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
          />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search entities"
            className="h-9 w-full rounded-lg border border-line-strong bg-white pl-9 pr-3 text-[13px] text-ink placeholder:text-subtle hover:border-[#AAB2BC]"
          />
        </label>

        <FilterMenu
          filters={filters}
          onChange={updateFilters}
          types={graph?.nodes.map((node) => node.type) ?? []}
        />

        <button
          type="button"
          className={quietButtonClass}
          onClick={() => cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 42 } }, { duration: 220 })}
        >
          <Scan size={15} />
          Fit
        </button>

        <button
          type="button"
          className={quietButtonClass}
          onClick={() => {
            clearPositions(caseId)
            const cy = cyRef.current
            if (!cy) return
            const layout = cy.layout(layoutOptions(elements.length))
            layout.one('layoutstop', () => setLayoutTick((tick) => tick + 1))
            layout.run()
          }}
        >
          <RotateCcw size={15} />
          Reset
        </button>

        <button
          type="button"
          className={quietButtonClass}
          onClick={() => setLegendOpen((open) => !open)}
          aria-pressed={legendOpen}
        >
          <Info size={15} />
          Legend
        </button>

        <button
          type="button"
          className={iconButtonClass}
          onClick={onFocusToggle}
          aria-label={focused ? 'Exit focus mode' : 'Focus the Connections panel'}
          title={focused ? 'Exit focus mode' : 'Focus'}
        >
          {focused ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
        </button>
      </header>

      {highlightPath.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 border-b border-[#EADFC4] bg-evidence-soft px-4 py-2.5">
          <span className="text-[13px] font-semibold text-[#7C5615]">
            {pathPlan.ordered ? 'Showing the path' : 'Showing the entities'}{' '}
            {highlightLabel ? `for: ${highlightLabel}` : 'from the last answer'}
          </span>
          <span className="text-[13px] text-[#8A6A2C]">
            {highlightPath.length} {highlightPath.length === 1 ? 'entity' : 'entities'}
            {documentsForced ? ' · document nodes switched on because one is included' : ''}
          </span>
          <button type="button" className={`${quietButtonClass} ml-auto`} onClick={onClearPath}>
            <Eraser size={15} />
            Clear Path
          </button>
        </div>
      )}

      <div className="relative min-h-0 flex-1">
        {/*
          Sized inline, not with `absolute inset-0`. Cytoscape stamps
          `__________cytoscape_container { position: relative }` onto this node
          from a stylesheet it injects at runtime, which lands after Tailwind's
          and wins — the element stops being absolutely positioned, `inset-0`
          no longer stretches it, and it collapses to zero height with its
          canvases. An inline height beats the injected rule outright.
        */}
        <div
          ref={containerRef}
          style={{
            width: '100%',
            height: '100%',
            backgroundColor: '#FCFDFE',
            backgroundImage: 'radial-gradient(#DDE3E9 1px, transparent 1px)',
            backgroundSize: '22px 22px',
          }}
        />

        {isLoading && (
          <div className="absolute inset-0 grid place-items-center bg-[#FCFDFE]/85">
            <div className="text-center">
              <div className="mx-auto size-8 animate-spin rounded-full border-2 border-line-strong border-t-civic" />
              <p className="mt-3 text-sm text-muted">Building the connection map...</p>
            </div>
          </div>
        )}

        {isError && (
          <div className="absolute inset-0 grid place-items-center p-6">
            <div role="alert" className="max-w-sm rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-5 text-center">
              <AlertCircle size={20} className="mx-auto text-danger" />
              <h3 className="mt-3 text-sm font-semibold text-ink">The connection map could not load</h3>
              <p className="mt-1.5 text-sm leading-6 text-muted">
                The case service did not return this case&apos;s graph.
              </p>
              <button type="button" onClick={onRetry} className={`${quietButtonClass} mt-4`}>
                Retry
              </button>
            </div>
          </div>
        )}

        {!isLoading && !isError && elements.length === 0 && (
          <div className="absolute inset-0 grid place-items-center p-6">
            <div className="max-w-sm text-center">
              <EntityIcon type="person" size={22} />
              <h3 className="mt-4 text-base font-semibold text-ink">Nothing to connect yet</h3>
              <p className="mt-1.5 text-sm leading-6 text-muted">
                {hiddenCount > 0
                  ? 'Every entity is hidden by the current filters. Change them to see the case.'
                  : 'Add a document in Documents and the entities inside it appear here.'}
              </p>
            </div>
          </div>
        )}

        {legendOpen && <Legend onClose={() => setLegendOpen(false)} />}

        {activeEdge && edgePopover && (
          <EdgePopover
            edge={activeEdge}
            x={edgePopover.x}
            y={edgePopover.y}
            labelOf={(id) => nodeLabels.get(id) ?? id}
            onClose={() => setEdgePopover(null)}
            onOpenNode={(id) => {
              setEdgePopover(null)
              onSelectNode(id)
            }}
          />
        )}
      </div>

      <footer className="flex items-center justify-between gap-4 border-t border-line bg-panel px-4 py-2 text-xs text-muted">
        <span>
          {elements.filter((element) => element.group === 'nodes').length} entities ·{' '}
          {elements.filter((element) => element.group === 'edges').length} links shown
        </span>
        {hiddenCount > 0 && <span>{hiddenCount} hidden by filters</span>}
      </footer>
    </section>
  )
}

interface FilterMenuProps {
  filters: GraphFilters
  onChange: (filters: GraphFilters) => void
  types: string[]
}

function FilterMenu({ filters, onChange, types }: FilterMenuProps) {
  const present = useMemo(
    () => [...new Set(types)].sort((a, b) => a.localeCompare(b)) as NodeType[],
    [types],
  )
  const activeCount =
    filters.hiddenTypes.length + (filters.includeDocuments ? 1 : 0) + (filters.hideInferred ? 1 : 0)

  function toggleType(type: string) {
    const hidden = filters.hiddenTypes.includes(type)
      ? filters.hiddenTypes.filter((item) => item !== type)
      : [...filters.hiddenTypes, type]
    onChange({ ...filters, hiddenTypes: hidden })
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button type="button" className={quietButtonClass}>
          <SlidersHorizontal size={15} />
          Filter
          {activeCount > 0 && (
            <span className="ml-0.5 rounded-full bg-civic-soft px-1.5 text-[11px] font-semibold text-civic">
              {activeCount}
            </span>
          )}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="z-50 max-h-[70vh] w-[248px] overflow-y-auto rounded-lg border border-line bg-panel p-2 shadow-[0_14px_35px_rgba(32,37,43,0.12)]"
        >
          <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-[0.05em] text-subtle">
            Entity types
          </DropdownMenu.Label>
          {present
            .filter((type) => type !== 'document')
            .map((type) => (
              <CheckRow
                key={type}
                checked={!filters.hiddenTypes.includes(type)}
                label={entityStyle(type).label}
                onSelect={() => toggleType(type)}
              />
            ))}
          <DropdownMenu.Separator className="my-1.5 h-px bg-line" />
          <DropdownMenu.Label className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-[0.05em] text-subtle">
            Links
          </DropdownMenu.Label>
          <CheckRow
            checked={filters.includeDocuments}
            label="Show document nodes"
            hint="Documents link everything named in them"
            onSelect={() => onChange({ ...filters, includeDocuments: !filters.includeDocuments })}
          />
          <CheckRow
            checked={filters.hideInferred}
            label="Hide inferred links"
            hint={`Confidence below ${INFERRED_BELOW}`}
            onSelect={() => onChange({ ...filters, hideInferred: !filters.hideInferred })}
          />
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

interface CheckRowProps {
  checked: boolean
  label: string
  hint?: string
  onSelect: () => void
}

function CheckRow({ checked, label, hint, onSelect }: CheckRowProps) {
  return (
    <DropdownMenu.CheckboxItem
      checked={checked}
      onSelect={(event) => {
        event.preventDefault()
        onSelect()
      }}
      className="flex cursor-pointer select-none items-start gap-2.5 rounded-md px-2 py-2 text-sm text-ink outline-none hover:bg-canvas focus:bg-canvas"
    >
      <span
        className={`mt-0.5 grid size-4 shrink-0 place-items-center rounded border ${
          checked ? 'border-civic bg-civic text-white' : 'border-line-strong bg-white'
        }`}
      >
        {checked && <Check size={12} strokeWidth={3} />}
      </span>
      <span>
        <span className="block leading-5">{label}</span>
        {hint && <span className="block text-[11px] leading-4 text-muted">{hint}</span>}
      </span>
    </DropdownMenu.CheckboxItem>
  )
}

function Legend({ onClose }: { onClose: () => void }) {
  return (
    <div className="absolute bottom-4 right-4 z-20 w-[236px] rounded-[10px] border border-line bg-panel p-4 shadow-[0_14px_35px_rgba(32,37,43,0.12)]">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">Legend</h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close legend"
          className="grid size-7 place-items-center rounded-md text-muted hover:bg-canvas hover:text-ink"
        >
          <X size={15} />
        </button>
      </div>
      <ul className="mt-3 space-y-2">
        {(Object.keys(entityStyles) as NodeType[]).map((type) => (
          <li key={type} className="flex items-center gap-2.5 text-[13px] text-muted">
            <EntityIcon type={type} size={13} />
            {entityStyles[type].label}
          </li>
        ))}
      </ul>
      <div className="mt-3 space-y-2 border-t border-line pt-3 text-[13px] text-muted">
        <div className="flex items-center gap-2.5">
          <svg width="26" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="26" y2="4" stroke="#D3D8DE" strokeWidth="1.5" />
          </svg>
          Recorded link
        </div>
        <div className="flex items-center gap-2.5">
          <svg width="26" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="26" y2="4" stroke="#D3D8DE" strokeWidth="1.5" strokeDasharray="5 4" />
          </svg>
          Inferred link
        </div>
        <div className="flex items-center gap-2.5">
          <svg width="26" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="26" y2="4" stroke="#C58B2A" strokeWidth="3" />
          </svg>
          Answer path
        </div>
      </div>
    </div>
  )
}

interface EdgePopoverProps {
  edge: GraphEdge
  x: number
  y: number
  labelOf: (id: string) => string
  onClose: () => void
  onOpenNode: (id: string) => void
}

/** A relationship gets a compact popover rather than the full drawer — it is
 *  usually one sentence and a confidence, and the drawer belongs to entities. */
function EdgePopover({ edge, x, y, labelOf, onClose, onOpenNode }: EdgePopoverProps) {
  const inferred = edge.confidence < INFERRED_BELOW
  const basis = typeof edge.attrs.basis === 'string' ? edge.attrs.basis : null

  return (
    <div
      className="absolute z-30 w-[262px] -translate-x-1/2 rounded-[10px] border border-line bg-panel p-3.5 shadow-[0_14px_35px_rgba(32,37,43,0.14)]"
      style={{ left: x, top: y + 14 }}
      role="dialog"
      aria-label="Relationship details"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] font-semibold leading-5 text-ink">
          <button type="button" className="underline decoration-line-strong underline-offset-2 hover:text-civic" onClick={() => onOpenNode(edge.src)}>
            {labelOf(edge.src)}
          </button>{' '}
          <span className="font-normal text-muted">{edgeLabel(edge.type)}</span>{' '}
          <button type="button" className="underline decoration-line-strong underline-offset-2 hover:text-civic" onClick={() => onOpenNode(edge.dst)}>
            {labelOf(edge.dst)}
          </button>
        </p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close relationship details"
          className="grid size-6 shrink-0 place-items-center rounded text-muted hover:bg-canvas hover:text-ink"
        >
          <X size={14} />
        </button>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <span
          className={`${chipClass} ${
            inferred ? 'border-[#E4D3AF] bg-evidence-soft text-[#8A5F16]' : 'border-[#B9D6C8] bg-success-soft text-success'
          }`}
        >
          {inferred ? 'Inferred' : 'Recorded'}
        </span>
        <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
          Confidence {Math.round(edge.confidence * 100)}%
        </span>
      </div>

      {basis && <p className="mt-2.5 text-xs leading-5 text-muted">Basis: {basis.replace(/_/g, ' ')}</p>}
      <p className="mt-2 text-xs leading-5 text-muted">
        Read from {edge.sources.length} {edge.sources.length === 1 ? 'passage' : 'passages'}. Open either
        entity to see the documents behind it.
      </p>
    </div>
  )
}
