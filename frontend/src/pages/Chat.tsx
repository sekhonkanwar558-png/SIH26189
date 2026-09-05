import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUp, Check, Copy, Paperclip, Plus, Share2, Square, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { GraphPanel } from '../components/GraphPanel'
import { activeOfficer } from '../config'
import {
  ApiError,
  askCase,
  createCase,
  deleteCase,
  getBrief,
  getCases,
  getConversation,
  getGraph,
  isAssistantDown,
  renameCase,
  uploadDocument,
} from '../lib/api'
import type { AgentAnswer, ConversationTurn } from '../types'

/**
 * shikonye — the whole product.
 *
 * One conversation per case, and a graph when an answer has a route to show.
 * There are no sections, no panels and no commands (D25, D26): everything an
 * officer wants, he gets by typing a sentence, because the officer is not
 * technical and a second thing to learn is a second thing to get wrong.
 *
 * The depth is all behind this file — the per-case graph, the tool loop, the
 * citation check, the hash-chained custody log. None of it is a control here,
 * and that is the point.
 */

const RAIL = 260

/** A case needs an id before it has a name, and the officer should not be asked
 *  to invent either. He gets a case; it names itself from the first thing he
 *  says to it. */
const UNNAMED = 'New case'

const newCaseId = () =>
  `case-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`

/** The rail label, taken from his own words rather than a form he had to fill. */
function titleFrom(question: string) {
  const line = question.trim().replace(/\s+/g, ' ')
  if (line.length <= 48) return line
  return `${line.slice(0, 47).trimEnd()}…`
}

// ---------------------------------------------------------------- primitives

const softButton =
  'inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[12px] text-muted ' +
  'transition hover:bg-raised hover:text-ink'

function Thinking() {
  return (
    <div className="flex items-center gap-1.5 py-1" aria-label="shikonye is working">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="thinking-dot inline-block h-1.5 w-1.5 rounded-full bg-subtle"
          style={{ animationDelay: `${i * 160}ms` }}
        />
      ))}
    </div>
  )
}

// -------------------------------------------------------------------- answer

