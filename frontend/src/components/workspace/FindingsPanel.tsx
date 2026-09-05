import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Route, Search, TrendingUp, Users } from 'lucide-react'
import { getAnalytics, investigateFinding } from '../../lib/api'
import { formatCaseDate, titleCase } from '../../lib/format'
import { chipClass, quietButtonClass } from '../../lib/ui'
import type { AgentAnswer, Finding } from '../../types'
import { EntityIcon } from './EntityIcon'
import { PanelBody, PanelHeader, PanelShell } from './PanelShell'

const severityStyles = {
  high: 'border-[#E7C7C7] bg-danger-soft text-danger',
  medium: 'border-[#E9D1A8] bg-warning-soft text-warning',
  low: 'border-line-strong bg-canvas text-muted',
} as const

interface FindingsPanelProps {
  caseId: string
  onShowPath: (path: string[], label: string) => void
  onOpenNode: (nodeId: string) => void
  /** An investigation is a real answer — it belongs in the conversation. */
  onInvestigated: (question: string, answer: AgentAnswer) => void
  onToast: (message: string) => void
  focused: boolean
  onFocusToggle: () => void
}

export function FindingsPanel({
  caseId,
  onShowPath,
  onOpenNode,
  onInvestigated,
  onToast,
  focused,
  onFocusToggle,
}: FindingsPanelProps) {
  const queryClient = useQueryClient()

  const analyticsQuery = useQuery({
    queryKey: ['analytics', caseId],
    queryFn: () => getAnalytics(caseId, 'betweenness', 8),
  })

  const investigate = useMutation({
    mutationFn: (finding: Finding) => investigateFinding(caseId, finding.id),
    onSuccess: async (answer, finding) => {
      onInvestigated(`Investigate: ${finding.headline}`, answer)
      onToast('shikonye worked that finding — see the conversation')
      await queryClient.invalidateQueries({ queryKey: ['memory', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['custody', caseId] })
    },
    onError: () => onToast('That finding could not be investigated. Try again.'),
  })

  const analytics = analyticsQuery.data

  return (
    <PanelShell label="Findings">
      <PanelHeader title="Findings" focused={focused} onFocusToggle={onFocusToggle}>
        {analytics && (
          <span className="text-xs text-muted">{analytics.findings.length} worked out so far</span>
        )}
      </PanelHeader>

      <PanelBody>
        {analyticsQuery.isLoading && (
          <div className="animate-pulse space-y-2.5" aria-label="Loading findings">
            {[0, 1, 2, 3].map((row) => (
              <div key={row} className="h-[104px] rounded-[10px] bg-[#EFF1F3]" />
            ))}
          </div>
        )}

        {analyticsQuery.isError && (
          <div role="alert" className="flex items-start gap-3 rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-4">
            <AlertCircle size={19} className="mt-0.5 shrink-0 text-danger" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-ink">Findings are unavailable</p>
              <p className="mt-1 text-sm leading-6 text-muted">
                The case service did not return this case&apos;s analysis.
              </p>
              <button
                type="button"
                className={`${quietButtonClass} mt-3`}
                onClick={() => void analyticsQuery.refetch()}
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {analytics && (
          <>
            <p className="mb-4 text-[13px] leading-6 text-muted">
              Computed from this case&apos;s own graph, so they hold whether or not the reasoning
              model is reachable.
            </p>

            {analytics.findings.length === 0 && (
              <p className="rounded-[10px] border border-dashed border-line-strong bg-panel px-5 py-8 text-center text-sm text-muted">
                Nothing stands out yet. Add more documents and the analysis re-runs itself.
              </p>
            )}

            <ul className="space-y-2.5">
              {analytics.findings.map((finding) => (
                <li key={finding.id} className="rounded-[10px] border border-line bg-panel p-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-[15px] font-semibold leading-6 text-ink">
                      {finding.headline}
                    </h3>
                    <span
                      className={`${chipClass} shrink-0 ${severityStyles[finding.severity] ?? severityStyles.low}`}
                    >
                      {titleCase(finding.severity)}
                    </span>
                  </div>

                  <p className="mt-1.5 text-sm leading-6 text-muted">{finding.detail}</p>

                  <div className="mt-2.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
                      {titleCase(finding.kind)}
                    </span>
                    {finding.ts && <span>{formatCaseDate(finding.ts)}</span>}
                  </div>

                  <div className="mt-3.5 flex flex-wrap gap-2 border-t border-line pt-3.5">
                    {finding.node_ids.length > 0 && (
                      <button
                        type="button"
                        className={quietButtonClass}
                        onClick={() => onShowPath(finding.node_ids, finding.headline)}
                      >
                        <Route size={15} />
                        Show on graph
                      </button>
                    )}
                    <button
                      type="button"
                      className={quietButtonClass}
                      disabled={investigate.isPending}
                      onClick={() => investigate.mutate(finding)}
                    >
                      <Search size={15} />
                      {investigate.isPending && investigate.variables?.id === finding.id
                        ? 'Working...'
                        : 'Investigate'}
                    </button>
                  </div>
                </li>
              ))}
            </ul>

            <section className="mt-7" aria-labelledby="influencers-heading">
              <h3
                id="influencers-heading"
                className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink"
              >
                <TrendingUp size={16} className="text-civic" />
                Who holds this network together
              </h3>
              <ul className="space-y-2">
                {analytics.influencers.map((influencer) => (
                  <li key={influencer.node_id}>
                    <button
                      type="button"
                      onClick={() => onOpenNode(influencer.node_id)}
                      className="flex w-full items-start gap-3 rounded-[10px] border border-line bg-panel p-3.5 text-left transition-colors hover:border-[#BCC5CE] hover:bg-canvas"
                    >
                      <EntityIcon type={influencer.node_id} size={16} />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-semibold text-ink">
                          {influencer.label}
                        </span>
                        <span className="mt-0.5 block text-[13px] leading-6 text-muted">
                          {influencer.why}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>

            <section className="mt-7" aria-labelledby="communities-heading">
              <h3
                id="communities-heading"
                className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink"
              >
                <Users size={16} className="text-civic" />
                Groups in this case
              </h3>
              <ul className="grid gap-2 sm:grid-cols-2">
                {analytics.communities.map((community) => (
                  <li
                    key={community.cluster_id}
                    className="rounded-[10px] border border-line bg-panel p-3.5"
                  >
                    <p className="text-sm font-semibold text-ink">
                      Group {community.cluster_id.replace(/^c/, '')}
                    </p>
                    <p className="mt-1 text-xs text-muted">
                      {community.size} entities · {community.people.length} people
                    </p>
                    {community.people.length > 0 && (
                      <button
                        type="button"
                        className={`${quietButtonClass} mt-2.5`}
                        onClick={() =>
                          onShowPath(community.people, `Group ${community.cluster_id}`)
                        }
                      >
                        Show group
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </PanelBody>
    </PanelShell>
  )
}
