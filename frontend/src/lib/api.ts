import type { CaseSummary, NewCaseInput } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
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
