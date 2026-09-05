import { useCallback, useEffect, useRef, useState } from 'react'
import type { AgentAnswer, CaseBrief, IngestResult } from '../types'

/**
 * The conversation an officer has with this case's agent.
 *
 * It lives in the client because the backend has no transcript endpoint — what
 * it keeps is the agent's own memory (§5.2 act tools), which is a different
 * thing: conclusions worth recalling next month, not chat. The transcript is
 * kept per case on this device so a reload in the middle of a briefing does not
 * lose the thread.
 */

export type Message =
  | { id: string; role: 'officer'; ts: string; text: string; attachments: string[] }
  | { id: string; role: 'shikonye'; ts: string; kind: 'brief'; brief: CaseBrief }
  | {
      id: string
      role: 'shikonye'
      ts: string
      kind: 'answer'
      question: string
      answer: AgentAnswer
    }
  | {
      id: string
      role: 'shikonye'
      ts: string
      kind: 'upload'
      filename: string
      result: IngestResult
    }
  | {
      id: string
      role: 'shikonye'
      ts: string
      kind: 'notice'
      text: string
      tone: 'info' | 'error'
    }

const STORAGE_KEY = 'caselens.conversation'
/** Enough to scroll back through a working session, bounded so storage cannot
 *  grow without limit on a long-running case. */
const MAX_KEPT = 80

function storageKey(caseId: string) {
  return `${STORAGE_KEY}.${caseId}`
}

function load(caseId: string): Message[] {
  try {
    const raw = window.localStorage.getItem(storageKey(caseId))
    return raw ? (JSON.parse(raw) as Message[]) : []
  } catch {
    return []
  }
}

function newId() {
  return `m${Date.now()}${Math.random().toString(36).slice(2, 7)}`
}

/**
 * `Omit` collapses a union into its shared keys, which would let a brief be
 * pushed with an answer's fields. Distributing over the union keeps each
 * message shape intact.
 */
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never
type NewMessage = DistributiveOmit<Message, 'id' | 'ts'>

export function useConversation(caseId: string) {
  const [messages, setMessages] = useState<Message[]>(() => load(caseId))
  const caseRef = useRef(caseId)

  // Switching case switches transcript — two cases never share one (§2.4).
  useEffect(() => {
    if (caseRef.current !== caseId) {
      caseRef.current = caseId
      setMessages(load(caseId))
    }
  }, [caseId])

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey(caseId), JSON.stringify(messages.slice(-MAX_KEPT)))
    } catch {
      // A full or disabled store costs the officer their scrollback on reload,
      // nothing more — the case itself is on the server.
    }
  }, [caseId, messages])

  const push = useCallback((message: NewMessage) => {
    const complete = { id: newId(), ts: new Date().toISOString(), ...message } as Message
    setMessages((current) => [...current, complete])
    return complete.id
  }, [])

  const pushOfficer = useCallback(
    (text: string, attachments: string[] = []) =>
      push({ role: 'officer', text, attachments }),
    [push],
  )

  const pushAnswer = useCallback(
    (question: string, answer: AgentAnswer) =>
      push({ role: 'shikonye', kind: 'answer', question, answer }),
    [push],
  )

  const pushBrief = useCallback(
    (brief: CaseBrief) => push({ role: 'shikonye', kind: 'brief', brief }),
    [push],
  )

  const pushUpload = useCallback(
    (filename: string, result: IngestResult) =>
      push({ role: 'shikonye', kind: 'upload', filename, result }),
    [push],
  )

  const pushNotice = useCallback(
    (text: string, tone: 'info' | 'error' = 'info') =>
      push({ role: 'shikonye', kind: 'notice', text, tone }),
    [push],
  )

  const clear = useCallback(() => {
    setMessages([])
    try {
      window.localStorage.removeItem(storageKey(caseId))
    } catch {
      // Nothing to clear when storage is unavailable.
    }
  }, [caseId])

  const hasBrief = messages.some(
    (message) => message.role === 'shikonye' && message.kind === 'brief',
  )

  return { messages, pushOfficer, pushAnswer, pushBrief, pushUpload, pushNotice, clear, hasBrief }
}

export type Conversation = ReturnType<typeof useConversation>
