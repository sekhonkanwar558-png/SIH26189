import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Link2, ShieldAlert, ShieldCheck } from 'lucide-react'
import { getCustody } from '../../lib/api'
import { formatCaseDate, shortHash, titleCase } from '../../lib/format'
import { chipClass, quietButtonClass } from '../../lib/ui'
import { PanelBody, PanelHeader, PanelShell } from './PanelShell'

/**
 * The hash-chained audit log (§3.6). Every document that arrived and every
 * inference the system made, each entry hash-linked to the one before it — so
 * altering any earlier entry breaks every hash after it, and the panel says
 * exactly where.
 */

const actionLabels: Record<string, string> = {
  ingest: 'Document received',
  extract: 'Entities extracted',
  infer: 'Conclusion recorded',
  query: 'Question asked',
  web_search: 'Web search',
  export: 'Exported',
}

interface CustodyPanelProps {
  caseId: string
  focused: boolean
  onFocusToggle: () => void
}

export function CustodyPanel({ caseId, focused, onFocusToggle }: CustodyPanelProps) {
  const custodyQuery = useQuery({
    queryKey: ['custody', caseId],
    queryFn: () => getCustody(caseId),
  })

  const log = custodyQuery.data

  return (
    <PanelShell label="Custody">
      <PanelHeader title="Custody" focused={focused} onFocusToggle={onFocusToggle}>
        {log && <span className="text-xs text-muted">{log.verification.entries} entries</span>}
      </PanelHeader>

      <PanelBody>
        {custodyQuery.isLoading && (
          <div className="animate-pulse space-y-2.5" aria-label="Loading the custody log">
            <div className="h-20 rounded-[10px] bg-[#EFF1F3]" />
            {[0, 1, 2, 3].map((row) => (
              <div key={row} className="h-14 rounded-[10px] bg-[#F1F3F5]" />
            ))}
          </div>
        )}

        {custodyQuery.isError && (
          <div role="alert" className="flex items-start gap-3 rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-4">
            <AlertCircle size={19} className="mt-0.5 shrink-0 text-danger" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-ink">The custody log is unavailable</p>
              <button
                type="button"
                className={`${quietButtonClass} mt-3`}
                onClick={() => void custodyQuery.refetch()}
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {log && (
          <>
            <div
              className={`rounded-[10px] border p-4 ${
                log.verification.valid
                  ? 'border-[#B9D6C8] bg-success-soft'
                  : 'border-[#E7C7C7] bg-danger-soft'
              }`}
            >
              <div className="flex items-start gap-3">
                {log.verification.valid ? (
                  <ShieldCheck size={22} className="mt-0.5 shrink-0 text-success" />
                ) : (
                  <ShieldAlert size={22} className="mt-0.5 shrink-0 text-danger" />
                )}
                <div className="min-w-0">
                  <p className="text-[15px] font-semibold text-ink">
                    {log.verification.valid
                      ? 'The record of this case is intact'
                      : 'This record has been altered'}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-muted">
                    {log.verification.valid
                      ? `All ${log.verification.entries} entries verify against the entry before them. Nothing in this case's history has been changed since it was written.`
                      : log.verification.reason ||
                        'One entry no longer matches the hash recorded after it.'}
                  </p>
                  {!log.verification.valid && log.verification.broken_at !== null && (
                    <p className="mt-2 text-sm font-semibold text-danger">
                      The chain breaks at entry #{log.verification.broken_at}. Everything after it
                      is unreliable.
                    </p>
                  )}
                  {log.verification.head && (
                    <p className="mt-2 font-mono text-[11px] text-subtle">
                      head {shortHash(log.verification.head, 24)}
                    </p>
                  )}
                </div>
              </div>
            </div>

            <p className="mb-3 mt-5 text-[13px] leading-6 text-muted">
              Newest first. Each entry carries the hash of the one before it, so the order itself is
              evidence.
            </p>

            <ol className="space-y-2">
              {[...log.entries].reverse().map((entry) => (
                <li key={entry.seq} className="rounded-[10px] border border-line bg-panel p-3.5">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full border border-line-strong bg-canvas font-mono text-[11px] font-semibold text-muted">
                      {entry.seq}
                    </span>
                    <span className="text-sm font-semibold text-ink">
                      {actionLabels[entry.action] ?? titleCase(entry.action)}
                    </span>
                    <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
                      {entry.actor}
                    </span>
                    <span className="ml-auto text-xs text-muted">{formatCaseDate(entry.ts)}</span>
                  </div>

                  <p className="mt-2 break-words text-[13px] text-muted">{entry.ref}</p>

                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-subtle">
                    <span className="flex items-center gap-1.5">
                      <Link2 size={12} />
                      prev {shortHash(entry.prev_hash, 12)}
                    </span>
                    <span>this {shortHash(entry.hash, 12)}</span>
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </PanelBody>
    </PanelShell>
  )
}
