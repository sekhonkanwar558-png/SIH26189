import type {
  CoseLayoutOptions,
  EdgeSingular,
  ElementDefinition,
  StylesheetJson,
} from 'cytoscape'
import { INFERRED_BELOW, entityIconUri, entityStyle } from './entities'
import type { CaseGraph, Community, GraphEdge, GraphNode } from '../types'

/**
 * Everything the Connections canvas needs to turn a §5.1 graph into something
 * an officer can read. Kept out of the component so the canvas file is about
 * interaction and this one is about the picture.
 */

/** Three sizes, because more than three stops meaning anything at a glance. */
const NODE_SIZES = [34, 46, 60] as const

export interface GraphFilters {
  /** Node types the officer has switched off. */
  hiddenTypes: string[]
  /** Document nodes are hubs and are off by default — see §5.6 `/graph`. */
  includeDocuments: boolean
  /** Hide links the system inferred rather than read, below `INFERRED_BELOW`. */
  hideInferred: boolean
}

export const defaultFilters: GraphFilters = {
  hiddenTypes: [],
  includeDocuments: false,
  hideInferred: false,
}

/**
 * Degree decides node size, and it is computed from the edges actually being
 * drawn rather than from the whole case: a node whose links are all filtered
 * out should not still look important.
 */
function sizeLevels(nodes: GraphNode[], edges: GraphEdge[]) {
  const degree = new Map<string, number>()
  for (const node of nodes) degree.set(node.id, 0)
  for (const edge of edges) {
    if (degree.has(edge.src)) degree.set(edge.src, (degree.get(edge.src) ?? 0) + 1)
    if (degree.has(edge.dst)) degree.set(edge.dst, (degree.get(edge.dst) ?? 0) + 1)
  }

  const ranked = [...degree.values()].sort((a, b) => a - b)
  const at = (fraction: number) => ranked[Math.floor(ranked.length * fraction)] ?? 0
  const mid = at(0.6)
  const high = at(0.9)

  return { degree, mid, high }
}

export function buildElements(
  graph: CaseGraph,
  communities: Community[],
  filters: GraphFilters,
): ElementDefinition[] {
  const clusterOf = new Map<string, string>()
  for (const community of communities) {
    for (const member of community.members) clusterOf.set(member, community.cluster_id)
  }

  const hidden = new Set(filters.hiddenTypes)
  const nodes = graph.nodes.filter((node) => {
    if (node.type === 'document' && !filters.includeDocuments) return false
    return !hidden.has(node.type)
  })
  const visible = new Set(nodes.map((node) => node.id))
  const edges = graph.edges.filter((edge) => {
    if (!visible.has(edge.src) || !visible.has(edge.dst)) return false
    return !(filters.hideInferred && edge.confidence < INFERRED_BELOW)
  })

  const { degree, mid, high } = sizeLevels(nodes, edges)

  const nodeElements: ElementDefinition[] = nodes.map((node) => {
    const count = degree.get(node.id) ?? 0
    const size = count >= high ? NODE_SIZES[2] : count >= mid ? NODE_SIZES[1] : NODE_SIZES[0]
    const style = entityStyle(node.type)
    return {
      group: 'nodes',
      data: {
        id: node.id,
        label: node.label,
        type: node.type,
        cluster: clusterOf.get(node.id) ?? 'c0',
        degree: count,
        size,
        tint: style.tint,
        border: style.border,
        ink: style.ink,
        icon: entityIconUri(node.type),
      },
    }
  })

  const edgeElements: ElementDefinition[] = edges.map((edge) => ({
    group: 'edges',
    data: {
      id: edge.id,
      source: edge.src,
      target: edge.dst,
      type: edge.type,
      confidence: edge.confidence,
      inferred: edge.confidence < INFERRED_BELOW,
      sameCluster: clusterOf.get(edge.src) === clusterOf.get(edge.dst),
    },
  }))

  return [...nodeElements, ...edgeElements]
}

export const stylesheet: StylesheetJson = [
  {
    selector: 'node',
    style: {
      width: 'data(size)',
      height: 'data(size)',
      'background-color': 'data(tint)',
      'background-image': 'data(icon)',
      'background-fit': 'none',
      'background-width': '52%',
      'background-height': '52%',
      'border-width': 1.5,
      'border-color': 'data(border)',
      shape: 'ellipse',
      label: 'data(label)',
      'font-family': 'Inter Variable, Inter, system-ui, sans-serif',
      'font-size': 11,
      'font-weight': 500,
      color: '#48515B',
      'text-valign': 'bottom',
      'text-margin-y': 5,
      'text-max-width': '110px',
      'text-wrap': 'ellipsis',
      'text-background-color': '#FFFFFF',
      'text-background-opacity': 0.82,
      'text-background-padding': '2px',
      'text-background-shape': 'roundrectangle',
      'transition-property': 'opacity, border-width, border-color',
      'transition-duration': 180,
    },
  },
  {
    selector: 'edge',
    style: {
      width: 1,
      'line-color': '#D3D8DE',
      'curve-style': 'bezier',
      'control-point-step-size': 28,
      opacity: 0.75,
      'transition-property': 'opacity, line-color, width',
      'transition-duration': 180,
    },
  },
  {
    // Inferred rather than recorded — dashed, so the officer can see which
    // links the system worked out and which a document stated outright.
    selector: 'edge[?inferred]',
    style: { 'line-style': 'dashed', 'line-dash-pattern': [5, 4], opacity: 0.6 },
  },
  {
    selector: 'node:selected',
    style: { 'border-width': 3, 'border-color': '#245B8A' },
  },
  {
    selector: 'edge:selected',
    style: { 'line-color': '#245B8A', width: 2.4, opacity: 1 },
  },
  {
    selector: '.faded',
    style: { opacity: 0.12, 'text-opacity': 0.12 },
  },
  {
    // Evidence Amber: the reasoning, not decoration (§3.5 / D3).
    selector: 'node.on-path',
    style: {
      'border-width': 3.5,
      'border-color': '#C58B2A',
      'background-color': '#FBF4E6',
      color: '#20252B',
      'font-weight': 600,
      'z-index': 30,
    },
  },
  {
    selector: 'edge.on-path',
    style: {
      'line-color': '#C58B2A',
      width: 3,
      opacity: 1,
      'line-style': 'solid',
      'z-index': 30,
    },
  },
  {
    selector: '.search-hit',
    style: { 'border-width': 3, 'border-color': '#245B8A', 'z-index': 25 },
  },
  {
    selector: '.dimmed-hidden',
    style: { display: 'none' },
  },
]

