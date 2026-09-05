import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, BookmarkCheck, CircleHelp, PackageSearch, Route, Sparkles } from 'lucide-react'
import { useMemo } from 'react'
import { closeMemory, getMemory } from '../../lib/api'
import { formatCaseDate } from '../../lib/format'
import { chipClass, quietButtonClass } from '../../lib/ui'
import type { MemoryEntry } from '../../types'
import { PanelBody, PanelHeader, PanelShell } from './PanelShell'

/**
 * What the agent has worked out and is still carrying. This is the difference
 * between an assistant and a search box (§3.8): an officer can come back in a
 * month and ask why it thinks something, and get the same answer with the same
 * citations.
 */
const groups = [
  {
    kind: 'conclusion',
    title: 'What it has concluded',
    blurb: 'Worked out from the case and kept, so it is still known next week.',
    icon: BookmarkCheck,
  },
  {
    kind: 'open_question',
    title: 'What it could not settle',
    blurb: 'Held open and re-checked as documents arrive.',
    icon: CircleHelp,
  },
  {
    kind: 'request',
    title: 'What it is asking for',
    blurb: 'Evidence that would unblock an answer it cannot give yet.',
    icon: PackageSearch,
  },
  {
    kind: 'briefing',
    title: 'What it has already told you',
    blurb: 'Findings it has raised, so it does not raise the same one twice.',
    icon: Sparkles,
  },
] as const

interface MemoryPanelProps {
  caseId: string
  onShowPath: (path: string[], label: string) => void
  onToast: (message: string) => void
  focused: boolean
  onFocusToggle: () => void
}

export function MemoryPanel({
  caseId,
  onShowPath,
  onToast,
  focused,
  onFocusToggle,
}: MemoryPanelProps) {
  const queryClient = useQueryClient()

  const memoryQuery = useQuery({
    queryKey: ['memory', caseId],
    queryFn: () => getMemory(caseId),
  })

  const close = useMutation({
    mutationFn: (entry: MemoryEntry) => closeMemory(caseId, entry.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['memory', caseId] })
      onToast('Marked as resolved')
    },
    onError: () => onToast('That entry could not be updated. Try again.'),
  })

  const byKind = useMemo(() => {
    const map = new Map<string, MemoryEntry[]>()
    for (const entry of memoryQuery.data ?? []) {
      map.set(entry.kind, [...(map.get(entry.kind) ?? []), entry])
    }
    return map
  }, [memoryQuery.data])

  const total = memoryQuery.data?.length ?? 0

  return (
    <PanelShell label="Memory">
      <PanelHeader title="Memory" focused={focused} onFocusToggle={onFocusToggle}>
        <span className="text-xs text-muted">{total} entries</span>
      </PanelHeader>

      <PanelBody>
        {memoryQuery.isLoading && (
          <div className="animate-pulse space-y-2.5" aria-label="Loading case memory">
            {[0, 1, 2].map((row) => (
              <div key={row} className="h-20 rounded-[10px] bg-[#EFF1F3]" />
            ))}
          </div>
        )}

        {memoryQuery.isError && (
          <div role="alert" className="flex items-start gap-3 rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-4">
            <AlertCircle size={19} className="mt-0.5 shrink-0 text-danger" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-ink">Case memory is unavailable</p>
              <button
                type="button"
                className={`${quietButtonClass} mt-3`}
                onClick={() => void memoryQuery.refetch()}
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {memoryQuery.data && total === 0 && (
          <p className="rounded-[10px] border border-dashed border-line-strong bg-panel px-5 py-8 text-center text-sm leading-6 text-muted">
            Nothing remembered yet. As shikonye works this case it records what it concludes, what
            it cannot settle and what evidence it needs — and all of it stays here.
          </p>
        )}

        <div className="space-y-6">
          {groups.map((group) => {
            const entries = byKind.get(group.kind) ?? []
            if (entries.length === 0) return null
            const Icon = group.icon

            return (
              <section key={group.kind} aria-labelledby={`memory-${group.kind}`}>
                <h3
                  id={`memory-${group.kind}`}
                  className="flex items-center gap-2 text-sm font-semibold text-ink"
                >
                  <Icon size={16} className="text-civic" />
                  {group.title}
                  <span className="font-normal text-muted">({entries.length})</span>
                </h3>
                <p className="mb-3 mt-1 text-[13px] leading-6 text-muted">{group.blurb}</p>

                <ul className="space-y-2.5">
                  {entries.map((entry) => (
                    <li key={entry.id} className="rounded-[10px] border border-line bg-panel p-4">
                      <p className="text-sm leading-6 text-ink">{entry.text}</p>

                      <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                        <span
                          className={`${chipClass} ${
                            entry.status === 'open'
                              ? 'border-[#E9D1A8] bg-warning-soft text-warning'
                              : 'border-line-strong bg-canvas text-muted'
                          }`}
                        >
                          {entry.status === 'open' ? 'Open' : 'Resolved'}
                        </span>
                        {typeof entry.confidence === 'number' && (
                          <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
                            Confidence {Math.round(entry.confidence * 100)}%
                          </span>
                        )}
                        {entry.created && <span>{formatCaseDate(entry.created)}</span>}
                      </div>

                      {typeof entry.meta?.why === 'string' && (
                        <p className="mt-2 text-[13px] leading-6 text-muted">
                          Why: {entry.meta.why}
                        </p>
                      )}

                      <div className="mt-3.5 flex flex-wrap gap-2 border-t border-line pt-3.5">
                        {entry.node_ids.length > 0 && (
                          <button
                            type="button"
                            className={quietButtonClass}
                            onClick={() => onShowPath(entry.node_ids, entry.text.slice(0, 60))}
                          >
                            <Route size={15} />
                            Show on graph
                          </button>
                        )}
                        {entry.status === 'open' && (
                          <button
                            type="button"
                            className={quietButtonClass}
                            disabled={close.isPending}
                            onClick={() => close.mutate(entry)}
                          >
                            Mark resolved
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}
        </div>
      </PanelBody>
    </PanelShell>
  )
}
