import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Eye, EyeOff, FileText, Route, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getNode } from '../../lib/api'
import { edgeLabel, entityStyle, INFERRED_BELOW } from '../../lib/entities'
import { documentKindLabel } from '../../lib/documents'
import { formatCaseDate, isSensitiveType, maskIdentifier, titleCase } from '../../lib/format'
import { chipClass, quietButtonClass } from '../../lib/ui'
import type { CaseDocument, GraphEdge, GraphNode, NodeProfile, SourceRef } from '../../types'
import { EntityIcon } from './EntityIcon'
import type { SourceRequest } from './SourceDialog'

interface NodeDrawerProps {
  caseId: string
  nodeId: string | null
  onClose: () => void
  onSelectNode: (nodeId: string) => void
  onOpenSource: (request: SourceRequest) => void
  /** Start a trace: this entity becomes the "from" end. */
  onTraceFrom: (nodeId: string, label: string) => void
  /** Run the trace: `traceFrom` to the entity currently open. */
  onTraceTo: (nodeId: string, label: string) => void
  onCancelTrace: () => void
  traceFrom: { id: string; label: string } | null
  tracing: boolean
  /**
   * `panel` docks it beside the graph so nothing is covered — the Connections
   * panel is only 40% of the workspace and an overlay hides most of it.
   * `overlay` is for the tablet layout, where there is only one column.
   */
  variant?: 'panel' | 'overlay'
}

