import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  ArrowRight,
  ChevronDown,
  CircleDot,
  FileText,
  FolderOpen,
  GitBranch,
  Menu,
  MoreHorizontal,
  Search,
  Trash2,
  UserRoundSearch,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { KeyboardEvent, MouseEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DeleteCaseDialog,
  EditCaseDialog,
  NewCaseDialog,
} from '../components/CaseDialogs'
import { Sidebar } from '../components/Sidebar'
import {
  loadAccessibilityPreferences,
  loadOfficerProfile,
  saveAccessibilityPreferences,
  saveOfficerProfile,
  type AccessibilityPreferences,
  type OfficerProfile,
} from '../config'
import { getCases, updateCase } from '../lib/api'
import { compactNumber, formatCaseDate, sentenceCase } from '../lib/format'
import type { CaseSummary } from '../types'

type ToastMessage = { id: number; message: string }

export function CasesPage() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [officer, setOfficer] = useState<OfficerProfile>(() => loadOfficerProfile())
  const [preferences, setPreferences] = useState<AccessibilityPreferences>(() =>
    loadAccessibilityPreferences(),
  )
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [toast, setToast] = useState<ToastMessage | null>(null)

  const casesQuery = useQuery({
    queryKey: ['cases', officer.id],
    queryFn: () => getCases(officer.id),
  })

  const caseTypes = useMemo(
    () =>
      Array.from(new Set((casesQuery.data ?? []).map((item) => item.case_type))).sort((a, b) =>
        a.localeCompare(b),
      ),
    [casesQuery.data],
  )

  const filteredCases = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return [...(casesQuery.data ?? [])]
      .sort((a, b) => new Date(b.updated).getTime() - new Date(a.updated).getTime())
      .filter((item) => {
        const matchesSearch =
          !normalizedSearch ||
          item.title.toLowerCase().includes(normalizedSearch) ||
          item.case_type.toLowerCase().includes(normalizedSearch)
        const matchesStatus = statusFilter === 'all' || item.status === statusFilter
        const matchesType = typeFilter === 'all' || item.case_type === typeFilter
        return matchesSearch && matchesStatus && matchesType
      })
  }, [casesQuery.data, search, statusFilter, typeFilter])

  const activeCases = filteredCases.filter((item) => item.status !== 'closed')
  const closedCases = filteredCases.filter((item) => item.status === 'closed')

  useEffect(() => {
    const root = document.documentElement
    root.dataset.textSize = preferences.textSize
    root.classList.toggle('caselens-increased-contrast', preferences.increasedContrast)
    root.classList.toggle('caselens-reduced-motion', preferences.reducedMotion)
  }, [preferences])

  function showToast(message: string) {
    setToast({ id: Date.now(), message })
  }

  function handleSettingsSave(
    nextOfficer: OfficerProfile,
    nextPreferences: AccessibilityPreferences,
  ) {
    saveOfficerProfile(nextOfficer)
    saveAccessibilityPreferences(nextPreferences)
    setOfficer(nextOfficer)
    setPreferences(nextPreferences)
    showToast('Officer settings saved')
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <Sidebar
        collapsed={sidebarCollapsed}
        mobileOpen={mobileNavOpen}
        officer={officer}
        preferences={preferences}
        onCollapseChange={setSidebarCollapsed}
        onMobileClose={() => setMobileNavOpen(false)}
        onSettingsSave={handleSettingsSave}
      />

      <div className="hidden h-16 items-center gap-3 border-b border-line bg-panel px-5 max-[899px]:flex">
        <button
          type="button"
          className="grid size-10 place-items-center rounded-lg border border-line-strong bg-white text-ink hover:bg-canvas"
          aria-label="Open navigation menu"
          onClick={() => {
            setSidebarCollapsed(false)
            setMobileNavOpen(true)
          }}
        >
          <Menu size={20} />
        </button>
        <span className="text-sm font-semibold text-ink">CaseLens</span>
        <span className="text-sm text-muted">/</span>
        <span className="text-sm text-muted">Cases</span>
      </div>

      <main
        className={`min-h-screen transition-[margin] duration-200 max-[899px]:ml-0 ${sidebarCollapsed ? 'ml-[72px]' : 'ml-[240px]'}`}
      >
        <div className="mx-auto w-full max-w-[1260px] px-8 pb-16 pt-9 max-[899px]:px-5 max-[899px]:pt-7 xl:px-12">
          <header className="flex items-start justify-between gap-8">
            <div>
              <p className="mb-2 text-sm font-medium text-civic">Investigation workspace</p>
              <h1 className="text-[30px] font-semibold leading-tight tracking-[-0.035em] text-ink">
                Cases
              </h1>
              <p className="mt-2 max-w-2xl text-[15px] leading-6 text-muted">
                Open a case to review its documents, connections and work with shikonye.
              </p>
            </div>
            <NewCaseDialog
              officer={officer}
              onCreated={(createdCase) => showToast(`${createdCase.title} created`)}
            />
          </header>

          <section aria-label="Case search and filters" className="mt-8 flex flex-wrap items-center gap-3">
            <label className="relative min-w-[300px] flex-1">
              <span className="sr-only">Search cases</span>
              <Search
                size={18}
                strokeWidth={1.8}
                className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
              />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by case title or type"
                className="h-11 w-full rounded-lg border border-line-strong bg-panel pl-10 pr-4 text-sm text-ink placeholder:text-subtle hover:border-[#AAB2BC]"
              />
            </label>
            <FilterSelect
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'All statuses' },
                { value: 'open', label: 'Active' },
                { value: 'paused', label: 'Paused' },
                { value: 'closed', label: 'Closed' },
              ]}
            />
            <FilterSelect
              label="Case type"
              value={typeFilter}
              onChange={setTypeFilter}
              options={[
                { value: 'all', label: 'All case types' },
                ...caseTypes.map((item) => ({ value: item, label: sentenceCase(item) })),
              ]}
            />
          </section>

          {casesQuery.isError && (
            <div role="alert" className="mt-7 flex items-start gap-3 rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-5">
              <AlertCircle size={20} className="mt-0.5 shrink-0 text-danger" />
              <div className="flex-1">
                <h2 className="text-sm font-semibold text-ink">Case service is unavailable</h2>
                <p className="mt-1 text-sm leading-6 text-muted">
                  Your workspace is still available. Reconnect to load the latest case information.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void casesQuery.refetch()}
                className="h-9 rounded-lg border border-line-strong bg-white px-3.5 text-sm font-semibold text-ink hover:bg-canvas"
              >
                Retry
              </button>
            </div>
          )}

          <section className="mt-8" aria-labelledby="active-cases-heading">
            <div className="mb-3 flex items-center justify-between">
              <h2 id="active-cases-heading" className="text-sm font-semibold text-ink">
                Active cases
              </h2>
              {!casesQuery.isLoading && (
                <span className="text-xs font-medium text-muted">
                  {activeCases.length} {activeCases.length === 1 ? 'case' : 'cases'}
                </span>
              )}
            </div>

            {casesQuery.isLoading ? (
              <CasesSkeleton />
            ) : activeCases.length > 0 ? (
              <div className="space-y-3">
                {activeCases.map((caseItem) => (
                  <CaseCard caseItem={caseItem} key={caseItem.case_id} onToast={showToast} />
                ))}
              </div>
            ) : !casesQuery.isError ? (
              <EmptyCases hasFilters={Boolean(search || statusFilter !== 'all' || typeFilter !== 'all')} />
            ) : null}
          </section>

          {closedCases.length > 0 && (
            <details className="mt-7 overflow-hidden rounded-[10px] border border-line bg-panel">
              <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 text-sm font-semibold text-ink">
                <span>Closed Cases ({closedCases.length})</span>
                <ChevronDown size={18} className="text-muted" />
              </summary>
              <div className="space-y-3 border-t border-line bg-canvas/50 p-3">
                {closedCases.map((caseItem) => (
                  <CaseCard caseItem={caseItem} key={caseItem.case_id} onToast={showToast} />
                ))}
              </div>
            </details>
          )}
        </div>
      </main>

      {toast && <Toast key={toast.id} message={toast.message} onDismiss={() => setToast(null)} />}
    </div>
  )
}

