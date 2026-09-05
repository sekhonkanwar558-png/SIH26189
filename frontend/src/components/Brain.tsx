import { useQuery } from '@tanstack/react-query'
import cytoscape from 'cytoscape'
import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { getMemory } from '../lib/api'
import type { CaseGraph } from '../types'

/**
 * The case's brain — the graph it has built, and what it has worked out.
 *
 * **This is not an illustration of an answer** (§2.5, D29). It is the thing the
 * answers are computed from: a graph on disk that grows every time a document
 * arrives, and which is queried with tools one call at a time. A chat assistant
 * holds a case in a context window and forgets the first document to fit the
 * fortieth; this holds nothing, and the fortieth document makes the first worth
 * more, because a link needs both ends.
 *
 * It opens by itself when an answer has a route through it, and the officer can
 * open it whenever he wants to look — that is the "option to graph" the pivot
 * kept. It is the only panel in the product and there must not be a second one
 * (D25).
 *
 * What is lit is what the answer rested on, in Evidence Amber and in nothing
 * else (D28). Consecutive hops light the real edge between them; a finding's
 * unordered set lights its members only, because a set is not a journey anyone
 * can take (D23). **Nothing is ever drawn between two nodes with no edge.**
 */

const INK = '#0d0d0d'
const GREY = '#c9c9cf'
const AMBER = '#b8791f'

export interface BrainProps {
  caseId: string
  graph: CaseGraph
  /** Ordered node ids the answer rests on, or an unordered cited set. Empty is
   *  the officer looking at the brain rather than an answer explaining itself. */
  path: string[]
  /** True when `path` is an ordered route, false when it is a cited set. */
  ordered: boolean
  onClose: () => void
}

export function Brain({ caseId, graph, path, ordered, onClose }: BrainProps) {
  const host = useRef<HTMLDivElement | null>(null)

  const memory = useQuery({
    queryKey: ['memory', caseId],
    queryFn: () => getMemory(caseId),
    enabled: path.length === 0,
    staleTime: 30_000,
  })

  useEffect(() => {
    if (!host.current) return

    const lit = new Set(path)
    const hops = new Set<string>()
    if (ordered) {
      for (let i = 0; i < path.length - 1; i += 1) {
        hops.add(`${path[i]}|${path[i + 1]}`)
        hops.add(`${path[i + 1]}|${path[i]}`)
      }
    }

    const nodes = graph.nodes.map((node) => ({
      data: { id: node.id, label: node.label, lit: lit.has(node.id) ? 1 : 0 },
    }))
    const known = new Set(graph.nodes.map((n) => n.id))
    const edges = graph.edges
      .filter((edge) => known.has(edge.src) && known.has(edge.dst))
      .map((edge) => ({
        data: {
          id: edge.id,
          source: edge.src,
          target: edge.dst,
          // An unordered set has no hops, so the links *inside* the set are what
          // is lit. Either way the edge must exist in the graph to be drawn.
          lit: ordered
            ? hops.has(`${edge.src}|${edge.dst}`)
              ? 1
              : 0
            : lit.has(edge.src) && lit.has(edge.dst)
              ? 1
              : 0,
        },
      }))

    const cy = cytoscape({
      container: host.current,
      elements: { nodes, edges },
      style: [
        {
          selector: 'node',
          style: { 'background-color': GREY, width: 9, height: 9, label: '' },
        },
        {
          selector: 'node[lit = 1]',
          style: {
            'background-color': AMBER,
            width: 20,
            height: 20,
            label: 'data(label)',
            'font-size': 11,
            'font-family': 'Inter Variable, Inter, system-ui, sans-serif',
            color: INK,
            'text-margin-y': -8,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'straight',
            width: 1,
            'line-color': '#ececef',
            opacity: 0.7,
          },
        },
        { selector: 'edge[lit = 1]', style: { 'line-color': AMBER, width: 2.5, opacity: 1 } },
      ],
      layout: {
        name: 'cose',
        animate: false,
        nodeRepulsion: 9000,
        idealEdgeLength: 60,
        padding: 40,
      } as cytoscape.LayoutOptions,
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    })

    // Cytoscape sets `position: relative` on its container at runtime, which
    // beats a Tailwind `absolute` and collapses the canvas to zero height. The
    // container is sized inline, and a ResizeObserver keeps it right when the
    // panel opens, closes or the window changes.
    const fit = () => {
      cy.resize()
      if (lit.size) cy.fit(cy.nodes('[lit = 1]'), 80)
      else cy.fit(undefined, 40)
    }
    fit()
    const observer = new ResizeObserver(fit)
    observer.observe(host.current)

    return () => {
      observer.disconnect()
      cy.destroy()
    }
  }, [graph, path, ordered])

  const { nodes, edges, documents } = graph.counts
  // Documents are nodes too (§5.1); they are not entities, and the count
  // beside an upload's "read 11 entities" has to agree with it.
  const entities = nodes - documents
  const conclusions = (memory.data ?? []).filter((m) => m.kind === 'conclusion').slice(0, 3)
  const questions = (memory.data ?? [])
    .filter((m) => m.kind === 'open_question' && m.status === 'open')
    .slice(0, 2)

  return (
    <aside className="flex h-full min-h-0 w-full flex-col border-l border-line bg-canvas">
      <header className="flex shrink-0 items-baseline gap-3 px-4 py-3">
        <p className="text-[13px] text-ink">
          {path.length === 0
            ? 'The brain of this case'
            : ordered && path.length > 1
              ? `The route this answer rests on — ${path.length} steps`
              : 'What this answer rests on'}
        </p>
        <p className="text-[12px] text-subtle">
          {entities.toLocaleString()} entities · {edges.toLocaleString()} links · {documents} documents
        </p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Hide the brain"
          className="ml-auto rounded-lg p-1.5 text-subtle transition hover:bg-raised hover:text-ink"
        >
          <X size={16} />
        </button>
      </header>

      <div
        ref={host}
        className="min-h-0 flex-1"
        style={{ position: 'relative', width: '100%' }}
      />

      {path.length === 0 && (conclusions.length > 0 || questions.length > 0) && (
        <div className="max-h-[38%] shrink-0 overflow-y-auto border-t border-line px-4 py-3">
          {conclusions.length > 0 && (
            <>
              <p className="text-[11px] uppercase tracking-wide text-subtle">
                What it has worked out
              </p>
              <ul className="mt-1.5 space-y-1.5">
                {conclusions.map((item) => (
                  <li key={item.id} className="text-[12px] leading-5 text-muted">
                    {item.text}
                  </li>
                ))}
              </ul>
            </>
          )}
          {questions.length > 0 && (
            <>
              <p className="mt-3 text-[11px] uppercase tracking-wide text-subtle">Still open</p>
              <ul className="mt-1.5 space-y-1.5">
                {questions.map((item) => (
                  <li key={item.id} className="text-[12px] leading-5 text-muted">
                    {item.text}
                  </li>
                ))}
              </ul>
            </>
          )}
          <p className="mt-3 text-[11px] leading-5 text-subtle">
            This belongs to the case, not to the conversation. Clearing the thread does not
            touch it.
          </p>
        </div>
      )}
    </aside>
  )
}