export function NodeDrawer({
  caseId,
  nodeId,
  onClose,
  onSelectNode,
  onOpenSource,
  onTraceFrom,
  onTraceTo,
  onCancelTrace,
  traceFrom,
  tracing,
  variant = 'overlay',
}: NodeDrawerProps) {
  // Tracked as "which entity was revealed" rather than a boolean reset by an
  // effect: opening a different entity masks it again on its own, because
  // Reveal is a decision about one identifier and not a session-wide setting.
  const [revealedFor, setRevealedFor] = useState<string | null>(null)
  const revealed = revealedFor !== null && revealedFor === nodeId

  const query = useQuery({
    queryKey: ['node', caseId, nodeId],
    queryFn: () => getNode(caseId, nodeId!),
    enabled: Boolean(nodeId),
  })

  useEffect(() => {
    if (!nodeId) return undefined
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [nodeId, onClose])

  if (!nodeId) return null

  const profile = query.data
  const node = profile?.node
  // `/nodes/{id}` returns one entry per source reference, so a name that appears
  // 34 times in one CDR comes back as the same file 34 times. The officer needs
  // the document once, with how often it names them.
  const namedIn = groupSources(profile)
  const sensitive = node ? isSensitiveType(node.type) : false
  const displayLabel = node
    ? sensitive && !revealed
      ? maskIdentifier(node.label)
      : node.label
    : nodeId

  return (
    <aside
      className={
        variant === 'panel'
          ? 'flex h-full min-h-0 w-full flex-col border-l border-line bg-panel'
          : 'absolute inset-y-0 right-0 z-30 flex w-[380px] max-w-[calc(100%-24px)] flex-col border-l border-line bg-panel shadow-[-14px_0_38px_rgba(32,37,43,0.10)]'
      }
      aria-label="Entity details"
    >
      <header className="flex items-start gap-3 border-b border-line p-4">
        {node && <EntityIcon type={node.type} size={19} />}
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[17px] font-semibold tracking-[-0.015em] text-ink">
            {displayLabel}
          </h2>
          <p className="mt-0.5 text-xs text-muted">
            {node ? entityStyle(node.type).label : 'Loading entity'}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close entity details"
          className="grid size-9 shrink-0 place-items-center rounded-lg border border-line text-muted hover:bg-canvas hover:text-ink"
        >
          <X size={17} />
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {query.isLoading && (
          <div className="animate-pulse space-y-3 p-4" aria-label="Loading entity details">
            {[0, 1, 2, 3, 4, 5].map((row) => (
              <div key={row} className="h-4 rounded bg-[#EEF0F2]" style={{ width: `${94 - row * 8}%` }} />
            ))}
          </div>
        )}

        {query.isError && (
          <div role="alert" className="m-4 flex items-start gap-3 rounded-lg border border-[#E6C0C0] bg-danger-soft p-4">
            <AlertCircle size={18} className="mt-0.5 shrink-0 text-danger" />
            <div>
              <p className="text-sm font-semibold text-ink">This entity could not be opened</p>
              <p className="mt-1 text-sm leading-6 text-muted">It may have been removed from the case.</p>
            </div>
          </div>
        )}

        {profile && node && (
          <>
            <Section title="Identity">
              {sensitive && (
                <button
                  type="button"
                  className={`${quietButtonClass} mb-3`}
                  onClick={() => setRevealedFor(revealed ? null : nodeId)}
                >
                  {revealed ? <EyeOff size={15} /> : <Eye size={15} />}
                  {revealed ? 'Hide identifier' : 'Reveal identifier'}
                </button>
              )}
              <dl className="space-y-2.5">
                <Row label="Type" value={entityStyle(node.type).label} />
                {node.first_seen && <Row label="First seen" value={formatCaseDate(node.first_seen)} />}
                {node.last_seen && <Row label="Last seen" value={formatCaseDate(node.last_seen)} />}
                <Row label="Links" value={String(profile.edges.length)} />
                <Row
                  label="Named in"
                  value={
                    namedIn.length === 1
                      ? '1 document'
                      : `${namedIn.length} documents`
                  }
                />
                {Object.entries(node.attrs)
                  .filter(([key]) => key !== 'aliases')
                  .map(([key, value]) => (
                    <Row key={key} label={titleCase(key)} value={renderAttr(value)} />
                  ))}
              </dl>
            </Section>

            <Section title={`Connections (${profile.neighbours.length})`}>
              <ul className="space-y-1.5">
                {profile.neighbours.map((neighbour) => (
                  <NeighbourRow
                    key={neighbour.id}
                    neighbour={neighbour}
                    edges={profile.edges.filter(
                      (edge) => edge.src === neighbour.id || edge.dst === neighbour.id,
                    )}
                    selfId={node.id}
                    onSelect={() => onSelectNode(neighbour.id)}
                  />
                ))}
                {profile.neighbours.length === 0 && (
                  <li className="text-sm text-muted">Nothing links to this entity yet.</li>
                )}
              </ul>
            </Section>

            <Section title={`Documents (${namedIn.length})`}>
              <ul className="space-y-1.5">
                {namedIn.map((entry) => (
                  <li key={entry.document.doc_id}>
                    <button
                      type="button"
                      onClick={() =>
                        onOpenSource({
                          docId: entry.document.doc_id,
                          start: entry.first?.start,
                          end: entry.first?.end,
                          context: node.label,
                        })
                      }
                      className="flex w-full items-center gap-2.5 rounded-lg border border-line bg-white px-3 py-2.5 text-left transition-colors hover:bg-canvas"
                    >
                      <FileText size={16} className="shrink-0 text-civic" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-ink">
                          {entry.document.filename}
                        </span>
                        <span className="block text-xs text-muted">
                          {documentKindLabel(entry.document.kind)} ·{' '}
                          {entry.count === 1
                            ? 'opens at the cited text'
                            : `named ${entry.count} times · opens at the first`}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
                {namedIn.length === 0 && (
                  <li className="text-sm text-muted">
                    This entity came from structured data rather than a document passage.
                  </li>
                )}
              </ul>
            </Section>
          </>
        )}
      </div>

      {profile && node && (
        <footer className="border-t border-line p-3">
          {traceFrom && traceFrom.id !== node.id ? (
            <>
              <button
                type="button"
                className={`${quietButtonClass} w-full`}
                disabled={tracing}
                onClick={() => onTraceTo(node.id, node.label)}
              >
                <Route size={15} />
                {tracing ? 'Finding a route...' : `Trace route from ${traceFrom.label}`}
              </button>
              <button
                type="button"
                className="mt-1.5 h-8 w-full rounded-lg text-xs font-medium text-muted hover:bg-canvas hover:text-ink"
                onClick={onCancelTrace}
              >
                Cancel
              </button>
            </>
          ) : traceFrom ? (
            <p className="rounded-lg border border-[#E4D3AF] bg-evidence-soft px-3 py-2.5 text-[13px] leading-5 text-[#7C5615]">
              Tracing from <strong>{traceFrom.label}</strong>. Open the entity you want to reach —
              from the graph, a citation or the list above.
            </p>
          ) : (
            <button
              type="button"
              className={`${quietButtonClass} w-full`}
              onClick={() => onTraceFrom(node.id, node.label)}
            >
              <Route size={15} />
              Trace a route from this entity
            </button>
          )}
        </footer>
      )}
    </aside>
  )
}

/**
 * One row per document rather than one per citation, with the number of times
 * the entity is named in it and the offset of the first mention to open at.
 */
function groupSources(profile: NodeProfile | undefined) {
  if (!profile) return []
  const byDoc = new Map<string, { document: CaseDocument; count: number; first?: SourceRef }>()
  for (const document of profile.documents) {
    const existing = byDoc.get(document.doc_id)
    if (existing) existing.count += 1
    else byDoc.set(document.doc_id, { document, count: 1 })
  }
  for (const source of profile.node.sources) {
    const entry = byDoc.get(source.doc_id)
    if (entry && !entry.first) entry.first = source
  }
  return [...byDoc.values()]
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-line p-4 last:border-b-0">
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.05em] text-subtle">{title}</h3>
      {children}
    </section>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="max-w-[60%] break-words text-right text-sm font-medium text-ink">{value}</dd>
    </div>
  )
}

function renderAttr(value: unknown): string {
  if (value === null || value === undefined) return 'Not recorded'
  if (Array.isArray(value)) return value.map(String).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

interface NeighbourRowProps {
  neighbour: GraphNode
  edges: GraphEdge[]
  selfId: string
  onSelect: () => void
}

function NeighbourRow({ neighbour, edges, selfId, onSelect }: NeighbourRowProps) {
  const sensitive = isSensitiveType(neighbour.type)
  const strongest = edges.reduce<GraphEdge | null>(
    (best, edge) => (!best || edge.confidence > best.confidence ? edge : best),
    null,
  )
  const direction = strongest?.src === selfId ? '' : 'is '

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left transition-colors hover:bg-canvas"
      >
        <EntityIcon type={neighbour.type} size={14} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">
            {sensitive ? maskIdentifier(neighbour.label) : neighbour.label}
          </span>
          {strongest && (
            <span className="block truncate text-xs text-muted">
              {direction}
              {edgeLabel(strongest.type)}
              {edges.length > 1 ? ` · ${edges.length} links` : ''}
            </span>
          )}
        </span>
        {strongest && strongest.confidence < INFERRED_BELOW && (
          <span className={`${chipClass} border-[#E4D3AF] bg-evidence-soft text-[#8A5F16]`}>Inferred</span>
        )}
      </button>
    </li>
  )
}
