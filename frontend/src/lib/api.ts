import type {
  Analytics,
  CaseBrief,
  CaseDetail,
  CaseDocument,
  CaseGraph,
  CaseSummary,
  CustodyLog,
  HealthReport,
  MemoryEntry,
  NewCaseInput,
  NodeProfile,
  PathResult,
  SourceExcerpt,
  UploadResponse,
  AgentAnswer,
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

export function getCases(officer: string) {
  return request<CaseSummary[]>(`/api/cases?officer=${encodeURIComponent(officer)}`)
}

export function createCase(input: NewCaseInput) {
  return request<CaseSummary>('/api/cases', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateCase(
  caseId: string,
  updates: Partial<Pick<CaseSummary, 'title' | 'case_type' | 'brief' | 'status'>>,
) {
  return request<CaseSummary>(`/api/cases/${encodeURIComponent(caseId)}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export function deleteCase(caseId: string) {
  return request<void>(
    `/api/cases/${encodeURIComponent(caseId)}?confirm=${encodeURIComponent(caseId)}`,
    { method: 'DELETE' },
  )
}

// ----------------------------------------------------------- case workspace
// One function per §5.6 endpoint. Nothing here reshapes a response: the screens
// consume the contract directly, so a drift between the two shows up as a type
// error rather than as a quietly wrong panel.

const caseUrl = (caseId: string, suffix = '') =>
  `/api/cases/${encodeURIComponent(caseId)}${suffix}`

export function getHealth() {
  return request<HealthReport>('/api/health')
}

export function getCase(caseId: string) {
  return request<CaseDetail>(caseUrl(caseId))
}

export function getGraph(caseId: string, includeDocuments = false) {
  return request<CaseGraph>(
    caseUrl(caseId, `/graph?include_documents=${includeDocuments}`),
  )
}

export function getNode(caseId: string, nodeId: string) {
  // The node id carries its own colon and the route is a :path, so the prefix
  // must survive encoding — encodeURIComponent would turn `person:x` into
  // `person%3Ax` and the lookup would miss.
  return request<NodeProfile>(
    caseUrl(caseId, `/nodes/${nodeId.split('/').map(encodeURIComponent).join('/')}`),
  )
}

export function getPath(caseId: string, a: string, b: string, maxHops = 6) {
  const query = new URLSearchParams({ a, b, max_hops: String(maxHops) })
  return request<PathResult[]>(caseUrl(caseId, `/path?${query}`))
}

export function getAnalytics(caseId: string, metric = 'betweenness', limit = 10) {
  const query = new URLSearchParams({ metric, limit: String(limit) })
  return request<Analytics>(caseUrl(caseId, `/analytics?${query}`))
}

export function getDocuments(caseId: string) {
  return request<CaseDocument[]>(caseUrl(caseId, '/documents'))
}

export function getSource(caseId: string, docId: string, start?: number, end?: number) {
  const query = new URLSearchParams({ doc_id: docId })
  if (start !== undefined) query.set('start', String(start))
  if (end !== undefined) query.set('end', String(end))
  return request<SourceExcerpt>(caseUrl(caseId, `/source?${query}`))
}

export function getBrief(caseId: string) {
  return request<CaseBrief>(caseUrl(caseId, '/brief'))
}

export function askCase(caseId: string, question: string, actor: string) {
  return request<AgentAnswer>(caseUrl(caseId, '/ask'), {
    method: 'POST',
    body: JSON.stringify({ question, actor }),
  })
}

export function investigateFinding(caseId: string, findingId: string) {
  return request<AgentAnswer>(
    caseUrl(caseId, `/findings/${encodeURIComponent(findingId)}/investigate`),
    { method: 'POST' },
  )
}

export function getMemory(caseId: string, kind?: string, status?: string) {
  const query = new URLSearchParams()
  if (kind) query.set('kind', kind)
  if (status) query.set('status', status)
  const suffix = query.toString() ? `/memory?${query}` : '/memory'
  return request<MemoryEntry[]>(caseUrl(caseId, suffix))
}

export function closeMemory(caseId: string, memId: string, status = 'resolved') {
  return request<MemoryEntry>(
    caseUrl(caseId, `/memory/${encodeURIComponent(memId)}/close?status=${status}`),
    { method: 'POST' },
  )
}

export function getCustody(caseId: string, limit?: number) {
  const suffix = limit ? `/custody?limit=${limit}` : '/custody'
  return request<CustodyLog>(caseUrl(caseId, suffix))
}

export function uploadDocument(
  caseId: string,
  file: File,
  kind: string | undefined,
  actor: string,
  onProgress?: (percent: number) => void,
) {
  const query = new URLSearchParams({ actor })
  if (kind) query.set('kind', kind)
  const url = `${API_BASE}${caseUrl(caseId, `/documents?${query}`)}`

  // XHR rather than fetch: an officer uploading a 40-page scan needs to see it
  // moving, and fetch still cannot report upload progress.
  return new Promise<UploadResponse>((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText) as unknown
      } catch {
        // A non-JSON body is handled by the status check below.
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100)
        resolve(body as UploadResponse)
        return
      }
      const detail =
        (body as { detail?: string } | null)?.detail ||
        'This document could not be added to the case.'
      reject(new ApiError(detail, xhr.status))
    }
    xhr.onerror = () =>
      reject(new ApiError('The case service could not be reached.', 0))
    xhr.send(form)
  })
}

