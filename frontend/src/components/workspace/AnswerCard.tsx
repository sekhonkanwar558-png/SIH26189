import {
  AlertTriangle,
  Check,
  ChevronDown,
  Copy,
  Info,
  RotateCcw,
  Route,
  ShieldAlert,
} from 'lucide-react'
import { useState } from 'react'
import { edgeLabel } from '../../lib/entities'
import { isSensitiveType, maskIdentifier } from '../../lib/format'
import { chipClass, quietButtonClass } from '../../lib/ui'
import type { AgentAnswer, GraphEdge, GraphNode } from '../../types'
import { EntityIcon } from './EntityIcon'
import type { SourceRequest } from './SourceDialog'

const confidenceStyles = {
  high: { label: 'High confidence', className: 'border-[#B9D6C8] bg-success-soft text-success' },
  medium: { label: 'Medium confidence', className: 'border-[#E9D1A8] bg-warning-soft text-warning' },
  low: { label: 'Low confidence', className: 'border-line-strong bg-canvas text-muted' },
} as const

interface AnswerCardProps {
  answer: AgentAnswer
  resolveNode: (id: string) => GraphNode | undefined
  resolveEdge: (id: string) => GraphEdge | undefined
  onShowPath: () => void
  onOpenNode: (id: string) => void
  onOpenSource: (request: SourceRequest) => void
  onRetry?: () => void
  pathActive: boolean
}