export function layoutOptions(elementCount: number): CoseLayoutOptions {
  return {
    name: 'cose',
    // Computed, then placed. Animating a force layout through its iterations
    // on a graph this dense reads as a wobble, not as motion worth watching —
    // the demo case alone carries 1,148 links.
    animate: false,
    randomize: false,
    // Nodes in one community settle closer together, so the clusters the
    // analytics found are the clusters the officer sees.
    idealEdgeLength: (edge: EdgeSingular) => (edge.data('sameCluster') ? 55 : 130),
    edgeElasticity: (edge: EdgeSingular) => (edge.data('sameCluster') ? 120 : 45),
    nodeRepulsion: () => 12_000,
    nodeOverlap: 14,
    gravity: 42,
    nestingFactor: 1.1,
    // A dense case is the normal case here — the demo graph alone carries
    // 1,148 links — so the iteration count comes down as the graph grows.
    numIter: elementCount > 900 ? 700 : 1_200,
    componentSpacing: 90,
    fit: true,
    padding: 42,
  }
}

/**
 * Turn a list of highlighted node ids into the edges to light with them.
 *
 * Two different things arrive here and they render differently:
 *
 * - **An ordered path** from an answer's `highlight_path` (§5.3). Consecutive
 *   nodes are joined, so each hop gets exactly one amber edge and the path
 *   draws itself in order. Where a pair is joined by several links the most
 *   confident one is lit.
 * - **A set of entities** from a finding — `node_ids` has no ordering and its
 *   members are usually not adjacent. Lighting consecutive pairs would draw
 *   nothing at all, so when no hop connects, every edge *inside* the set is lit
 *   instead. Those links are real; only the ordering was never there.
 *
 * What is never done is drawing a line between two nodes with no edge between
 * them, which would invent a connection the case does not contain.
 */
export function pathEdgeIds(path: string[], edges: GraphEdge[]) {
  const between = (a: string, b: string) =>
    edges.filter(
      (edge) => (edge.src === a && edge.dst === b) || (edge.src === b && edge.dst === a),
    )
  const strongest = (candidates: GraphEdge[]) =>
    candidates.reduce((left, right) => (right.confidence > left.confidence ? right : left))

  const hops: string[] = []
  for (let index = 0; index < path.length - 1; index += 1) {
    const candidates = between(path[index], path[index + 1])
    if (candidates.length > 0) hops.push(strongest(candidates).id)
  }
  if (hops.length > 0) return { edgeIds: hops, ordered: true }

  const members = new Set(path)
  const inside = edges
    .filter((edge) => members.has(edge.src) && members.has(edge.dst))
    .map((edge) => edge.id)
  return { edgeIds: inside, ordered: false }
}

const POSITIONS_KEY = 'caselens.graph-positions'
const FILTERS_KEY = 'caselens.graph-filters'

type PositionMap = Record<string, { x: number; y: number }>

function readStore<T>(key: string, caseId: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(`${key}.${caseId}`)
    return raw ? ({ ...fallback, ...(JSON.parse(raw) as T) } as T) : fallback
  } catch {
    return fallback
  }
}

function writeStore(key: string, caseId: string, value: unknown) {
  try {
    window.localStorage.setItem(`${key}.${caseId}`, JSON.stringify(value))
  } catch {
    // A browser with storage disabled still gets a working graph; it just
    // will not remember where the officer dragged things.
  }
}

export const loadPositions = (caseId: string) =>
  readStore<PositionMap>(POSITIONS_KEY, caseId, {})
export const savePositions = (caseId: string, positions: PositionMap) =>
  writeStore(POSITIONS_KEY, caseId, positions)
export const clearPositions = (caseId: string) => {
  try {
    window.localStorage.removeItem(`${POSITIONS_KEY}.${caseId}`)
  } catch {
    // Nothing to clear when storage is unavailable.
  }
}

export const loadFilters = (caseId: string) =>
  readStore<GraphFilters>(FILTERS_KEY, caseId, defaultFilters)
export const saveFilters = (caseId: string, filters: GraphFilters) =>
  writeStore(FILTERS_KEY, caseId, filters)
