import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUp, Check, Copy, Paperclip, Plus, Share2, Trash2, Waypoints } from 'lucide-react'
import type { CSSProperties } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Brain } from '../components/Brain'
import { Evidence } from '../components/Evidence'
import { activeOfficer } from '../config'
import {
  ApiError,
  askCase,
  clearConversation,
  createCase,
  deleteCase,
  getHealth,
  getCases,
  getConversation,
  getGraph,
  isAssistantDown,
  renameCase,
  uploadDocument,
} from '../lib/api'
import type { AgentAnswer, CaseCounts, ConversationTurn } from '../types'

/**
 * Suishōdama — the whole product.
 *
 * One conversation per case, and the case's brain when there is something to
 * look at. There are no sections, no panels and no commands (D25, D26):
 * everything an officer wants, he gets by typing a sentence, because the
 * officer is not technical and a second thing to learn is a second thing to get
 * wrong.
 *
 * **What is behind this file is not a context window** (§2.5, D29). Every case
 * has a brain on disk — its graph, its analytics, its memory, its hash-chained
 * custody log — and the assistant queries it with tools rather than holding the
 * documents in a prompt. That is why the one number on screen is what the brain
 * holds, and why it is worth watching it change.
 */

const RAIL = 260

/** A case needs an id before it has a name, and the officer should not be asked
 *  to invent either. He gets a case; it names itself from the first thing he
 *  says to it. */
const UNNAMED = 'New case'

/** Three openings, for a man who has just been handed a product with no menus.
 *  With no panels to explore, the empty screen is the only place discoverability
 *  can live — and each of these is a real question the case can answer. */
const OPENERS = [
  'What is this case about?',
  'Who matters most here?',
  "What have you found that I haven't asked about?",
]

const newCaseId = () =>
  `case-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`

/** The rail label, taken from his own words rather than a form he had to fill. */
function titleFrom(question: string) {
  const line = question.trim().replace(/\s+/g, ' ')
  if (line.length <= 48) return line
  return `${line.slice(0, 47).trimEnd()}…`
}

const count = (n: number, one: string, many = `${one}s`) =>
  `${n.toLocaleString()} ${n === 1 ? one : many}`

/** `counts.nodes` includes the document nodes — each file is a node so
 *  `MENTIONED_IN` has somewhere to point (§5.1). The officer is told how many
 *  *entities* an upload read, so the line beside it must count the same things,
 *  or a judge who adds them up finds one that does not exist. */
const entitiesIn = (counts: CaseCounts) => counts.nodes - counts.documents

// ---------------------------------------------------------------- primitives

const softButton =
  'inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[12px] text-muted ' +
  'transition hover:bg-raised hover:text-ink'

