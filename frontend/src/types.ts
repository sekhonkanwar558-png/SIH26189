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

// ------------------------------------------------------------------ the case
// Everything below mirrors the backend contracts: README §5.1 (graph), §5.3
// (answer) and §5.6 (HTTP API). These are the server's shapes, not view
// models — if a screen needs something else, the fix is a field in §5.6, not
// a reshape in the client.
//
// Only what the chat actually calls is here. The nine §5.6 endpoints the
// interface does not call (custody, path, timeline, analytics, investigate)
// are reached by *asking* — they are the agent's tools, not screens — so
// carrying their types here would be describing a client that no longer
// exists. README §11 lists them and says why.

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

/** §5.3 — the agent → UI boundary, plus the backend's own citation check. */
export interface AgentAnswer {
  answer: string
  cited_nodes: string[]
  cited_edges: string[]
  highlight_path: string[]
  /**
   * What kind of thing was just said. `evidence` asserts something about this
   * case and must rest on it, so an uncited one fails verification. `guidance`
   * is advice, a plan, a clarifying question — it asserts no case fact, so it
   * has nothing to cite and is not a failure. Absent means treat as evidence.
   */
  claim_type?: 'evidence' | 'guidance'
  confidence: 'high' | 'medium' | 'low'
  caveats: string[]
  /**
   * Always present on /ask and /brief. Absent only on an answer stored before
   * that was true, so a missing block means "no verification ran" — which is
   * not the same as failing one, and the two are rendered differently.
   */
  verified?: {
    ok: boolean
    dropped_nodes: string[]
    dropped_edges: string[]
  }
}

/** One turn of the case's own conversation. Stored on the case (D27), so this
 *  is fetched rather than remembered by the browser. */
export interface ConversationTurn {
  seq: number
  role: 'officer' | 'shikonye'
  actor: string
  text: string
  answer: AgentAnswer | Record<string, never>
  node_ids: string[]
  ts: string
  graph_rev: number
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
  /** True when nothing has been found since the last briefing, so this is the
   *  one already in the thread rather than a new one. */
  repeat?: boolean
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

export interface NodeProfile {
  node: GraphNode
  edges: GraphEdge[]
  neighbours: GraphNode[]
  documents: CaseDocument[]
}

export interface SourceExcerpt {
  doc_id: string
  filename: string
  kind: string
  start: number
  end: number
  text: string
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