interface CaseCardProps {
  caseItem: CaseSummary
  onToast: (message: string) => void
}

function CaseCard({ caseItem, onToast }: CaseCardProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const statusMutation = useMutation({
    mutationFn: (status: CaseSummary['status']) => updateCase(caseItem.case_id, { status }),
    onSuccess: async (_, status) => {
      await queryClient.invalidateQueries({ queryKey: ['cases'] })
      onToast(status === 'closed' ? 'Case moved to Closed Cases' : 'Case status updated')
    },
    onError: () => onToast('The case status could not be changed. Try again.'),
  })

  function openCase() {
    navigate(`/cases/${encodeURIComponent(caseItem.case_id)}`)
  }

  function stopCardAction(event: MouseEvent) {
    event.stopPropagation()
  }

  function handleCardKey(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openCase()
    }
  }

  return (
    <>
      <article
        role="link"
        tabIndex={0}
        onClick={openCase}
        onKeyDown={handleCardKey}
        className="group cursor-pointer rounded-[10px] border border-line bg-panel p-5 transition-[border-color,background-color] duration-150 hover:border-[#BCC5CE] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-civic"
        aria-label={`Open ${caseItem.title}`}
      >
        <div className="flex items-start gap-5">
          <div className="grid size-11 shrink-0 place-items-center rounded-lg border border-[#CDDAE6] bg-civic-soft text-civic">
            <FolderOpen size={21} strokeWidth={1.8} />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-5">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2.5">
                  <h3 className="truncate text-[17px] font-semibold tracking-[-0.015em] text-ink">
                    {caseItem.title}
                  </h3>
                  <StatusBadge status={caseItem.status} />
                </div>
                <p className="mt-1.5 text-sm text-muted">{sentenceCase(caseItem.case_type)}</p>
              </div>

              <div onClick={stopCardAction}>
                <DropdownMenu.Root>
                  <DropdownMenu.Trigger asChild>
                    <button
                      type="button"
                      className="grid size-9 place-items-center rounded-lg text-muted hover:bg-canvas hover:text-ink"
                      aria-label={`More actions for ${caseItem.title}`}
                    >
                      <MoreHorizontal size={20} />
                    </button>
                  </DropdownMenu.Trigger>
                  <DropdownMenu.Portal>
                    <DropdownMenu.Content
                      align="end"
                      sideOffset={6}
                      className="z-50 min-w-[190px] rounded-lg border border-line bg-panel p-1.5 shadow-[0_14px_35px_rgba(32,37,43,0.12)]"
                    >
                      <MenuItem onSelect={() => setEditOpen(true)}>Edit case</MenuItem>
                      {caseItem.status !== 'paused' && caseItem.status !== 'closed' && (
                        <MenuItem onSelect={() => statusMutation.mutate('paused')}>
                          Pause case
                        </MenuItem>
                      )}
                      {caseItem.status === 'paused' && (
                        <MenuItem onSelect={() => statusMutation.mutate('open')}>
                          Mark active
                        </MenuItem>
                      )}
                      {caseItem.status !== 'closed' && (
                        <MenuItem onSelect={() => statusMutation.mutate('closed')}>
                          Close case
                        </MenuItem>
                      )}
                      <DropdownMenu.Separator className="my-1 h-px bg-line" />
                      <DropdownMenu.Item
                        onSelect={() => setDeleteOpen(true)}
                        className="flex h-9 cursor-pointer select-none items-center gap-2 rounded-md px-2.5 text-sm text-danger outline-none hover:bg-danger-soft focus:bg-danger-soft"
                      >
                        <Trash2 size={16} />
                        Delete case
                      </DropdownMenu.Item>
                    </DropdownMenu.Content>
                  </DropdownMenu.Portal>
                </DropdownMenu.Root>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-x-5 gap-y-3 border-t border-line pt-4 sm:grid-cols-4">
              <CaseMetric icon={<FileText size={17} />} value={caseItem.counts.documents} label="Documents" />
              <CaseMetric icon={<CircleDot size={17} />} value={caseItem.counts.nodes} label="Entities" />
              <CaseMetric icon={<GitBranch size={17} />} value={caseItem.counts.edges} label="Connections" />
              <CaseMetric
                icon={<UserRoundSearch size={17} />}
                value={caseItem.open_questions}
                label="Open questions"
              />
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
              <p className="text-xs text-muted">Recent activity: {formatCaseDate(caseItem.updated)}</p>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation()
                  openCase()
                }}
                className="inline-flex h-9 items-center gap-2 rounded-lg border border-line-strong bg-white px-3.5 text-sm font-semibold text-civic transition-colors group-hover:border-[#AAB7C3] hover:bg-civic-soft"
              >
                Open Case
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </article>

      {editOpen && (
        <EditCaseDialog
          caseItem={caseItem}
          open={editOpen}
          onOpenChange={setEditOpen}
          onSaved={() => onToast('Case details saved')}
        />
      )}
      {deleteOpen && (
        <DeleteCaseDialog
          caseItem={caseItem}
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          onDeleted={() => onToast('Case deleted')}
        />
      )}
    </>
  )
}

