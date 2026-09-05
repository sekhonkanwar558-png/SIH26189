import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  CircleAlert,
  FileCheck2,
  Info,
  Maximize2,
  Minimize2,
  Route,
  Trash2,
  WifiOff,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, askCase, getBrief, uploadDocument } from '../../lib/api'
import type { Conversation, Message } from '../../lib/conversation'
import { documentKindLabel } from '../../lib/documents'
import { formatClockTime, formatDayLabel, titleCase } from '../../lib/format'
import { chipClass, iconButtonClass, quietButtonClass } from '../../lib/ui'
import type { CaseBrief, CaseGraph, Finding, GraphEdge, GraphNode, IngestResult } from '../../types'
import { AnswerCard } from './AnswerCard'
import { Composer, type PendingAttachment } from './Composer'
import type { SourceRequest } from './SourceDialog'

interface ShikonyeProps {
  caseId: string
  officerId: string
  conversation: Conversation
  graph: CaseGraph | undefined
  modelAvailable: boolean
  activePath: string[]
  onShowPath: (path: string[], label: string) => void
  onOpenNode: (nodeId: string) => void
  onOpenSource: (request: SourceRequest) => void
  onOpenFindings: () => void
  focused: boolean
  onFocusToggle: () => void
}

export function Shikonye({
  caseId,
  officerId,
  conversation,
  graph,
  modelAvailable,
  activePath,
  onShowPath,
  onOpenNode,
  onOpenSource,
  onOpenFindings,
  focused,
  onFocusToggle,
}: ShikonyeProps) {
  const queryClient = useQueryClient()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState<PendingAttachment[]>([])
  const [busy, setBusy] = useState(false)

  const { messages, pushOfficer, pushAnswer, pushBrief, pushUpload, pushNotice, clear, hasBrief } =
    conversation

  const nodesById = useMemo(() => {
    const map = new Map(graph?.nodes.map((node) => [node.id, node]) ?? [])
    return map
  }, [graph])
  const edgesById = useMemo(() => {
    const map = new Map(graph?.edges.map((edge) => [edge.id, edge]) ?? [])
    return map
  }, [graph])

  // What the agent says without being asked (§3.8) opens every conversation.
  const briefQuery = useQuery({
    queryKey: ['brief', caseId],
    queryFn: () => getBrief(caseId),
    enabled: !hasBrief,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (briefQuery.data && !hasBrief) pushBrief(briefQuery.data)
  }, [briefQuery.data, hasBrief, pushBrief])

  useEffect(() => {
    const container = scrollRef.current
    if (container) container.scrollTop = container.scrollHeight
  }, [messages.length, busy])

  function attach(files: FileList) {
    const additions: PendingAttachment[] = Array.from(files).map((file) => ({
      id: `${file.name}-${file.size}-${Math.random().toString(36).slice(2, 7)}`,
      file,
      kind: '',
      progress: 0,
      status: 'ready',
    }))
    setAttachments((current) => [...current, ...additions])
  }

  function updateAttachment(id: string, patch: Partial<PendingAttachment>) {
    setAttachments((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    )
  }

  async function send() {
    const question = text.trim()
    const pending = attachments.filter((item) => item.status === 'ready')
    if (!question && pending.length === 0) return

    setBusy(true)
    pushOfficer(question, pending.map((item) => item.file.name))
    setText('')

    // Documents go in first, so a question asked in the same turn is answered
    // against everything the officer just handed over.
    let ingested = 0
    for (const attachment of pending) {
      updateAttachment(attachment.id, { status: 'uploading', progress: 0 })
      try {
        const response = await uploadDocument(
          caseId,
          attachment.file,
          attachment.kind || undefined,
          officerId,
          (percent) => updateAttachment(attachment.id, { progress: percent }),
        )
        updateAttachment(attachment.id, { status: 'done', progress: 100 })
        pushUpload(attachment.file.name, response.document)
        ingested += 1
      } catch (error) {
        const detail =
          error instanceof ApiError
            ? error.message
            : 'This document could not be added to the case.'
        updateAttachment(attachment.id, { status: 'failed', error: detail })
        pushNotice(`${attachment.file.name} was not added. ${detail}`, 'error')
      }
    }

    if (ingested > 0) {
      setAttachments((current) => current.filter((item) => item.status !== 'done'))
      await queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['graph', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['analytics', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['documents', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['custody', caseId] })
    }

    if (question) {
      try {
        const answer = await askCase(caseId, question, officerId)
        pushAnswer(question, answer)
        await queryClient.invalidateQueries({ queryKey: ['memory', caseId] })
        await queryClient.invalidateQueries({ queryKey: ['custody', caseId] })
      } catch (error) {
        const detail =
          error instanceof ApiError
            ? error.message
            : 'The case service could not be reached.'
        pushNotice(detail, 'error')
      }
    }

    setBusy(false)
  }

  async function retry(question: string) {
    setBusy(true)
    try {
      const answer = await askCase(caseId, question, officerId)
      pushAnswer(question, answer)
    } catch {
      pushNotice('The case service could not be reached.', 'error')
    }
    setBusy(false)
  }

  const grouped = useMemo(() => groupByDay(messages), [messages])

  return (
    <section className="flex h-full min-h-0 flex-col bg-panel" aria-label="shikonye">
      <header className="flex items-center gap-3 border-b border-line px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold lowercase text-ink">shikonye</h2>
          <p className="text-xs text-muted">This case&apos;s assistant</p>
        </div>
        {!modelAvailable && (
          <span className={`${chipClass} border-[#E9D1A8] bg-warning-soft text-warning`}>
            <WifiOff size={13} />
            Offline analysis
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {messages.length > 0 && (
            <button
              type="button"
              className={quietButtonClass}
              onClick={clear}
              title="Clear this conversation from this device"
            >
              <Trash2 size={15} />
              Clear
            </button>
          )}
          <button
            type="button"
            className={iconButtonClass}
            onClick={onFocusToggle}
            aria-label={focused ? 'Exit focus mode' : 'Focus the shikonye panel'}
            title={focused ? 'Exit focus mode' : 'Focus'}
          >
            {focused ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
        {briefQuery.isLoading && messages.length === 0 && (
          <div className="animate-pulse space-y-3" aria-label="Loading the case briefing">
            <div className="h-4 w-1/3 rounded bg-[#EEF0F2]" />
            <div className="h-24 rounded-[12px] bg-[#F1F3F5]" />
            <div className="h-16 rounded-[12px] bg-[#F4F6F7]" />
            <p className="pt-1 text-center text-xs text-muted">
              Reading the case before saying anything...
            </p>
          </div>
        )}

        {briefQuery.isError && messages.length === 0 && (
          <div role="alert" className="flex items-start gap-3 rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-4">
            <AlertCircle size={19} className="mt-0.5 shrink-0 text-danger" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-ink">The case briefing could not load</p>
              <p className="mt-1 text-sm leading-6 text-muted">
                Everything else in this case is still available.
              </p>
              <button type="button" className={`${quietButtonClass} mt-3`} onClick={() => void briefQuery.refetch()}>
                Retry
              </button>
            </div>
          </div>
        )}

        <div className="space-y-5">
          {grouped.map((group) => (
            <div key={group.day} className="space-y-3">
              <div className="flex items-center gap-3" role="separator" aria-label={group.day}>
                <span className="h-px flex-1 bg-line" />
                <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-subtle">
                  {group.day}
                </span>
                <span className="h-px flex-1 bg-line" />
              </div>

              {group.messages.map((message) => (
                <MessageRow
                  key={message.id}
                  message={message}
                  resolveNode={(id) => nodesById.get(id)}
                  resolveEdge={(id) => edgesById.get(id)}
                  activePath={activePath}
                  onShowPath={onShowPath}
                  onOpenNode={onOpenNode}
                  onOpenSource={onOpenSource}
                  onOpenFindings={onOpenFindings}
                  onRetry={message.role === 'shikonye' && message.kind === 'answer'
                    ? () => void retry(message.question)
                    : undefined}
                />
              ))}
            </div>
          ))}
        </div>

        {busy && (
          <div className="mt-4 flex items-center gap-2.5 text-sm text-muted">
            <span className="flex gap-1" aria-hidden="true">
              <span className="size-1.5 animate-bounce rounded-full bg-line-strong [animation-delay:-0.2s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-line-strong [animation-delay:-0.1s]" />
              <span className="size-1.5 animate-bounce rounded-full bg-line-strong" />
            </span>
            {attachments.some((item) => item.status === 'uploading')
              ? 'Reading the documents you added...'
              : 'Working through the case graph...'}
          </div>
        )}
      </div>

      <Composer
        text={text}
        onTextChange={setText}
        attachments={attachments}
        onAttach={attach}
        onRemove={(id) => setAttachments((current) => current.filter((item) => item.id !== id))}
        onChangeKind={(id, kind) => updateAttachment(id, { kind })}
        onSubmit={() => void send()}
        busy={busy}
      />
    </section>
  )
}

interface MessageRowProps {
  message: Message
  resolveNode: (id: string) => GraphNode | undefined
  resolveEdge: (id: string) => GraphEdge | undefined
  activePath: string[]
  onShowPath: (path: string[], label: string) => void
  onOpenNode: (id: string) => void
  onOpenSource: (request: SourceRequest) => void
  onOpenFindings: () => void
  onRetry?: () => void
}

function MessageRow(props: MessageRowProps) {
  const { message } = props

  if (message.role === 'officer') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[86%]">
          <div className="mb-1 flex items-center justify-end gap-2">
            <span className="text-[11px] font-semibold text-muted">You</span>
            <span className="text-[11px] text-subtle">{formatClockTime(message.ts)}</span>
          </div>
          <div className="rounded-[12px] rounded-tr-[4px] border border-[#CBD9E5] bg-white px-3.5 py-2.5">
            {message.text && (
              <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{message.text}</p>
            )}
            {message.attachments.length > 0 && (
              <ul className={message.text ? 'mt-2 space-y-1' : 'space-y-1'}>
                {message.attachments.map((name) => (
                  <li key={name} className="flex items-center gap-1.5 text-[13px] text-muted">
                    <FileCheck2 size={14} className="shrink-0" />
                    {name}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[94%]">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-[11px] font-semibold lowercase text-muted">shikonye</span>
          <span className="text-[11px] text-subtle">{formatClockTime(message.ts)}</span>
        </div>
        <ShikonyeBody {...props} />
      </div>
    </div>
  )
}

function ShikonyeBody({
  message,
  resolveNode,
  resolveEdge,
  activePath,
  onShowPath,
  onOpenNode,
  onOpenSource,
  onOpenFindings,
  onRetry,
}: MessageRowProps) {
  if (message.role !== 'shikonye') return null

  if (message.kind === 'answer') {
    const samePath =
      message.answer.highlight_path.length > 0 &&
      message.answer.highlight_path.join('|') === activePath.join('|')
    return (
      <AnswerCard
        answer={message.answer}
        resolveNode={resolveNode}
        resolveEdge={resolveEdge}
        onShowPath={() => onShowPath(message.answer.highlight_path, message.question)}
        onOpenNode={onOpenNode}
        onOpenSource={onOpenSource}
        onRetry={onRetry}
        pathActive={samePath}
      />
    )
  }

  if (message.kind === 'brief') {
    return (
      <BriefCard
        brief={message.brief}
        resolveNode={resolveNode}
        resolveEdge={resolveEdge}
        activePath={activePath}
        onShowPath={onShowPath}
        onOpenNode={onOpenNode}
        onOpenSource={onOpenSource}
        onOpenFindings={onOpenFindings}
      />
    )
  }

  if (message.kind === 'upload') {
    return <UploadCard filename={message.filename} result={message.result} />
  }

  return (
    <div
      className={`rounded-[12px] border px-3.5 py-3 ${
        message.tone === 'error'
          ? 'border-[#E7C7C7] bg-danger-soft'
          : 'border-line bg-panel'
      }`}
    >
      <p className="flex items-start gap-2 text-sm leading-6 text-ink">
        {message.tone === 'error' ? (
          <CircleAlert size={16} className="mt-1 shrink-0 text-danger" />
        ) : (
          <Info size={16} className="mt-1 shrink-0 text-civic" />
        )}
        {message.text}
      </p>
    </div>
  )
}

/**
 * D18: a document the system could not read comes back 200 with a warning, and
 * the warning is the whole point — a green tick over an empty graph is worse
 * than an error. So warnings are the loudest thing in this card.
 */
function UploadCard({ filename, result }: { filename: string; result: IngestResult }) {
  const empty = result.nodes_new === 0 && result.edges_new === 0

  return (
    <div className="rounded-[12px] border border-line bg-panel p-4">
      <p className="text-[15px] leading-7 text-ink">
        <span className="font-semibold">{filename}</span> is now part of this case, filed as{' '}
        <span className="font-semibold">{documentKindLabel(result.kind)}</span>.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
          {result.nodes_new} new entities
        </span>
        <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
          {result.edges_new} new links
        </span>
        <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
          {result.chars.toLocaleString('en-IN')} characters read
        </span>
      </div>

      {result.warnings.length > 0 && (
        <div className="mt-3.5 rounded-lg border border-[#E9D1A8] bg-warning-soft p-3.5">
          <p className="flex items-center gap-2 text-sm font-semibold text-ink">
            <CircleAlert size={16} className="shrink-0 text-warning" />
            This document was not fully read
          </p>
          <ul className="mt-2 space-y-1.5">
            {result.warnings.map((warning) => (
              <li key={warning} className="text-[13px] leading-6 text-ink">
                {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {empty && result.warnings.length === 0 && (
        <p className="mt-3 text-[13px] leading-6 text-muted">
          Nothing new was added — every entity in it was already in this case.
        </p>
      )}

      {result.entities.length > 0 && (
        <p className="mt-3 text-[13px] leading-6 text-muted">
          Found: {result.entities.slice(0, 8).join(', ')}
          {result.entities.length > 8 ? `, and ${result.entities.length - 8} more` : ''}.
        </p>
      )}
    </div>
  )
}

interface BriefCardProps {
  brief: CaseBrief
  resolveNode: (id: string) => GraphNode | undefined
  resolveEdge: (id: string) => GraphEdge | undefined
  activePath: string[]
  onShowPath: (path: string[], label: string) => void
  onOpenNode: (id: string) => void
  onOpenSource: (request: SourceRequest) => void
  onOpenFindings: () => void
}

function BriefCard({
  brief,
  resolveNode,
  resolveEdge,
  activePath,
  onShowPath,
  onOpenNode,
  onOpenSource,
  onOpenFindings,
}: BriefCardProps) {
  const top = brief.findings.slice(0, 3)

  return (
    <div className="space-y-3">
      {brief.narrative && (
        <AnswerCard
          answer={brief.narrative}
          resolveNode={resolveNode}
          resolveEdge={resolveEdge}
          onShowPath={() => onShowPath(brief.narrative!.highlight_path, 'Opening briefing')}
          onOpenNode={onOpenNode}
          onOpenSource={onOpenSource}
          pathActive={brief.narrative.highlight_path.join('|') === activePath.join('|')}
        />
      )}

      {top.length > 0 && (
        <div className="rounded-[12px] border border-line bg-panel p-4">
          <h3 className="text-sm font-semibold text-ink">
            What stands out in this case
          </h3>
          <p className="mt-1 text-[13px] leading-6 text-muted">
            Worked out from the case graph, so these hold with or without the reasoning model.
          </p>
          <ul className="mt-3 space-y-2.5">
            {top.map((finding) => (
              <BriefFinding
                key={finding.id}
                finding={finding}
                onShow={() => onShowPath(finding.node_ids, finding.headline)}
              />
            ))}
          </ul>
          {brief.findings.length > top.length && (
            <button type="button" className={`${quietButtonClass} mt-3.5`} onClick={onOpenFindings}>
              See all {brief.findings.length} findings
            </button>
          )}
        </div>
      )}

      {(brief.open_questions.length > 0 || brief.requests.length > 0) && (
        <div className="rounded-[12px] border border-line bg-panel p-4">
          <h3 className="text-sm font-semibold text-ink">What I still need</h3>
          <ul className="mt-2.5 space-y-2">
            {[...brief.requests, ...brief.open_questions].slice(0, 4).map((entry) => (
              <li key={entry.id} className="text-[13px] leading-6 text-muted">
                {entry.text}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

const severityStyles = {
  high: 'border-[#E7C7C7] bg-danger-soft text-danger',
  medium: 'border-[#E9D1A8] bg-warning-soft text-warning',
  low: 'border-line-strong bg-canvas text-muted',
} as const

function BriefFinding({ finding, onShow }: { finding: Finding; onShow: () => void }) {
  return (
    <li className="rounded-lg border border-line bg-canvas p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold leading-6 text-ink">{finding.headline}</p>
        <span className={`${chipClass} shrink-0 ${severityStyles[finding.severity] ?? severityStyles.low}`}>
          {titleCase(finding.severity)}
        </span>
      </div>
      <p className="mt-1.5 text-[13px] leading-6 text-muted">{finding.detail}</p>
      {finding.node_ids.length > 0 && (
        <button type="button" className={`${quietButtonClass} mt-2.5`} onClick={onShow}>
          <Route size={15} />
          Show on graph
        </button>
      )}
    </li>
  )
}

function groupByDay(messages: Message[]) {
  const groups: Array<{ day: string; messages: Message[] }> = []
  for (const message of messages) {
    const day = formatDayLabel(message.ts)
    const last = groups[groups.length - 1]
    if (last && last.day === day) last.messages.push(message)
    else groups.push({ day, messages: [message] })
  }
  return groups
}
