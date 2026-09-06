import { useQuery } from '@tanstack/react-query'
import cytoscape from 'cytoscape'
import {
  ChevronRight,
  Crosshair,
  FileText,
  MessageSquareQuote,
  Minus,
  Plus,
  RotateCcw,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getMemory, getNode, getSource } from '../lib/api'
import type {
  CaseDocument,
  CaseGraph,
  GraphNode,
  NodeType,
  SourceExcerpt,
  SourceRef,
} from '../types'

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
 * (D25): an entity he clicks opens *inside* this panel, never beside it.
 *
 * What is lit is what the answer rested on, in Evidence Amber and in nothing
 * else (D28). Consecutive hops light the real edge between them; a finding's
 * unordered set lights its members only, because a set is not a journey anyone
 * can take (D23). **Nothing is ever drawn between two nodes with no edge.**
 *
 * ## Why it does not draw the whole case at once
 *
 * It used to. 116 entities and 1,148 links arrived as one cloud of identical
 * grey dots with no labels, which is a picture of *having* a graph rather than
 * a way of reading one — an officer could not tell a person from a bank
 * account, and clicking did nothing at all.
 *
 * It now opens on what matters and **opens further where he asks it to**: the
 * route an answer rests on, or the most connected entities in the case, and
 * every node expands to its own neighbours on a click. That is the same motion
 * an investigation actually has — start at a name, pull the thread — and it is
 * why depth is a click rather than a setting.
 */

// ------------------------------------------------------------------ language

const INK = '#0d0d0d'
const AMBER = '#b8791f'
const LINE = '#e4e4e8'

/**
 * A type is drawn, not written. Shape carries it first and tone second, so the
 * distinction survives both a projector and a colour-blind judge.
 *
 * These tones are deliberately desaturated and none of them is anywhere near
 * Evidence Amber, which still means one thing and only one thing (D28). The
 * rule that a colour must carry meaning is *kept* here rather than bent: in a
 * diagram the type of a thing IS meaning, and this is the one surface in the
 * product that is a diagram rather than prose.
 */
const TYPE_STYLE: Record<NodeType, { shape: string; tone: string; word: string }> = {
  person: { shape: 'ellipse', tone: '#394351', word: 'person' },
  phone: { shape: 'round-rectangle', tone: '#4a7268', word: 'number' },
  organization: { shape: 'hexagon', tone: '#55617a', word: 'organisation' },
  location: { shape: 'pentagon', tone: '#6b7a5c', word: 'place' },
  vehicle: { shape: 'rhomboid', tone: '#5f6f86', word: 'vehicle' },
  account: { shape: 'diamond', tone: '#5c5675', word: 'account' },
  device: { shape: 'barrel', tone: '#6e6577', word: 'device' },
  event: { shape: 'cut-rectangle', tone: '#7a6558', word: 'prior case' },
  document: { shape: 'rectangle', tone: '#b0b0b8', word: 'document' },
}

const styleFor = (type: string) =>
  TYPE_STYLE[type as NodeType] ?? { shape: 'ellipse', tone: '#6b6b76', word: type }

/** How many entities the brain opens on when nobody has asked it anything. */
const SEED = 26
/** A document can touch two hundred things. Opening all of them is a hairball
 *  again, so the busiest are opened and the officer is told what was held back. */
const FAN = 40

const TAU = Math.PI * 2

/**
 * One document an entity appears in — and the line it appears on.
 *
 * A filename is not evidence. The officer's question is "where does it say
 * that?", and the answer is three words further down the same list: the row
 * opens to the exact passage the entity was read out of, offsets and all. It is
 * the same trail the Evidence component draws under an answer, reachable from
 * the graph as well, because a thing he clicked on the picture and a thing he
 * read in a sentence are the same thing and must open the same way.
 */