function StatusBadge({ status }: { status: CaseSummary['status'] }) {
  const config = {
    open: { label: 'Active', className: 'border-[#B9D6C8] bg-success-soft text-success' },
    paused: { label: 'Paused', className: 'border-[#E9D1A8] bg-warning-soft text-warning' },
    closed: { label: 'Closed', className: 'border-line-strong bg-canvas text-muted' },
  }[status]

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${config.className}`}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {config.label}
    </span>
  )
}

interface CaseMetricProps {
  icon: React.ReactNode
  value: number
  label: string
}

function CaseMetric({ icon, value, label }: CaseMetricProps) {
  return (
    <div className="flex items-center gap-2.5 text-muted">
      <span className="text-civic">{icon}</span>
      <span>
        <span className="block text-sm font-semibold text-ink">{compactNumber(value)}</span>
        <span className="block text-[11px] font-medium text-muted">{label}</span>
      </span>
    </div>
  )
}

interface MenuItemProps {
  children: React.ReactNode
  onSelect: () => void
}

function MenuItem({ children, onSelect }: MenuItemProps) {
  return (
    <DropdownMenu.Item
      onSelect={onSelect}
      className="flex h-9 cursor-pointer select-none items-center rounded-md px-2.5 text-sm text-ink outline-none hover:bg-canvas focus:bg-canvas"
    >
      {children}
    </DropdownMenu.Item>
  )
}

interface FilterSelectProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: Array<{ value: string; label: string }>
}

function FilterSelect({ label, value, onChange, options }: FilterSelectProps) {
  return (
    <label>
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 min-w-[150px] rounded-lg border border-line-strong bg-panel px-3.5 pr-9 text-sm font-medium text-ink hover:border-[#AAB2BC]"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function CasesSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading cases">
      {[0, 1].map((item) => (
        <div key={item} className="animate-pulse rounded-[10px] border border-line bg-panel p-5">
          <div className="flex gap-5">
            <div className="size-11 rounded-lg bg-[#EDF0F3]" />
            <div className="flex-1">
              <div className="h-5 w-2/5 rounded bg-[#E7EAEE]" />
              <div className="mt-3 h-4 w-1/5 rounded bg-[#EEF0F2]" />
              <div className="mt-6 h-px bg-line" />
              <div className="mt-4 grid grid-cols-4 gap-4">
                {[0, 1, 2, 3].map((metric) => (
                  <div key={metric} className="h-9 rounded bg-[#F0F2F4]" />
                ))}
              </div>
            </div>
          </div>
        </div>
      ))}
      <p className="pt-1 text-center text-xs text-muted">Loading current case information...</p>
    </div>
  )
}

function EmptyCases({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="rounded-[10px] border border-dashed border-line-strong bg-panel px-6 py-12 text-center">
      <div className="mx-auto grid size-11 place-items-center rounded-lg bg-civic-soft text-civic">
        {hasFilters ? <Search size={20} /> : <FolderOpen size={20} />}
      </div>
      <h3 className="mt-4 text-base font-semibold text-ink">
        {hasFilters ? 'No cases match these filters' : 'No active cases yet'}
      </h3>
      <p className="mx-auto mt-1 max-w-md text-sm leading-6 text-muted">
        {hasFilters
          ? 'Change the search or filter choices to see more cases.'
          : 'Create a case, then add documents for shikonye to analyze.'}
      </p>
    </div>
  )
}

function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  const [paused, setPaused] = useState(false)
  const [remaining, setRemaining] = useState(4000)

  useEffect(() => {
    if (paused) return undefined
    const started = Date.now()
    const timer = window.setTimeout(onDismiss, remaining)
    return () => {
      window.clearTimeout(timer)
      setRemaining((current) => Math.max(0, current - (Date.now() - started)))
    }
  }, [onDismiss, paused, remaining])

  return (
    <div
      role="status"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className="fixed bottom-6 right-6 z-[70] flex min-w-[280px] items-center gap-3 rounded-[10px] border border-line bg-panel px-4 py-3 text-sm font-medium text-ink shadow-[0_12px_35px_rgba(32,37,43,0.12)]"
    >
      <span className="grid size-7 place-items-center rounded-full bg-success-soft text-success">✓</span>
      {message}
    </div>
  )
}
