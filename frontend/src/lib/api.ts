import type {
  AgentAnswer,
  CaseBrief,
  CaseGraph,
  CaseSummary,
  ConversationTurn,
  MemoryEntry,
  NewCaseInput,
  NodeProfile,
  SourceExcerpt,
  UploadResponse,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** 503 means the assistant itself is down — not the case service. The two read
 *  very differently to an officer and must not be shown the same way. */
export const isAssistantDown = (error: unknown) =>
  error instanceof ApiError && error.status === 503

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // The browser sets multipart's own Content-Type, boundary included. Forcing
  // application/json onto a FormData body makes the upload unparseable.
  const isForm = init?.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    let detail = 'The case service could not complete this request.'
    try {
      const body = (await response.json()) as { detail?: string }
      detail = body.detail || detail
    } catch {
      // Keep the plain-language fallback when the server returns no JSON.
    }
    throw new ApiError(detail, response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const caseUrl = (caseId: string, suffix = '') =>
  `/api/cases/${encodeURIComponent(caseId)}${suffix}`

export const getCases = (officer: string) =>
  request<CaseSummary[]>(`/api/cases?officer=${encodeURIComponent(officer)}`)

export const createCase = (input: NewCaseInput) =>
  request<CaseSummary>('/api/cases', { method: 'POST', body: JSON.stringify(input) })

export const renameCase = (caseId: string, title: string) =>
  request<CaseSummary>(caseUrl(caseId), {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })

export const deleteCase = (caseId: string) =>
  request<{ deleted: string }>(
    caseUrl(caseId, `?confirm=${encodeURIComponent(caseId)}`),
    { method: 'DELETE' },
  )

// ------------------------------------------------------------- conversation

/** The thread lives on the case, so it is fetched, not remembered by this tab.
 *  Reload, another machine, a colleague — same conversation. */
export const getConversation = (caseId: string) =>
  request<{ turns: ConversationTurn[] }>(caseUrl(caseId, '/conversation'))

export const clearConversation = (caseId: string) =>
  request<{ cleared: number }>(
    caseUrl(caseId, `/conversation?confirm=${encodeURIComponent(caseId)}`),
    { method: 'DELETE' },
  )

export const askCase = (caseId: string, question: string, actor: string) =>
  request<AgentAnswer>(caseUrl(caseId, '/ask'), {
    method: 'POST',
    body: JSON.stringify({ question, actor }),
  })

export const getBrief = (caseId: string) => request<CaseBrief>(caseUrl(caseId, '/brief'))

// -------------------------------------------------------------- the evidence

export const getGraph = (caseId: string, includeDocuments = false) =>
  request<CaseGraph>(
    caseUrl(caseId, `/graph?include_documents=${includeDocuments ? 'true' : 'false'}`),
  )

export const getNode = (caseId: string, nodeId: string) =>
  request<NodeProfile>(caseUrl(caseId, `/nodes/${encodeURIComponent(nodeId)}`))

/** What the agent has concluded and what it is holding open. This is the case's,
 *  not the conversation's — it survives the thread being cleared (§2.5). */
export const getMemory = (caseId: string, kind?: string) =>
  request<MemoryEntry[]>(caseUrl(caseId, kind ? `/memory?kind=${kind}` : '/memory'))

export function getSource(caseId: string, docId: string, start?: number, end?: number) {
  const query = new URLSearchParams({ doc_id: docId })
  if (start !== undefined) query.set('start', String(start))
  if (end !== undefined) query.set('end', String(end))
  return request<SourceExcerpt>(caseUrl(caseId, `/source?${query}`))
}

/** Upload reports progress, because a scanned FIR is a slow thing to hand over
 *  and silence during it reads as a broken button. */
export function uploadDocument(
  caseId: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}${caseUrl(caseId, '/documents')}`)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        body = null
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as UploadResponse)
        return
      }
      const detail =
        (body as { detail?: string } | null)?.detail ||
        'That file could not be added to the case.'
      reject(new ApiError(detail, xhr.status))
    }
    xhr.onerror = () => reject(new ApiError('The case service could not be reached.', 0))
    xhr.send(form)
  })
}
