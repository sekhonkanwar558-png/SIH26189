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