function DocRow({
  caseId,
  doc,
  refs,
}: {
  caseId: string
  doc: CaseDocument
  refs: SourceRef[]
}) {
  const [open, setOpen] = useState(false)
  const [excerpt, setExcerpt] = useState<SourceExcerpt | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function toggle() {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    if (excerpt || error) return
    const ref = refs[0]
    if (!ref) {
      // A structured row (a CDR line, a bank entry) links without quoting prose,
      // so there is no passage to show. Saying so beats an empty box.
      setError('This one is a record rather than a passage — it links here without a line to quote.')
      return
    }
    try {
      setExcerpt(await getSource(caseId, ref.doc_id, ref.start, ref.end))
    } catch {
      setError('That source could not be opened.')
    }
  }

  return (
    <li>
      <button
        type="button"
        onClick={() => void toggle()}
        className="flex w-full items-center gap-2 rounded-lg px-1.5 py-1 text-left text-[12px] text-muted transition hover:bg-raised hover:text-ink"
      >
        <ChevronRight
          size={11}
          className={`shrink-0 text-subtle transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
        />
        <FileText size={12} className="shrink-0 text-subtle" />
        <span className="truncate">{doc.filename}</span>
      </button>

      {open && (
        <div className="rise mb-1 ml-[26px] mr-1 mt-1 rounded-lg border border-line bg-rail px-2.5 py-2">
          {excerpt ? (
            <>
              <p className="text-[12px] leading-6 text-ink">{excerpt.text}</p>
              <p className="mt-1.5 text-[11px] text-subtle">
                {excerpt.filename} · characters {excerpt.start.toLocaleString()}–
                {excerpt.end.toLocaleString()}
              </p>
            </>
          ) : (
            <p className="text-[11.5px] leading-5 text-subtle">
              {error ?? 'Opening…'}
            </p>
          )}
        </div>
      )}
    </li>
  )
}

// ------------------------------------------------------------------ the panel

export interface BrainProps {
  caseId: string
  graph: CaseGraph
  /** Ordered node ids the answer rests on, or an unordered cited set. Empty is
   *  the officer looking at the brain rather than an answer explaining itself. */
  path: string[]
  /** True when `path` is an ordered route, false when it is a cited set. */
  ordered: boolean
  onClose: () => void
  /** Put a question about this entity in the composer. The graph never answers
   *  anything itself — everything is still one chat (D25). */
  onAsk?: (question: string) => void
}

export function Brain({ caseId, graph, path, ordered, onClose, onAsk }: BrainProps) {
  const host = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const shown = useRef<Set<string>>(new Set())

  const [selected, setSelected] = useState<string | null>(null)
  const [held, setHeld] = useState<{ id: string; hidden: number } | null>(null)
  const [depth, setDepth] = useState(0)
  /** How many entities are on screen. Mirrors `shown`, which is a ref because
   *  the expand handler writes it — a ref read during render is a stale read. */
  const [drawn, setDrawn] = useState(0)

  // ------------------------------------------------------------- the case, indexed

  const index = useMemo(() => {
    const nodes = new Map<string, GraphNode>()
    for (const node of graph.nodes) nodes.set(node.id, node)

    // Only edges whose both ends are real nodes: an edge to something the graph
    // does not hold is a line drawn between a thing and nothing.
    const near = new Map<string, Set<string>>()
    const degree = new Map<string, number>()
    const edges = graph.edges.filter((e) => nodes.has(e.src) && nodes.has(e.dst))
    for (const edge of edges) {
      if (!near.has(edge.src)) near.set(edge.src, new Set())
      if (!near.has(edge.dst)) near.set(edge.dst, new Set())
      near.get(edge.src)!.add(edge.dst)
      near.get(edge.dst)!.add(edge.src)
      degree.set(edge.src, (degree.get(edge.src) ?? 0) + 1)
      degree.set(edge.dst, (degree.get(edge.dst) ?? 0) + 1)
    }
    const byDegree = (a: string, b: string) => (degree.get(b) ?? 0) - (degree.get(a) ?? 0)
    const isWho = (id: string) => {
      const t = nodes.get(id)?.type
      return t === 'person' || t === 'organization'
    }
    // People and organisations first, each still ranked by how connected it is.
    const busiest = [
      ...[...nodes.keys()].filter(isWho).sort(byDegree),
      ...[...nodes.keys()].filter((id) => !isWho(id)).sort(byDegree),
    ]
    return { nodes, edges, near, degree, busiest }
  }, [graph])

  /** Size says how connected a thing is, which is the case's own argument about
   *  who matters — the same quantity the analytics rank on. */
  const sizeOf = useCallback(
    (id: string) => {
      const d = index.degree.get(id) ?? 0
      return Math.round(Math.min(38, 13 + Math.sqrt(d) * 3.4))
    },
    [index],
  )

  const elementsFor = useCallback(
    (ids: Set<string>, lit: Set<string>, hops: Set<string>) => {
      const nodes = [...ids]
        .filter((id) => index.nodes.has(id))
        .map((id) => {
          const node = index.nodes.get(id)!
          const face = styleFor(node.type)
          const size = sizeOf(id)
          return {
            data: {
              id,
              label: node.label,
              shape: face.shape,
              tone: face.tone,
              size,
              lit: lit.has(id) ? 1 : 0,
              // A label on every dot is a label on nothing, and a phone number
              // written across a person's name is worse than no label at all.
              // Named things carry their name; identifiers wait for a hover.
              named:
                lit.has(id) || ((node.type === 'person' || node.type === 'organization') && size >= 17)
                  ? 1
                  : 0,
            },
          }
        })

      const edges = index.edges
        .filter((e) => ids.has(e.src) && ids.has(e.dst))
        .map((e) => ({
          data: {
            id: e.id,
            source: e.src,
            target: e.dst,
            kind: e.type,
            lit: hops.size
              ? hops.has(`${e.src}|${e.dst}`)
                ? 1
                : 0
              : lit.has(e.src) && lit.has(e.dst)
                ? 1
                : 0,
          },
        }))

      return { nodes, edges }
    },
    [index, sizeOf],
  )

  // ------------------------------------------------------------------ opening

  /**
   * What the panel opens on: the answer's own nodes, or a readable core of the
   * case.
   *
   * The core is **people first, then whatever binds them**. People alone do not
   * work: in a case built largely from call records two men are connected
   * *through* their handsets, so a seed of the twenty busiest people is twenty
   * islands, and the layout draws them as a grid of loose dots — a picture of
   * a case with no connections in it, which is the opposite of the claim.
   *
   * So the bridges come too: the phones, accounts and places that touch two or
   * more of the people already in, busiest first. What opens is a network.
   */
  const opening = useMemo(() => {
    if (path.length > 0) return path.filter((id) => index.nodes.has(id))

    const isWho = (id: string) => {
      const t = index.nodes.get(id)?.type
      return t === 'person' || t === 'organization'
    }
    const people = index.busiest.filter(isWho).slice(0, Math.round(SEED * 0.55))
    const core = new Set(people)

    const bridges = index.busiest
      .filter((id) => !core.has(id))
      .map((id) => ({
        id,
        joins: [...(index.near.get(id) ?? [])].filter((n) => core.has(n)).length,
      }))
      .filter((c) => c.joins >= 2)
      .sort((a, b) => b.joins - a.joins)

    for (const bridge of bridges) {
      if (core.size >= SEED) break
      core.add(bridge.id)
    }

    // Anything still touching nothing on screen is a dot in a corner saying
    // nothing. It is one click away in the graph it does belong to.
    return [...core].filter((id) => {
      const near = index.near.get(id)
      return near ? [...near].some((n) => core.has(n)) : false
    })
  }, [path, index])

  const paint = useCallback(() => {
    const cy = cyRef.current
    if (!cy) return

    const lit = new Set(path)
    const hops = new Set<string>()
    if (ordered) {
      for (let i = 0; i < path.length - 1; i += 1) {
        hops.add(`${path[i]}|${path[i + 1]}`)
        hops.add(`${path[i + 1]}|${path[i]}`)
      }
    }

    const ids = new Set(opening)
    // A route of two nodes with nothing around it is a picture of a fact, not a
    // place to look. Where the opening is small, one hop of context comes with
    // it — dimmed, and never drawn where there is no edge.
    if (ids.size > 0 && ids.size <= 8) {
      for (const id of [...ids]) {
        for (const other of index.near.get(id) ?? []) {
          if (ids.size >= 34) break
          ids.add(other)
        }
      }
    }

    shown.current = ids
    setDrawn(ids.size)
    setSelected(null)
    setHeld(null)
    setDepth(0)

    cy.batch(() => {
      cy.elements().remove()
      const { nodes, edges } = elementsFor(ids, lit, hops)
      // Nodes first: an edge added before its ends throws.
      cy.add([...nodes, ...edges] as cytoscape.ElementDefinition[])
    })

    // The panel and this canvas mount in the same commit, so cytoscape can
    // measure its container before the browser has laid it out and cache a
    // viewport it then never repaints — 26 nodes, correct positions, correct
    // styles, and an empty canvas until something else forces a redraw. The
    // resize before layout and the one on the next frame are what land the
    // first paint; without them the graph only ever appears if you touch it.
    cy.resize()
    cy.layout({
      name: 'cose',
      animate: false,
      nodeRepulsion: () => 14000,
      idealEdgeLength: () => 78,
      nodeOverlap: 18,
      padding: 48,
      randomize: true,
    } as cytoscape.LayoutOptions).run()

    requestAnimationFrame(() => {
      if (!cyRef.current) return
      cy.resize()
      // `resize()` alone returns early when the box has not changed, so on the
      // first open nothing is ever drawn — the graph appeared only if the
      // window happened to be resized. This is what lands the opening frame.
      cy.forceRender()
      cy.animate(
        { fit: { eles: cy.elements(), padding: 56 } },
        { duration: 420, easing: 'ease-out-cubic' },
      )
    })
  }, [path, ordered, opening, index, elementsFor])

  // ---------------------------------------------------------------- expanding

  /**
   * Open one entity to its own connections.
   *
   * New nodes are born at their parent and fan out to a ring, which is the
   * whole reason this reads as *opening* rather than as a redraw: the eye keeps
   * hold of where they came from. Nothing already on screen moves, so the
   * officer never loses the thing he was looking at — the commonest way a graph
   * UI throws its user away.
   */
  const open = useCallback(
    (id: string) => {
      const cy = cyRef.current
      if (!cy) return
      const parent = cy.getElementById(id)
      if (parent.empty()) return

      const all = [...(index.near.get(id) ?? [])]
      const fresh = all.filter((n) => !shown.current.has(n))
      if (fresh.length === 0) {
        setHeld(null)
        return
      }

      // The busiest first, because they are the ones that lead somewhere.
      fresh.sort((a, b) => (index.degree.get(b) ?? 0) - (index.degree.get(a) ?? 0))
      const taking = fresh.slice(0, FAN)
      const hidden = fresh.length - taking.length

      const at = parent.position()
      // Fan away from the middle of what is already drawn, so growth happens in
      // open space instead of on top of the graph.
      const centre = { x: 0, y: 0 }
      cy.nodes().forEach((n) => {
        centre.x += n.position('x')
        centre.y += n.position('y')
      })
      const n = Math.max(1, cy.nodes().length)
      centre.x /= n
      centre.y /= n
      const away = Math.atan2(at.y - centre.y, at.x - centre.x) || 0

      for (const nid of taking) shown.current.add(nid)

      const lit = new Set(path)
      const hops = new Set<string>()
      if (ordered) {
        for (let i = 0; i < path.length - 1; i += 1) {
          hops.add(`${path[i]}|${path[i + 1]}`)
          hops.add(`${path[i + 1]}|${path[i]}`)
        }
      }
      const { nodes, edges } = elementsFor(shown.current, lit, hops)
      const existing = new Set(cy.nodes().map((el) => el.id()))
      const edgesOn = new Set(cy.edges().map((el) => el.id()))

      const radius = 92 + Math.min(96, taking.length * 6)
      const spread = taking.length <= 2 ? 0.9 : Math.min(TAU * 0.62, 0.42 * taking.length)

      cy.batch(() => {
        const addedNodes = nodes.filter((el) => !existing.has(el.data.id))
        const addedEdges = edges.filter((el) => !edgesOn.has(el.data.id))
        cy.add(addedNodes as cytoscape.ElementDefinition[])
        cy.add(addedEdges as cytoscape.ElementDefinition[])
      })

      taking.forEach((nid, i) => {
        const el = cy.getElementById(nid)
        if (el.empty()) return
        const t = taking.length === 1 ? 0 : i / (taking.length - 1) - 0.5
        const angle = away + t * spread
        el.position({ x: at.x, y: at.y })
        el.style({ opacity: 0 })
        el.animate(
          {
            position: {
              x: at.x + Math.cos(angle) * radius,
              y: at.y + Math.sin(angle) * radius,
            },
            style: { opacity: 1 },
          },
          { duration: 460, easing: 'ease-out-cubic' },
        )
      })

      // Edges arrive with the nodes they belong to rather than snapping in first.
      cy.edges().filter((el) => Number(el.style('opacity')) === 0 || !edgesOn.has(el.id()))
        .style({ opacity: 0 })
        .animate({ style: { opacity: 1 } }, { duration: 460, easing: 'ease-out-cubic', queue: false })

      parent.addClass('opened')
      setDrawn(shown.current.size)
      setHeld(hidden > 0 ? { id, hidden } : null)
      setDepth((d) => d + 1)

      window.setTimeout(() => {
        if (!cyRef.current) return
        // The entity panel below has opened by now and taken the canvas with
        // it; fitting before that put the new nodes underneath it.
        cy.resize()
        cy.animate(
          { fit: { eles: cy.elements(), padding: 48 } },
          { duration: 420, easing: 'ease-in-out-cubic' },
        )
      }, 520)
    },
    [index, path, ordered, elementsFor],
  )

  // ------------------------------------------------------------------- mount

  /** The tap handler is bound once but must always call the current `open`. */
  const openRef = useRef(open)
  useEffect(() => {
    openRef.current = open
  }, [open])

  useEffect(() => {
    if (!host.current) return

    const cy = cytoscape({
      container: host.current,
      style: ([
        {
          selector: 'node',
          style: {
            'background-color': 'data(tone)',
            'background-opacity': 0.92,
            shape: 'data(shape)',
            width: 'data(size)',
            height: 'data(size)',
            'border-width': 0,
            'border-color': '#ffffff',
            label: '',
            'transition-property': 'background-color, border-width, width, height, opacity',
            'transition-duration': 180,
          },
        },
        {
          selector: 'node[named = 1]',
          style: {
            label: 'data(label)',
            'font-size': 10.5,
            'font-family': 'Inter Variable, Inter, system-ui, sans-serif',
            'font-weight': 500,
            color: '#4a4a55',
            'text-valign': 'bottom',
            'text-margin-y': 5,
            'text-max-width': '120px',
            'text-wrap': 'ellipsis',
          },
        },
        {
          selector: 'node.opened',
          style: { 'border-width': 2, 'border-color': '#ffffff', 'border-opacity': 1 },
        },
        {
          selector: 'node[lit = 1]',
          style: {
            'background-color': AMBER,
            'background-opacity': 1,
            color: INK,
            'font-weight': 600,
            'font-size': 11,
            label: 'data(label)',
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.92,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          },
        },
        {
          selector: 'node.hot',
          style: {
            label: 'data(label)',
            color: INK,
            'font-weight': 600,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.95,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'border-width': 3,
            'border-color': '#ffffff',
            'z-index': 20,
          },
        },
        { selector: 'node.picked', style: { 'border-width': 3, 'border-color': INK, 'z-index': 30 } },
        { selector: '.dim', style: { opacity: 0.12 } },
        {
          selector: 'edge',
          style: {
            'curve-style': 'straight',
            width: 1,
            'line-color': LINE,
            opacity: 0.75,
            'transition-property': 'line-color, width, opacity',
            'transition-duration': 180,
          },
        },
        { selector: 'edge[lit = 1]', style: { 'line-color': AMBER, width: 2.4, opacity: 1 } },
        { selector: 'edge.hot', style: { 'line-color': '#8f8f98', width: 1.8, opacity: 1, 'z-index': 10 } },
        // Data-driven `shape` and `width` are valid cytoscape mappers that the
        // published types do not model, so the sheet is cast as a whole.
      ] as unknown) as cytoscape.CytoscapeOptions['style'],
      minZoom: 0.15,
      maxZoom: 3.5,
      wheelSensitivity: 0.22,
      // The graph is a thing to read, not a thing to rearrange. Panning and
      // zooming are his; dragging a node somewhere meaningless is not.
      autoungrabify: true,
      boxSelectionEnabled: false,
    })
    cyRef.current = cy

    cy.on('tap', 'node', (event) => {
      const node = event.target as cytoscape.NodeSingular
      cy.nodes().removeClass('picked')
      node.addClass('picked')
      setSelected(node.id())
      openRef.current(node.id())
    })

    cy.on('tap', (event) => {
      if (event.target === cy) {
        cy.nodes().removeClass('picked')
        setSelected(null)
        setHeld(null)
      }
    })

    cy.on('mouseover', 'node', (event) => {
      const node = event.target as cytoscape.NodeSingular
      const keep = node.closedNeighborhood()
      cy.elements().difference(keep).addClass('dim')
      node.addClass('hot')
      keep.edges().addClass('hot')
      if (host.current) host.current.style.cursor = 'pointer'
    })

    cy.on('mouseout', 'node', () => {
      cy.elements().removeClass('dim hot')
      if (host.current) host.current.style.cursor = 'default'
    })

    // Cytoscape sets `position: relative` on its container at runtime, which
    // beats a Tailwind `absolute` and collapses the canvas to zero height. The
    // container is sized inline, and a ResizeObserver keeps it right when the
    // panel opens, closes or the window changes.
    const observer = new ResizeObserver(() => cy.resize())
    observer.observe(host.current)

    return () => {
      observer.disconnect()
      cy.destroy()
      cyRef.current = null
    }
  }, [])

  useEffect(() => {
    paint()
  }, [paint])

  // ------------------------------------------------------------------ reading

  const profile = useQuery({
    queryKey: ['node', caseId, selected],
    queryFn: () => getNode(caseId, selected as string),
    enabled: Boolean(selected),
    staleTime: 60_000,
  })

  const memory = useQuery({
    queryKey: ['memory', caseId],
    queryFn: () => getMemory(caseId),
    enabled: path.length === 0 && !selected,
    staleTime: 30_000,
  })

  const { nodes, edges, documents } = graph.counts
  // Documents are nodes too (§5.1); they are not entities, and the count
  // beside an upload's "read 11 entities" has to agree with it.
  const entities = nodes - documents
  const conclusions = (memory.data ?? []).filter((m) => m.kind === 'conclusion').slice(0, 3)
  const questions = (memory.data ?? [])
    .filter((m) => m.kind === 'open_question' && m.status === 'open')
    .slice(0, 2)

  const node = index.nodes.get(selected ?? '')
  const face = node ? styleFor(node.type) : null
  const links = selected ? (index.degree.get(selected) ?? 0) : 0

  /**
   * Reach a node from the panel rather than the picture.
   *
   * It may not be drawn yet — the officer is reading a list of connections, and
   * most of them are one hop past what is on screen. So it is added if missing,
   * centred, selected and opened, which is exactly what clicking it would have
   * done had he been able to see it.
   */
  const focus = (id: string) => {
    const cy = cyRef.current
    if (!cy) return
    if (!shown.current.has(id) && selected) open(selected)
    const el = cy.getElementById(id)
    if (el.empty()) return
    cy.nodes().removeClass('picked')
    el.addClass('picked')
    setSelected(id)
    cy.animate(
      { center: { eles: el }, zoom: Math.max(cy.zoom(), 0.9) },
      { duration: 360, easing: 'ease-out-cubic' },
    )
    open(id)
  }

  const zoom = (by: number) => {
    const cy = cyRef.current
    if (!cy) return
    cy.animate({ zoom: cy.zoom() * by, center: { eles: cy.elements() } }, { duration: 200 })
  }

  const fit = () => {
    const cy = cyRef.current
    if (!cy) return
    cy.animate({ fit: { eles: cy.elements(), padding: 56 } }, { duration: 380, easing: 'ease-out-cubic' })
  }

  return (
    <aside className="flex h-full min-h-0 w-full flex-col border-l border-line bg-rail">
      <header className="flex shrink-0 items-center gap-3 px-4 pb-2.5 pt-3.5">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium text-ink">
            {path.length === 0
              ? 'The brain of this case'
              : ordered && path.length > 1
                ? `The route this answer rests on — ${path.length} steps`
                : 'What this answer rests on'}
          </p>
          <p className="mt-0.5 text-[11.5px] text-subtle">
            {entities.toLocaleString()} entities · {edges.toLocaleString()} links · {documents}{' '}
            documents
          </p>
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-0.5">
          <button
            type="button"
            onClick={() => zoom(1 / 1.35)}
            aria-label="Zoom out"
            className="rounded-lg p-1.5 text-subtle transition hover:bg-raised hover:text-ink"
          >
            <Minus size={14} />
          </button>
          <button
            type="button"
            onClick={() => zoom(1.35)}
            aria-label="Zoom in"
            className="rounded-lg p-1.5 text-subtle transition hover:bg-raised hover:text-ink"
          >
            <Plus size={14} />
          </button>
          <button
            type="button"
            onClick={fit}
            aria-label="Fit everything on screen"
            className="rounded-lg p-1.5 text-subtle transition hover:bg-raised hover:text-ink"
          >
            <Crosshair size={14} />
          </button>
          <button
            type="button"
            onClick={paint}
            aria-label="Back to where it opened"
            title="Back to where it opened"
            className="rounded-lg p-1.5 text-subtle transition hover:bg-raised hover:text-ink disabled:opacity-30"
            disabled={depth === 0}
          >
            <RotateCcw size={14} />
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Hide the brain"
            className="ml-1 rounded-lg p-1.5 text-subtle transition hover:bg-raised hover:text-ink"
          >
            <X size={16} />
          </button>
        </div>
      </header>

      <div className="relative min-h-0 flex-1">
        <div ref={host} className="h-full w-full" style={{ position: 'relative' }} />

        <p className="pointer-events-none absolute inset-x-0 bottom-2 text-center text-[11px] text-subtle">
          {held
            ? `${held.hidden} more connections held back — the busiest ${FAN} are shown`
            : depth === 0
              ? 'Click any entity to open its connections'
              : `Showing ${drawn} of ${entities.toLocaleString()} entities`}
        </p>
      </div>

      {/* One panel, and this is inside it (D25). An entity opens here; it never
          opens a second surface beside the chat. */}
      {node && face ? (
        <div className="max-h-[46%] shrink-0 overflow-y-auto border-t border-line bg-canvas px-4 py-3.5">
          <div className="flex items-start gap-2.5">
            <span
              aria-hidden
              className="mt-1.5 inline-block h-2.5 w-2.5 shrink-0 rounded-[3px]"
              style={{ background: face.tone }}
            />
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-medium leading-5 text-ink">{node.label}</p>
              <p className="mt-0.5 text-[12px] text-subtle">
                {face.word} · {links.toLocaleString()} {links === 1 ? 'link' : 'links'}
                {profile.data ? ` · in ${profile.data.documents.length} of ${documents} documents` : ''}
              </p>
            </div>
          </div>

          {profile.data && profile.data.documents.length > 0 && (
            <>
              <p className="mt-3.5 px-1.5 text-[11px] uppercase tracking-[0.07em] text-subtle">
                Where it appears
              </p>
              <ul className="mt-1">
                {profile.data.documents.map((doc) => (
                  <DocRow
                    key={doc.doc_id}
                    caseId={caseId}
                    doc={doc}
                    refs={node.sources.filter((ref) => ref.doc_id === doc.doc_id)}
                  />
                ))}
              </ul>
            </>
          )}

          {profile.data && profile.data.neighbours.length > 0 && (
            <>
              <p className="mt-3.5 px-1.5 text-[11px] uppercase tracking-[0.07em] text-subtle">
                Connected to
              </p>
              <ul className="mt-1">
                {profile.data.neighbours.map((other) => {
                  const otherFace = styleFor(other.type)
                  return (
                    <li key={other.id}>
                      {/* Every connection is a way further in. Clicking one puts
                          it on the graph and opens it, so the panel and the
                          picture are two views of one walk rather than two
                          places to be. */}
                      <button
                        type="button"
                        onClick={() => focus(other.id)}
                        className="flex w-full items-center gap-2 rounded-lg px-1.5 py-1 text-left text-[12px] text-muted transition hover:bg-raised hover:text-ink"
                      >
                        <span
                          aria-hidden
                          className="inline-block h-2 w-2 shrink-0 rounded-[2px]"
                          style={{ background: otherFace.tone }}
                        />
                        <span className="truncate">{other.label}</span>
                        <span className="ml-auto shrink-0 text-[11px] text-subtle">
                          {otherFace.word}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </>
          )}

          {onAsk && (
            <button
              type="button"
              onClick={() => onAsk(`What do we know about ${node.label}?`)}
              className="mt-3.5 inline-flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-2.5 py-1.5 text-[12px] text-muted transition hover:border-line-strong hover:text-ink"
            >
              <MessageSquareQuote size={12} />
              Ask about {node.label.split(' ')[0]}
            </button>
          )}
        </div>
      ) : (
        path.length === 0 &&
        (conclusions.length > 0 || questions.length > 0) && (
          <div className="max-h-[38%] shrink-0 overflow-y-auto border-t border-line bg-canvas px-4 py-3">
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
        )
      )}
    </aside>
  )
}
