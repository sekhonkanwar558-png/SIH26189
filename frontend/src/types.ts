export interface CaseCounts {
  nodes: number
  edges: number
  documents: number
  graph_rev: number
}

export interface CaseSummary {
  case_id: string
  title: string
  officer: string
  case_type: string
  brief: string
  status: 'open' | 'paused' | 'closed'
  created: string
  updated: string
  synthetic: boolean
  counts: CaseCounts
  open_questions: number
}

export interface NewCaseInput {
  case_id: string
  title: string
  officer: string
  case_type: string
  brief: string
}

// --------------------------------------------------------------- workspace
// Everything below mirrors the backend contracts: README §5.1 (graph), §5.3
// (answer) and §5.6 (HTTP API). These are the server's shapes, not view
// models — if a screen needs something else, the fix is a field in §5.6, not
// a reshape in the client (§10.1a).

export type NodeType =
  | 'person'
  | 'phone'
  | 'organization'
  | 'location'
  | 'vehicle'
  | 'account'
  | 'device'
  | 'event'
  | 'document'

export type EdgeType =
  | 'CALLED'
  | 'MESSAGED'
  | 'TRANSFERRED_TO'
  | 'CO_OCCURS'
  | 'OWNS'
  | 'LOCATED_AT'
  | 'REGISTERED_TO'
  | 'MENTIONED_IN'

export interface SourceRef {
  doc_id: string
  start: number
  end: number
}

export interface GraphNode {
  id: string
  type: NodeType
  label: string
  attrs: Record<string, unknown>
  first_seen: string | null
  last_seen: string | null
  sources: SourceRef[]
}

export interface GraphEdge {
  id: string
  src: string
  dst: string
  type: EdgeType
  attrs: Record<string, unknown>
  weight: number
  confidence: number
  sources: SourceRef[]
}

export interface CaseGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  counts: CaseCounts
}

export interface CaseDocument {
  doc_id: string
  filename: string
  kind: string
  sha256: string
  ingested_at: string
  char_len: number
  meta: Record<string, unknown>
}

export interface CustodyVerification {
  valid: boolean
  entries: number
  head: string | null
  broken_at: number | null
  reason: string | null
}

export interface CaseDetail extends CaseSummary {
  documents: CaseDocument[]
  custody: CustodyVerification
  ner: NerBackend
}

export interface NerBackend {
  cue_patterns: boolean
  spacy: boolean
  spacy_model: string | null
}

export interface HealthReport {
  ok: boolean
  model: string
  model_available: boolean
  ner: NerBackend
  cases: number
}

/** §5.3 — the agent → UI boundary, plus the backend's own citation check. */
export interface AgentAnswer {
  answer: string
  cited_nodes: string[]
  cited_edges: string[]
  highlight_path: string[]
  confidence: 'high' | 'medium' | 'low'
  caveats: string[]
  /**
   * Optional on purpose. §5.6 describes this block as always present, and for
   * `/ask` it is — but `/brief` on a case with no documents returns a narrative
   * without it, because there were no citations to check. Absent means "not
   * verified", which is not the same as "failed verification", and the two are
   * rendered differently.
   */
  verified?: {
    ok: boolean
    dropped_nodes: string[]
    dropped_edges: string[]
  }
}

export interface Finding {
  id: string
  kind: string
  headline: string
  detail: string
  severity: 'high' | 'medium' | 'low'
  node_ids: string[]
  edge_ids: string[]
  ts: string | null
}

/** `/brief` wraps §5.3 in `narrative` — the findings stand without a model. */
export interface CaseBrief {
  case_id: string
  counts: CaseCounts
  findings: Finding[]
  new_findings: number
  requests: MemoryEntry[]
  open_questions: MemoryEntry[]
  narrative: AgentAnswer | null
}

export interface MemoryEntry {
  id: string
  kind: string
  status: string
  text: string
  node_ids: string[]
  edge_ids: string[]
  confidence?: number
  created?: string
  meta?: Record<string, unknown>
}

export interface Influencer {
  node_id: string
  label: string
  score: number
  metric: string
  why: string
}

export interface Community {
  cluster_id: string
  members: string[]
  people: string[]
  size: number
}

export interface Anomaly {
  kind: string
  description: string
  node_ids: string[]
  edge_ids: string[]
  score: number
  ts: string | null
}

export interface Analytics {
  influencers: Influencer[]
  communities: Community[]
  anomalies: Anomaly[]
  findings: Finding[]
}

export interface NodeProfile {
  node: GraphNode
  edges: GraphEdge[]
  neighbours: GraphNode[]
  documents: CaseDocument[]
}

export interface PathResult {
  path: string[]
  labels: string[]
  edges: string[]
  length: number
}

export interface SourceExcerpt {
  doc_id: string
  filename: string
  kind: string
  start: number
  end: number
  text: string
}

export interface CustodyEntry {
  seq: number
  ts: string
  actor: string
  action: string
  ref: string
  payload_sha256: string
  prev_hash: string
  hash: string
}

export interface CustodyLog {
  verification: CustodyVerification
  entries: CustodyEntry[]
}

/** What ingest reports back — `warnings` is D18 and must reach the officer. */
export interface IngestResult {
  doc_id: string
  kind: string
  chars: number
  nodes_new: number
  edges_new: number
  entities: string[]
  warnings: string[]
}

export interface UploadResponse {
  document: IngestResult
  analytics: Record<string, unknown>
  counts: CaseCounts
}