function Thinking() {
  return (
    <div className="flex items-center gap-1.5 py-1" aria-label="Suishōdama is working">
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
  caseId,
  answer,
  onShow,
  shown,
}: {
  caseId: string
  answer: AgentAnswer
  onShow: (ids: string[], ordered: boolean) => void
  shown: boolean
}) {
  const [copied, setCopied] = useState(false)

  // A verification that ran and failed is shown loudly. A missing block means
  // none ran, which is not the same thing.
  const failed = answer.verified ? !answer.verified.ok : false
  const path = answer.highlight_path ?? []
  const cited = answer.cited_nodes ?? []
  // A route if there is one; otherwise the entities it rested on, which light
  // as a set and never as a journey (D23).
  const lit = path.length > 0 ? path : cited
  const ordered = path.length > 0

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
      <div className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{answer.answer}</div>

      {failed && (
        <p className="mt-3 rounded-xl border border-[#f0dcdc] bg-danger-soft px-3 py-2 text-[13px] text-danger">
          This rests on something that is not in the case. Do not rely on it without
          checking it yourself.
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

      <Evidence caseId={caseId} answer={answer} />

      <div className="mt-2 flex items-center gap-1 opacity-0 transition group-hover:opacity-100 focus-within:opacity-100">
        <button type="button" className={softButton} onClick={() => void copy()}>
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
        {lit.length > 0 && (
          <button type="button" className={softButton} onClick={() => onShow(lit, ordered)}>
            <Share2 size={13} />
            {shown
              ? 'Showing on the brain'
              : ordered
                ? 'Show the route'
                : 'Show it on the brain'}
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------- page

/**
 * Remount on the case, rather than reset on it.
 *
 * Everything below is about *this* case — what the brain panel is showing, the
 * last upload, a delete waiting for its second click. Clearing that in an
 * effect leaves one render in which the old case's state is on the new case's
 * screen; keying it is the same intent with no window for it to be wrong in.
 */
export function Chat() {
  const { caseId } = useParams<{ caseId: string }>()
  return <CaseChat key={caseId ?? 'none'} caseId={caseId} />
}

function CaseChat({ caseId }: { caseId: string | undefined }) {
  const navigate = useNavigate()
  const client = useQueryClient()

  const [draft, setDraft] = useState('')
  /** What the brain panel is showing: a route, a cited set, or the brain itself
   *  (`ids: []`). `null` is closed. */
  const [lit, setLit] = useState<{ ids: string[]; ordered: boolean } | null>(null)
  const [uploading, setUploading] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  /** What the last document added to the brain. This is the product's argument
   *  in one line, so it is said in the moment it becomes true. */
  const [grew, setGrew] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [confirmDrop, setConfirmDrop] = useState<string | null>(null)

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
    enabled: Boolean(caseId) && lit !== null,
  })

  // Nothing here speaks on its own. The opening briefing used to run `/brief` —
  // a full model call — the moment a case was opened, and again whenever it was
  // refetched: answering a question records conclusions, new conclusions make
  // new findings, and the next refetch saw fresh ones and ran the model again.
  // Two typed questions produced five billed calls that way, three of them
  // unprompted and one of them returning nothing usable. Kanwar's call, 09-06:
  // the officer asks, and it answers — he can ask for a briefing like anything
  // else, by typing a sentence. `/brief` still exists on the API; the interface
  // no longer fires it.
  //
  // This replaces the briefing's other job. It used to be how the screen learned
  // the assistant was unreachable — by making a paid call and watching it fail.
  // `/api/health` says the same thing for nothing.
  const health = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    retry: false,
    staleTime: 30_000,
  })

  const turns = useMemo<ConversationTurn[]>(
    () => conversation.data?.turns ?? [],
    [conversation.data],
  )

  const openCase = (cases.data ?? []).find((item) => item.case_id === caseId)
  const counts: CaseCounts | undefined = openCase?.counts

  const ask = useMutation({
    mutationFn: (question: string) => askCase(caseId as string, question, activeOfficer.id),
    // His own words go on screen the instant he presses send. The server records
    // the question before it calls the model, so this is the real turn shown
    // early rather than a hopeful placeholder — but the answer takes the better
    // part of a minute, and for all of it the thread used to look exactly as it
    // did before he typed. An officer reads that as "it didn't hear me" and
    // sends it again, which costs a second run of the whole tool loop.
    onMutate: async (question: string) => {
      await client.cancelQueries({ queryKey: ['conversation', caseId] })
      const previous = client.getQueryData<{ turns: ConversationTurn[] }>([
        'conversation',
        caseId,
      ])
      const turns = previous?.turns ?? []
      const pending: ConversationTurn = {
        seq: (turns[turns.length - 1]?.seq ?? 0) + 1,
        role: 'officer',
        actor: activeOfficer.id,
        text: question,
        answer: {},
        node_ids: [],
        ts: new Date().toISOString(),
        graph_rev: 0,
      }
      client.setQueryData(['conversation', caseId], { turns: [...turns, pending] })
      return { previous }
    },
    onSuccess: (answer) => {
      void client.invalidateQueries({ queryKey: ['conversation', caseId] })
      void client.invalidateQueries({ queryKey: ['cases'] })
      const path = answer.highlight_path ?? []
      if (path.length > 0) setLit({ ids: path, ordered: true })
    },
    onError: (error) => {
      // His message is already on the case — `ask` records the question before
      // it calls the model — so show it. A question that vanishes when the
      // answer fails reads as "it didn't hear me", and he retypes it.
      void client.invalidateQueries({ queryKey: ['conversation', caseId] })
      setNotice(
        isAssistantDown(error)
          ? 'Suishōdama is not reachable right now. The case and everything in it are untouched — try again in a moment.'
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
      setConfirmDrop(null)
      void client.invalidateQueries({ queryKey: ['cases'] })
      if (id === caseId) navigate('/')
    },
  })

  const wipe = useMutation({
    mutationFn: () => clearConversation(caseId as string),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['conversation', caseId] })
      setNotice('The thread is cleared. The case keeps everything it has learned.')
    },
  })

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns.length, ask.isPending])

  // Escape closes the brain. Anything that opens over the conversation should
  // close the way everything else on a desktop closes, without him having to
  // find the control that opened it.
  useEffect(() => {
    if (lit === null) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setLit(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [lit])

  const send = useCallback(
    (text?: string) => {
      const question = (text ?? draft).trim()
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
    },
    [draft, caseId, ask, cases.data, client],
  )

  const attach = useCallback(
    async function attach(file: File) {
      if (!caseId) return
      const before = counts
      setUploading(file.name)
      setNotice(null)
      try {
        const result = await uploadDocument(caseId, file)
        void client.invalidateQueries({ queryKey: ['cases'] })
        void client.invalidateQueries({ queryKey: ['graph', caseId] })

        const warnings = result.document.warnings ?? []
        if (warnings.length > 0) {
          setNotice(warnings.join(' '))
          setGrew(null)
        } else {
          // What it *learned*, not what was uploaded. A file that arrives and
          // teaches the case nothing is the failure D18 exists to catch, and
          // saying "+0 entities" out loud is how an officer finds out.
          const nodes = entitiesIn(result.counts) - (before ? entitiesIn(before) : 0)
          const edges = result.counts.edges - (before?.edges ?? 0)
          setNotice(null)
          setGrew(
            `${file.name} — the brain grew by ${count(nodes, 'entity', 'entities')} and ${count(edges, 'link')}.`,
          )
        }
      } catch (error) {
        setNotice(error instanceof ApiError ? error.message : 'That file could not be added.')
      } finally {
        setUploading(null)
      }
    },
    [caseId, counts, client],
  )

  const empty = turns.length === 0 && !ask.isPending
  // With no assistant there is no product (D22), so he should learn that before
  // he has composed a sentence rather than after. `model_available` only reports
  // that a key is configured — a revoked key or a dead network still reads as
  // fine here and surfaces on the first question instead, which is the price of
  // not paying for a model call to find out.
  const assistantDown = health.data ? !health.data.model_available : false

  return (
    <div
      className="relative flex h-full bg-canvas"
      onDragOver={(event) => {
        if (!caseId) return
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={(event) => {
        if (event.currentTarget === event.target) setDragging(false)
      }}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        const file = event.dataTransfer.files?.[0]
        if (file) void attach(file)
      }}
    >
      {/* ------------------------------------------------------------ rail */}
      <nav
        className="hidden shrink-0 flex-col border-r border-line bg-rail md:flex"
        style={{ width: RAIL }}
        aria-label="Cases"
      >
        <div className="px-3 pb-3 pt-5">
          <div className="flex items-center gap-2 px-2 pb-5">
            <span
              aria-hidden
              className="inline-block h-[7px] w-[7px] rounded-full bg-evidence"
            />
            <p className="text-[15px] font-medium tracking-[-0.01em] text-ink">
              Suishōdama
            </p>
          </div>
          <button
            type="button"
            onClick={() => start.mutate()}
            className="flex w-full items-center gap-2 rounded-xl border border-line bg-canvas px-2.5 py-2 text-[13px] font-medium text-ink shadow-[0_1px_2px_rgba(13,13,13,0.04)] transition hover:border-line-strong hover:shadow-[0_2px_6px_rgba(13,13,13,0.06)] active:scale-[0.99]"
          >
            <Plus size={15} className="text-subtle" />
            New case
          </button>
        </div>

        <p className="px-5 pb-1.5 text-[11px] font-medium uppercase tracking-[0.07em] text-subtle">
          Cases
        </p>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {(cases.data ?? []).map((item) => {
            const active = item.case_id === caseId
            const confirming = confirmDrop === item.case_id
            return (
              <div key={item.case_id} className="group/rail relative">
                <button
                  type="button"
                  onClick={() => navigate(`/c/${encodeURIComponent(item.case_id)}`)}
                  className={`relative w-full truncate rounded-xl py-[7px] pl-2.5 pr-8 text-left text-[13px] transition ${
                    active
                      ? 'bg-raised font-medium text-ink'
                      : 'text-muted hover:bg-raised/70 hover:text-ink'
                  }`}
                  title={item.title}
                >
                  {item.title}
                </button>
                {confirming ? (
                  <button
                    type="button"
                    onClick={() => drop.mutate(item.case_id)}
                    onBlur={() => setConfirmDrop(null)}
                    autoFocus
                    className="absolute right-1 top-1.5 rounded-lg px-1.5 py-0.5 text-[11px] text-danger transition hover:bg-danger-soft"
                  >
                    Delete?
                  </button>
                ) : (
                  <button
                    type="button"
                    aria-label={`Delete ${item.title}`}
                    // Two clicks, because this destroys a case's whole brain —
                    // the graph, the memory and the custody chain with it.
                    onClick={() => setConfirmDrop(item.case_id)}
                    className="absolute right-1 top-1.5 rounded-lg p-1.5 text-subtle opacity-0 transition hover:text-danger group-hover/rail:opacity-100"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            )
          })}
        </div>

        {caseId && turns.length > 0 && (
          <div className="shrink-0 px-3 pb-4">
            <button
              type="button"
              onClick={() => wipe.mutate()}
              className="w-full rounded-xl px-2 py-2 text-left text-[12px] text-subtle transition hover:bg-raised hover:text-muted"
              title="The case keeps its graph, its findings and its custody chain. Only the thread goes."
            >
              Clear this thread
            </button>
          </div>
        )}
      </nav>

      {/* ------------------------------------------------------------ chat */}
      <main className="flex min-w-0 flex-1 flex-col">
        {/* The one control above the conversation. The brain used to be
            reachable only by pressing the line under the composer or an
            answer's own "show it on the brain" — both of which require
            something to have happened first. An officer who has just opened a
            case and wants to *look* at it had nowhere to press. */}
        {caseId && (
          <header className="flex shrink-0 items-center gap-3 px-4 pb-1 pt-3">
            <p className="min-w-0 flex-1 truncate text-[13px] text-muted">
              {openCase && openCase.title !== UNNAMED ? openCase.title : ''}
            </p>
            <button
              type="button"
              onClick={() => setLit((was) => (was === null ? { ids: [], ordered: false } : null))}
              aria-pressed={lit !== null}
              title={lit !== null ? 'Hide the brain' : "Open this case's brain"}
              className={`hidden shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12.5px] transition lg:inline-flex ${
                lit !== null
                  ? 'border-line-strong bg-raised text-ink'
                  : 'border-line bg-canvas text-muted hover:border-line-strong hover:text-ink'
              }`}
            >
              <Waypoints size={14} className={lit !== null ? 'text-ink' : 'text-subtle'} />
              Brain
            </button>
          </header>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[46rem] px-5 py-10">
            {empty && (
              <div className="pt-20 text-center">
                <p
                  className="settle text-[30px] font-medium tracking-[-0.03em] text-ink"
                  style={{ '--i': 0 } as CSSProperties}
                >
                  Suishōdama
                </p>
                <p
                  className="settle mx-auto mt-3.5 max-w-sm text-[14.5px] leading-6 text-muted"
                  style={{ '--i': 1 } as CSSProperties}
                >
                  {caseId
                    ? 'Hand it the case file. Ask it anything about what is in there.'
                    : 'Open a case, hand it the file, and ask it anything about what is in there.'}
                </p>
                {assistantDown && (
                  <p
                    className="settle mx-auto mt-5 max-w-md rounded-2xl border border-[#f0dcdc] bg-danger-soft px-4 py-3 text-[13px] leading-6 text-danger"
                    style={{ '--i': 2 } as CSSProperties}
                  >
                    Suishōdama is not reachable right now. The case, its documents and
                    everything it has learned are untouched — documents can still be
                    added, and it will answer as soon as it is back.
                  </p>
                )}
                {caseId && !assistantDown && (
                  <div className="mt-8 flex flex-col items-center gap-2">
                    {OPENERS.map((opener, i) => (
                      <button
                        key={opener}
                        type="button"
                        onClick={() => send(opener)}
                        style={{ '--i': i + 2 } as CSSProperties}
                        className="settle w-full max-w-sm rounded-xl border border-line bg-canvas px-4 py-2.5 text-left text-[13.5px] text-muted shadow-[0_1px_2px_rgba(13,13,13,0.03)] transition hover:-translate-y-px hover:border-line-strong hover:text-ink hover:shadow-[0_3px_10px_rgba(13,13,13,0.06)] active:translate-y-0"
                      >
                        {opener}
                      </button>
                    ))}
                  </div>
                )}
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
                        caseId={caseId as string}
                        answer={answer}
                        shown={
                          lit !== null &&
                          lit.ids.join('|') ===
                            ((answer.highlight_path ?? []).length > 0
                              ? (answer.highlight_path ?? []).join('|')
                              : (answer.cited_nodes ?? []).join('|'))
                        }
                        onShow={(ids, ordered) => setLit({ ids, ordered })}
                      />
                    ) : (
                      <div className="whitespace-pre-wrap text-[15px] leading-7 text-ink">
                        {turn.text}
                      </div>
                    )}
                  </div>
                )
              })}

              {ask.isPending && <Thinking />}
            </div>

            <div ref={bottom} />
          </div>
        </div>

        {/* ------------------------------------------------------- composer */}
        <div className="shrink-0 px-5 pb-5">
          <div className="mx-auto w-full max-w-[46rem]">
            {notice && <p className="mb-2 px-2 text-[13px] leading-6 text-muted">{notice}</p>}
            {uploading && (
              <p className="mb-2 px-2 text-[13px] text-muted">Reading {uploading}…</p>
            )}

            <div className="flex items-end gap-2 rounded-[26px] border border-line-strong bg-canvas px-3 py-2 shadow-[0_1px_2px_rgba(13,13,13,0.04),0_8px_24px_-12px_rgba(13,13,13,0.14)] transition duration-200 focus-within:border-ink/20 focus-within:shadow-[0_1px_2px_rgba(13,13,13,0.05),0_12px_32px_-14px_rgba(13,13,13,0.2)]">
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

              {/* There is no stop control, deliberately: the run is server-side
                  and the answer is recorded on the case whether this tab waits
                  for it or not, so a button that only stopped the waiting would
                  be telling him something untrue. */}
              <button
                type="button"
                onClick={() => send()}
                disabled={!draft.trim() || ask.isPending || !caseId}
                aria-label="Send"
                className="rounded-full bg-ink p-2 text-white transition duration-200 hover:opacity-85 active:scale-95 disabled:bg-line-strong disabled:text-subtle disabled:hover:opacity-100 disabled:active:scale-100"
              >
                <ArrowUp size={15} />
              </button>
            </div>

            {/* ------------------------------------------------- the brain bar */}
            {caseId && counts && (
              <p className="mt-3 text-center text-[12px] leading-5">
                {grew ? (
                  <button
                    type="button"
                    onClick={() => setLit({ ids: [], ordered: false })}
                    className="grew inline-flex items-center gap-1.5 rounded-full border border-evidence/25 bg-evidence-soft px-3 py-1 font-medium text-evidence transition hover:border-evidence/40"
                  >
                    <span aria-hidden className="inline-block h-1.5 w-1.5 rounded-full bg-evidence" />
                    {grew}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setLit({ ids: [], ordered: false })}
                    className="rounded-full px-3 py-1 text-subtle transition hover:bg-raised hover:text-muted"
                  >
                    This case&rsquo;s brain holds {count(entitiesIn(counts), 'entity', 'entities')},{' '}
                    {count(counts.edges, 'link')} and {count(counts.documents, 'document')}. It
                    grows with every document.
                  </button>
                )}
              </p>
            )}
          </div>
        </div>
      </main>

      {/* ----------------------------------------------------------- brain */}
      {lit !== null && caseId && !graph.data && (
        // Pressing Brain must do something in the same frame it is pressed.
        // Waiting for the graph before drawing anything read as a dead button.
        <aside className="panel-in hidden w-[38%] min-w-[320px] shrink-0 flex-col border-l border-line bg-rail px-4 pt-3.5 shadow-[-18px_0_36px_-30px_rgba(13,13,13,0.45)] lg:flex">
          <p className="text-[13px] font-medium text-ink">The brain of this case</p>
          <p className="mt-0.5 text-[11.5px] text-subtle">
            {graph.isError ? 'It could not be opened just now.' : 'Opening…'}
          </p>
        </aside>
      )}

      {lit !== null && graph.data && caseId && (
        <div className="hidden w-[38%] min-w-[320px] lg:block">
          <Brain
            caseId={caseId}
            graph={graph.data}
            path={lit.ids}
            ordered={lit.ordered}
            onClose={() => setLit(null)}
            // An entity he clicked becomes a question he is about to ask. The
            // graph answers nothing itself — it hands the sentence to the one
            // chat and lets him change it before it goes (D25).
            onAsk={(question) => {
              setDraft(question)
              composer.current?.focus()
            }}
          />
        </div>
      )}

      {/* Dropping a file anywhere on the screen is the officer's one job, so it
          works anywhere on the screen. */}
      {dragging && caseId && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center bg-canvas/70 backdrop-blur-[2px]">
          <p className="rise rounded-2xl border-2 border-dashed border-evidence/40 bg-canvas px-7 py-5 text-[14px] font-medium text-evidence shadow-[0_8px_30px_-12px_rgba(13,13,13,0.2)]">
            Drop it here and it goes into this case
          </p>
        </div>
      )}
    </div>
  )
}