export function AnswerCard({
  answer,
  resolveNode,
  resolveEdge,
  onShowPath,
  onOpenNode,
  onOpenSource,
  onRetry,
  pathActive,
}: AnswerCardProps) {
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [revealUnverified, setRevealUnverified] = useState(false)
  const [copied, setCopied] = useState(false)

  const confidence = confidenceStyles[answer.confidence] ?? confidenceStyles.low
  const hasCitations = answer.cited_nodes.length > 0 || answer.cited_edges.length > 0
  // A verification that ran and failed is a failure to show loudly. A missing
  // block means none ran — an empty case has nothing to cite and nothing to
  // check, and calling that "unverified" would cry wolf on every new case.
  const failed = answer.verified ? !answer.verified.ok : false
  const dropped = answer.verified ?? { dropped_nodes: [], dropped_edges: [] }

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(answer.answer)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2_000)
    } catch {
      // Clipboard access can be refused; the officer can still select the text.
    }
  }

  // §5.6: an answer whose citations did not check out is not an answer. It is
  // shown as a failure, and the text stays behind a deliberate click.
  if (failed && !revealUnverified) {
    return (
      <div className="rounded-[12px] border border-[#E7C7C7] bg-danger-soft p-4">
        <div className="flex items-start gap-3">
          <ShieldAlert size={19} className="mt-0.5 shrink-0 text-danger" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink">This answer could not be verified</p>
            <p className="mt-1.5 text-sm leading-6 text-muted">
              {hasCitations
                ? 'Some of the evidence it cited does not exist in this case graph, so it has not been shown as a finding.'
                : 'It cited nothing in this case, which means it was not answered from the case file.'}
            </p>
            {(dropped.dropped_nodes.length > 0 || dropped.dropped_edges.length > 0) && (
              <p className="mt-2 text-xs text-muted">
                Dropped {dropped.dropped_nodes.length} entity citations and{' '}
                {dropped.dropped_edges.length} link citations.
              </p>
            )}
            <div className="mt-3.5 flex flex-wrap gap-2">
              {onRetry && (
                <button type="button" className={quietButtonClass} onClick={onRetry}>
                  <RotateCcw size={15} />
                  Ask again
                </button>
              )}
              <button
                type="button"
                className={quietButtonClass}
                onClick={() => setRevealUnverified(true)}
              >
                Show the unverified answer
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-[12px] border border-line bg-panel p-4">
      {failed && (
        <div className="mb-3 flex items-start gap-2.5 rounded-lg border border-[#E7C7C7] bg-danger-soft px-3 py-2.5">
          <ShieldAlert size={16} className="mt-0.5 shrink-0 text-danger" />
          <p className="text-xs leading-5 text-ink">
            Unverified — shown at your request. Do not rely on this without checking it yourself.
          </p>
        </div>
      )}

      <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{answer.answer}</p>

      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        <span className={`${chipClass} ${confidence.className}`}>
          <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
          {confidence.label}
        </span>
        {hasCitations && (
          <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
            {answer.cited_nodes.length} entities · {answer.cited_edges.length} links cited
          </span>
        )}
      </div>

      {(answer.caveats ?? []).length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {(answer.caveats ?? []).map((caveat) => (
            <li key={caveat} className="flex items-start gap-2 text-[13px] leading-6 text-muted">
              <Info size={15} className="mt-1 shrink-0 text-[#9A6518]" />
              {caveat}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-3.5">
        <button type="button" className={quietButtonClass} onClick={copyAnswer}>
          {copied ? <Check size={15} /> : <Copy size={15} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
        {hasCitations && (
          <button
            type="button"
            className={quietButtonClass}
            onClick={() => setEvidenceOpen((open) => !open)}
            aria-expanded={evidenceOpen}
          >
            <ChevronDown
              size={15}
              className={`transition-transform ${evidenceOpen ? 'rotate-180' : ''}`}
            />
            View Evidence
          </button>
        )}
        {answer.highlight_path.length > 0 && (
          <button
            type="button"
            className={`${quietButtonClass} ${pathActive ? 'border-evidence bg-evidence-soft text-[#7C5615]' : ''}`}
            onClick={onShowPath}
          >
            <Route size={15} />
            {pathActive ? 'Path shown' : 'Show Path'}
          </button>
        )}
      </div>

      {evidenceOpen && (
        <div className="mt-3.5 rounded-lg border border-line bg-canvas p-3.5">
          <h4 className="text-[11px] font-semibold uppercase tracking-[0.05em] text-subtle">
            Evidence used
          </h4>

          {answer.cited_nodes.length > 0 && (
            <ul className="mt-2.5 flex flex-wrap gap-1.5">
              {answer.cited_nodes.map((id) => {
                const node = resolveNode(id)
                const label = node
                  ? isSensitiveType(node.type)
                    ? maskIdentifier(node.label)
                    : node.label
                  : id
                return (
                  <li key={id}>
                    <button
                      type="button"
                      onClick={() => onOpenNode(id)}
                      className="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-white py-1 pl-1 pr-2.5 text-xs font-medium text-ink transition-colors hover:border-[#AAB7C3] hover:bg-civic-soft"
                    >
                      <EntityIcon type={node?.type ?? id} size={11} />
                      {label}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}

          {answer.cited_edges.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {answer.cited_edges.slice(0, 8).map((id) => {
                const edge = resolveEdge(id)
                if (!edge) {
                  return (
                    <li key={id} className="text-xs text-muted">
                      Link {id} is no longer in the case graph.
                    </li>
                  )
                }
                const source = edge.sources[0]
                const from = resolveNode(edge.src)?.label ?? edge.src
                const to = resolveNode(edge.dst)?.label ?? edge.dst
                return (
                  <li key={id}>
                    <button
                      type="button"
                      disabled={!source}
                      onClick={() =>
                        source &&
                        onOpenSource({
                          docId: source.doc_id,
                          start: source.start,
                          end: source.end,
                          context: `${from} ${edgeLabel(edge.type)} ${to}`,
                        })
                      }
                      className="w-full rounded-md px-2 py-1.5 text-left text-xs leading-5 text-muted transition-colors enabled:hover:bg-white enabled:hover:text-ink disabled:cursor-default"
                    >
                      <span className="font-medium text-ink">{from}</span> {edgeLabel(edge.type)}{' '}
                      <span className="font-medium text-ink">{to}</span>
                      {source && <span className="ml-1.5 text-civic underline">open source</span>}
                    </button>
                  </li>
                )
              })}
              {answer.cited_edges.length > 8 && (
                <li className="px-2 text-xs text-muted">
                  and {answer.cited_edges.length - 8} more links.
                </li>
              )}
            </ul>
          )}

          {!hasCitations && (
            <p className="mt-2 flex items-start gap-2 text-xs leading-5 text-muted">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[#9A6518]" />
              Nothing was cited.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