function Answer({
  answer,
  onShowPath,
  pathShown,
}: {
  answer: AgentAnswer
  onShowPath: (path: string[]) => void
  pathShown: boolean
}) {
  const [copied, setCopied] = useState(false)

  // A verification that ran and failed is shown loudly. A missing block means
  // none ran, which is not the same thing.
  const failed = answer.verified ? !answer.verified.ok : false
  const path = answer.highlight_path ?? []

  async function copy() {
    try {
      await navigator.clipboard.writeText(answer.answer)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard can be refused; the text is still selectable */
    }
  }

  return (
    <div className="group">
      <div className="whitespace-pre-wrap text-[15px] leading-7 text-ink">
        {answer.answer}
      </div>

      {failed && (
        <p className="mt-3 rounded-xl border border-[#f0dcdc] bg-danger-soft px-3 py-2 text-[13px] text-danger">
          This rests on something that is not in the case. Do not rely on it
          without checking it yourself.
        </p>
      )}

      {answer.caveats?.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {answer.caveats.map((caveat) => (
            <li key={caveat} className="text-[13px] leading-6 text-muted">
              {caveat}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-2 flex items-center gap-1 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
        <button type="button" className={softButton} onClick={() => void copy()}>
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
        {path.length > 0 && (
          <button
            type="button"
            className={softButton}
            onClick={() => onShowPath(path)}
          >
            <Share2 size={13} />
            {pathShown ? 'Showing on the graph' : 'Show on the graph'}
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------- page

export function Chat() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const client = useQueryClient()

  const [draft, setDraft] = useState('')
  const [path, setPath] = useState<string[] | null>(null)
  const [uploading, setUploading] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const fileInput = useRef<HTMLInputElement | null>(null)
  const bottom = useRef<HTMLDivElement | null>(null)
  const composer = useRef<HTMLTextAreaElement | null>(null)

  const cases = useQuery({
    queryKey: ['cases'],
    queryFn: () => getCases(activeOfficer.id),
  })

  const conversation = useQuery({
    queryKey: ['conversation', caseId],
    queryFn: () => getConversation(caseId as string),
    enabled: Boolean(caseId),
  })

  const graph = useQuery({
    queryKey: ['graph', caseId],
    queryFn: () => getGraph(caseId as string, true),
    enabled: Boolean(caseId) && path !== null,
  })

  // The opening brief is the assistant speaking first. It writes itself into the
  // thread server-side and will not greet him twice for the same thing, so this
  // is fire-and-refetch rather than something rendered on its own.
  const brief = useQuery({
    queryKey: ['brief', caseId],
    queryFn: () => getBrief(caseId as string),
    enabled: Boolean(caseId),
    retry: false,
  })

  useEffect(() => {
    if (brief.data) void client.invalidateQueries({ queryKey: ['conversation', caseId] })
  }, [brief.data, caseId, client])

  const turns = useMemo<ConversationTurn[]>(
    () => conversation.data?.turns ?? [],
    [conversation.data],
  )

  const ask = useMutation({
    mutationFn: (question: string) =>
      askCase(caseId as string, question, activeOfficer.id),
    onSuccess: (answer) => {
      void client.invalidateQueries({ queryKey: ['conversation', caseId] })
      void client.invalidateQueries({ queryKey: ['cases'] })
      if (answer.highlight_path?.length) setPath(answer.highlight_path)
    },
    onError: (error) => {
      // His message is already on the case — `ask` records the question before
      // it calls the model — so show it. A question that vanishes when the
      // answer fails reads as "it didn't hear me", and he retypes it.
      void client.invalidateQueries({ queryKey: ['conversation', caseId] })
      setNotice(
        isAssistantDown(error)
          ? 'shikonye is not reachable right now. The case is untouched — try again in a moment.'
          : error instanceof ApiError
            ? error.message
            : 'That did not go through.',
      )
    },
  })

  const start = useMutation({
    mutationFn: () =>
      createCase({
        case_id: newCaseId(),
        title: UNNAMED,
        officer: activeOfficer.id,
        case_type: '',
        brief: '',
      }),
    onSuccess: (created) => {
      void client.invalidateQueries({ queryKey: ['cases'] })
      navigate(`/c/${encodeURIComponent(created.case_id)}`)
    },
  })

  const drop = useMutation({
    mutationFn: (id: string) => deleteCase(id),
    onSuccess: (_result, id) => {
      void client.invalidateQueries({ queryKey: ['cases'] })
      if (id === caseId) navigate('/')
    },
  })

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns.length, ask.isPending])

  useEffect(() => {
    setPath(null)
    setNotice(null)
  }, [caseId])

  const send = useCallback(() => {
    const question = draft.trim()
    if (!question || !caseId || ask.isPending) return
    setDraft('')
    setNotice(null)

    // First thing said in an unnamed case becomes its name, so the rail reads
    // like his own notes and he never fills in a title field.
    const open = (cases.data ?? []).find((item) => item.case_id === caseId)
    if (open && open.title === UNNAMED) {
      void renameCase(caseId, titleFrom(question))
        .then(() => client.invalidateQueries({ queryKey: ['cases'] }))
        .catch(() => undefined)
    }

    ask.mutate(question)
  }, [draft, caseId, ask, cases.data, client])

  async function attach(file: File) {
    if (!caseId) return
    setUploading(file.name)
    setNotice(null)
    try {
      const result = await uploadDocument(caseId, file)
      void client.invalidateQueries({ queryKey: ['cases'] })
      void client.invalidateQueries({ queryKey: ['graph', caseId] })
      const warnings = result.document.warnings ?? []
      setNotice(
        warnings.length > 0
          ? warnings.join(' ')
          : `${file.name} is in the case — ${result.document.entities.length} entities read from it.`,
      )
      // Something new arrived, so it may have something to say about it.
      void client.invalidateQueries({ queryKey: ['brief', caseId] })
    } catch (error) {
      setNotice(
        error instanceof ApiError ? error.message : 'That file could not be added.',
      )
    } finally {
      setUploading(null)
    }
  }

  const empty = turns.length === 0 && !ask.isPending && !brief.isLoading

  return (
    <div className="flex h-full bg-canvas">
      {/* ------------------------------------------------------------ rail */}
      <nav
        className="hidden shrink-0 flex-col border-r border-line bg-rail md:flex"
        style={{ width: RAIL }}
        aria-label="Cases"
      >
        <div className="px-3 py-4">
          <p className="px-2 pb-3 text-[15px] lowercase tracking-tight text-ink">
            shikonye
          </p>
          <button
            type="button"
            onClick={() => start.mutate()}
            className="flex w-full items-center gap-2 rounded-xl px-2 py-2 text-[13px] text-ink transition hover:bg-raised"
          >
            <Plus size={15} />
            New case
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {(cases.data ?? []).map((item) => {
            const active = item.case_id === caseId
            return (
              <div key={item.case_id} className="group/rail relative">
                <button
                  type="button"
                  onClick={() => navigate(`/c/${encodeURIComponent(item.case_id)}`)}
                  className={`w-full truncate rounded-xl py-2 pl-2 pr-8 text-left text-[13px] transition ${
                    active ? 'bg-raised text-ink' : 'text-muted hover:bg-raised hover:text-ink'
                  }`}
                  title={item.title}
                >
                  {item.title}
                </button>
                <button
                  type="button"
                  aria-label={`Delete ${item.title}`}
                  onClick={() => drop.mutate(item.case_id)}
                  className="absolute right-1 top-1.5 rounded-lg p-1.5 text-subtle opacity-0 transition hover:text-danger group-hover/rail:opacity-100"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            )
          })}
        </div>
      </nav>

      {/* ------------------------------------------------------------ chat */}
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[46rem] px-5 py-10">
            {empty && (
              <div className="pt-24 text-center">
                <p className="text-[22px] lowercase tracking-tight text-ink">shikonye</p>
                <p className="mx-auto mt-3 max-w-md text-[14px] leading-6 text-muted">
                  Hand it the case file. Ask it anything about what is in there.
                </p>
              </div>
            )}

            <div className="space-y-8">
              {turns.map((turn) => {
                if (turn.role === 'officer') {
                  return (
                    <div key={turn.seq} className="flex justify-end">
                      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-raised px-4 py-2.5 text-[15px] leading-7 text-ink">
                        {turn.text}
                      </div>
                    </div>
                  )
                }
                const answer = turn.answer as AgentAnswer
                return (
                  <div key={turn.seq} className="rise">
                    {answer?.answer ? (
                      <Answer
                        answer={answer}
                        pathShown={
                          path !== null &&
                          path.join('|') === (answer.highlight_path ?? []).join('|')
                        }
                        onShowPath={setPath}
                      />
                    ) : (
                      <div className="whitespace-pre-wrap text-[15px] leading-7 text-ink">
                        {turn.text}
                      </div>
                    )}
                  </div>
                )
              })}

              {(ask.isPending || brief.isLoading) && <Thinking />}
            </div>

            <div ref={bottom} />
          </div>
        </div>

        {/* ------------------------------------------------------- composer */}
        <div className="shrink-0 px-5 pb-6">
          <div className="mx-auto w-full max-w-[46rem]">
            {notice && (
              <p className="mb-2 px-2 text-[13px] leading-6 text-muted">{notice}</p>
            )}
            {uploading && (
              <p className="mb-2 px-2 text-[13px] text-muted">Reading {uploading}…</p>
            )}

            <div className="flex items-end gap-2 rounded-[26px] border border-line-strong bg-canvas px-3 py-2 shadow-[0_2px_10px_rgba(13,13,13,0.04)] transition focus-within:border-ink/25">
              <button
                type="button"
                aria-label="Add a document to this case"
                onClick={() => fileInput.current?.click()}
                disabled={!caseId}
                className="rounded-full p-2 text-muted transition hover:bg-raised hover:text-ink disabled:opacity-40"
              >
                <Paperclip size={17} />
              </button>
              <input
                ref={fileInput}
                type="file"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  if (file) void attach(file)
                  event.target.value = ''
                }}
              />

              <textarea
                ref={composer}
                rows={1}
                value={draft}
                disabled={!caseId}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    send()
                  }
                }}
                placeholder={caseId ? 'Ask anything about this case' : 'Open a case to begin'}
                className="max-h-48 min-h-[28px] flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-7 text-ink outline-none placeholder:text-subtle"
              />

              <button
                type="button"
                onClick={send}
                disabled={!draft.trim() || ask.isPending || !caseId}
                aria-label="Send"
                className="rounded-full bg-ink p-2 text-white transition disabled:bg-line-strong disabled:text-subtle"
              >
                {ask.isPending ? <Square size={15} /> : <ArrowUp size={15} />}
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* ----------------------------------------------------------- graph */}
      {path !== null && graph.data && (
        <div className="hidden w-[38%] min-w-[320px] lg:block">
          <GraphPanel graph={graph.data} path={path} onClose={() => setPath(null)} />
        </div>
      )}
    </div>
  )
}
