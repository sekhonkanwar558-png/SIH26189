import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  ArrowLeft,
  FileText,
  Lightbulb,
  Menu,
  MessageSquareText,
  Network,
  NotebookPen,
  ShieldCheck,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Sidebar, type SidebarNavItem } from '../components/Sidebar'
import { Connections } from '../components/workspace/Connections'
import { CustodyPanel } from '../components/workspace/CustodyPanel'
import { DocumentsPanel } from '../components/workspace/DocumentsPanel'
import { FindingsPanel } from '../components/workspace/FindingsPanel'
import { MemoryPanel } from '../components/workspace/MemoryPanel'
import { NodeDrawer } from '../components/workspace/NodeDrawer'
import { PanelBoundary } from '../components/workspace/PanelBoundary'
import { Shikonye } from '../components/workspace/Shikonye'
import { SourceDialog, type SourceRequest } from '../components/workspace/SourceDialog'
import {
  loadAccessibilityPreferences,
  loadOfficerProfile,
  saveAccessibilityPreferences,
  saveOfficerProfile,
  type AccessibilityPreferences,
  type OfficerProfile,
} from '../config'
import { getAnalytics, getCase, getGraph, getHealth, getPath } from '../lib/api'
import { useConversation } from '../lib/conversation'
import { compactNumber, sentenceCase } from '../lib/format'
import { chipClass, quietButtonClass, TABLET_BREAKPOINT } from '../lib/ui'

type Section = 'shikonye' | 'documents' | 'connections' | 'findings' | 'memory' | 'custody'
type Focus = 'none' | 'left' | 'right'

/** §3.5a — the assistant may take between 40% and 75% of the split. */
const MIN_LEFT = 40
const MAX_LEFT = 75
const SPLIT_KEY = 'caselens.split'
/** Docked entity-details column. Fixed, so the split can be computed around it. */
const DRAWER_PX = 360

export function Workspace() {
  const { caseId = '' } = useParams()

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [officer, setOfficer] = useState<OfficerProfile>(() => loadOfficerProfile())
  const [preferences, setPreferences] = useState<AccessibilityPreferences>(() =>
    loadAccessibilityPreferences(),
  )
  const [section, setSection] = useState<Section>('shikonye')
  const [focus, setFocus] = useState<Focus>('none')
  const [leftWidth, setLeftWidth] = useState(() => readSplit())
  const [tabletTab, setTabletTab] = useState<'panel' | 'connections'>('panel')
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [source, setSource] = useState<SourceRequest | null>(null)
  const [highlight, setHighlight] = useState<{ path: string[]; label: string }>({
    path: [],
    label: '',
  })
  const [toast, setToast] = useState<{ id: number; message: string } | null>(null)
  const [traceFrom, setTraceFrom] = useState<{ id: string; label: string } | null>(null)
  const [tracing, setTracing] = useState(false)
  const [isTablet, setIsTablet] = useState(
    () => typeof window !== 'undefined' && window.innerWidth < TABLET_BREAKPOINT,
  )

  const splitRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  const conversation = useConversation(caseId)

  const caseQuery = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => getCase(caseId),
    enabled: Boolean(caseId),
  })
  const graphQuery = useQuery({
    queryKey: ['graph', caseId],
    queryFn: () => getGraph(caseId, true),
    enabled: Boolean(caseId),
  })
  const analyticsQuery = useQuery({
    queryKey: ['analytics', caseId],
    queryFn: () => getAnalytics(caseId, 'betweenness', 8),
    enabled: Boolean(caseId),
  })
  const healthQuery = useQuery({ queryKey: ['health'], queryFn: getHealth, staleTime: 60_000 })

  useEffect(() => {
    const root = document.documentElement
    root.dataset.textSize = preferences.textSize
    root.classList.toggle('caselens-increased-contrast', preferences.increasedContrast)
    root.classList.toggle('caselens-reduced-motion', preferences.reducedMotion)
  }, [preferences])

  useEffect(() => {
    const onResize = () => setIsTablet(window.innerWidth < TABLET_BREAKPOINT)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // ------------------------------------------------------------ the divider
  useEffect(() => {
    function onMove(event: MouseEvent) {
      if (!draggingRef.current || !splitRef.current) return
      const bounds = splitRef.current.getBoundingClientRect()
      const percent = ((event.clientX - bounds.left) / bounds.width) * 100
      setLeftWidth(Math.min(MAX_LEFT, Math.max(MIN_LEFT, percent)))
    }
    function onUp() {
      if (!draggingRef.current) return
      draggingRef.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  useEffect(() => {
    try {
      window.localStorage.setItem(SPLIT_KEY, String(Math.round(leftWidth)))
    } catch {
      // The split just falls back to 60% next time.
    }
  }, [leftWidth])

  function onDividerKey(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      setLeftWidth((width) => Math.max(MIN_LEFT, width - 2))
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault()
      setLeftWidth((width) => Math.min(MAX_LEFT, width + 2))
    }
  }

  // ------------------------------------------------------------- callbacks
  // Memoised: Connections rebuilds its Cytoscape instance when this identity
  // changes, so a fresh function every render would destroy the canvas.
  const openNode = useCallback((nodeId: string) => {
    setSelectedNode(nodeId)
    if (window.innerWidth < TABLET_BREAKPOINT) setTabletTab('connections')
  }, [])

  const showPath = useCallback((path: string[], label: string) => {
    setHighlight({ path, label })
    if (window.innerWidth < TABLET_BREAKPOINT) setTabletTab('connections')
    setFocus((current) => (current === 'left' ? 'none' : current))
  }, [])

  const clearPath = useCallback(() => setHighlight({ path: [], label: '' }), [])

  /**
   * "How is this person connected to that account?" asked directly on the
   * graph — the same question as demo query 1, and the reason `/path` exists.
   * Two steps rather than a picker: the officer is already clicking entities.
   */
  const runTrace = useCallback(
    async (toId: string, toLabel: string) => {
      if (!traceFrom) return
      setTracing(true)
      try {
        const routes = await getPath(caseId, traceFrom.id, toId)
        if (routes.length === 0) {
          setToast({
            id: Date.now(),
            message: `No route links ${traceFrom.label} to ${toLabel} in this case`,
          })
        } else {
          const best = routes[0]
          setHighlight({ path: best.path, label: `${traceFrom.label} → ${toLabel}` })
          if (window.innerWidth < TABLET_BREAKPOINT) setTabletTab('connections')
          setFocus((current) => (current === 'left' ? 'none' : current))
        }
      } catch {
        setToast({ id: Date.now(), message: 'That route could not be worked out. Try again.' })
      }
      setTracing(false)
      setTraceFrom(null)
    },
    [caseId, traceFrom],
  )

  const showToast = useCallback((message: string) => {
    setToast({ id: Date.now(), message })
  }, [])

  useEffect(() => {
    if (!toast) return undefined
    const timer = window.setTimeout(() => setToast(null), 4_000)
    return () => window.clearTimeout(timer)
  }, [toast])

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

  function selectSection(next: Section) {
    setSection(next)
    setMobileNavOpen(false)
    if (next === 'connections') {
      setFocus('right')
      setTabletTab('connections')
      return
    }
    setFocus('none')
    setTabletTab('panel')
  }

  const navItems: SidebarNavItem[] = useMemo(
    () => [
      { key: 'shikonye', label: 'shikonye', icon: <MessageSquareText size={19} strokeWidth={1.8} /> },
      { key: 'documents', label: 'Documents', icon: <FileText size={19} strokeWidth={1.8} /> },
      { key: 'connections', label: 'Connections', icon: <Network size={19} strokeWidth={1.8} /> },
      { key: 'findings', label: 'Findings', icon: <Lightbulb size={19} strokeWidth={1.8} /> },
      { key: 'memory', label: 'Memory', icon: <NotebookPen size={19} strokeWidth={1.8} /> },
      { key: 'custody', label: 'Custody', icon: <ShieldCheck size={19} strokeWidth={1.8} /> },
    ],
    [],
  ).map((item) => ({
    ...item,
    active: section === item.key,
    onSelect: () => selectSection(item.key as Section),
  }))

  const caseDetail = caseQuery.data
  const activeLabel = navItems.find((item) => item.key === section)?.label ?? 'shikonye'
  const leftPanel = (
    <PanelBoundary label={activeLabel}>{renderLeftPanel()}</PanelBoundary>
  )

  function renderLeftPanel() {
    const focused = focus === 'left'
    const onFocusToggle = () => setFocus(focused ? 'none' : 'left')

    switch (section) {
      case 'documents':
        return (
          <DocumentsPanel
            caseId={caseId}
            officerId={officer.id}
            onOpenSource={setSource}
            onToast={showToast}
            focused={focused}
            onFocusToggle={onFocusToggle}
          />
        )
      case 'findings':
        return (
          <FindingsPanel
            caseId={caseId}
            onShowPath={showPath}
            onOpenNode={openNode}
            onInvestigated={(question, answer) => {
              conversation.pushOfficer(question)
              conversation.pushAnswer(question, answer)
            }}
            onToast={showToast}
            focused={focused}
            onFocusToggle={onFocusToggle}
          />
        )
      case 'memory':
        return (
          <MemoryPanel
            caseId={caseId}
            onShowPath={showPath}
            onToast={showToast}
            focused={focused}
            onFocusToggle={onFocusToggle}
          />
        )
      case 'custody':
        return <CustodyPanel caseId={caseId} focused={focused} onFocusToggle={onFocusToggle} />
      default:
        return (
          <Shikonye
            caseId={caseId}
            officerId={officer.id}
            conversation={conversation}
            graph={graphQuery.data}
            modelAvailable={healthQuery.data?.model_available ?? false}
            activePath={highlight.path}
            onShowPath={showPath}
            onOpenNode={openNode}
            onOpenSource={setSource}
            onOpenFindings={() => selectSection('findings')}
            focused={focused}
            onFocusToggle={onFocusToggle}
          />
        )
    }
  }

  const connections = (
    <PanelBoundary label="Connections">
      <Connections
        caseId={caseId}
        graph={graphQuery.data}
        communities={analyticsQuery.data?.communities ?? []}
        isLoading={graphQuery.isLoading}
        isError={graphQuery.isError}
        onRetry={() => void graphQuery.refetch()}
        highlightPath={highlight.path}
        highlightLabel={highlight.label || null}
        onClearPath={clearPath}
        onSelectNode={openNode}
        selectedNodeId={selectedNode}
        reducedMotion={preferences.reducedMotion}
        focused={focus === 'right'}
        onFocusToggle={() => setFocus(focus === 'right' ? 'none' : 'right')}
      />
    </PanelBoundary>
  )

  return (
    <div className="h-screen overflow-hidden bg-canvas text-ink">
      <Sidebar
        collapsed={sidebarCollapsed}
        mobileOpen={mobileNavOpen}
        officer={officer}
        preferences={preferences}
        onCollapseChange={setSidebarCollapsed}
        onMobileClose={() => setMobileNavOpen(false)}
        onSettingsSave={handleSettingsSave}
        items={navItems}
        aboveNav={
          <Link
            to="/"
            className="flex h-10 w-full items-center gap-2.5 rounded-lg px-3 text-sm font-medium text-muted transition-colors hover:bg-canvas hover:text-ink"
          >
            <ArrowLeft size={17} />
            Back to Cases
          </Link>
        }
      />

      <div
        className={`flex h-screen flex-col transition-[margin] duration-200 max-[899px]:ml-0 ${
          sidebarCollapsed ? 'ml-[72px]' : 'ml-[240px]'
        }`}
      >
        <header className="flex shrink-0 items-center gap-3 border-b border-line bg-panel px-5 py-3">
          <button
            type="button"
            className="hidden size-10 shrink-0 place-items-center rounded-lg border border-line-strong bg-white text-ink hover:bg-canvas max-[899px]:grid"
            aria-label="Open navigation menu"
            onClick={() => {
              setSidebarCollapsed(false)
              setMobileNavOpen(true)
            }}
          >
            <Menu size={20} />
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="truncate text-[17px] font-semibold tracking-[-0.02em] text-ink">
                {caseDetail?.title ?? (caseQuery.isLoading ? 'Loading case...' : caseId)}
              </h1>
              {caseDetail && (
                <>
                  <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
                    {sentenceCase(caseDetail.case_type)}
                  </span>
                  {caseDetail.custody.valid ? (
                    <span className={`${chipClass} border-[#B9D6C8] bg-success-soft text-success`}>
                      <ShieldCheck size={13} />
                      Record intact
                    </span>
                  ) : (
                    <span className={`${chipClass} border-[#E7C7C7] bg-danger-soft text-danger`}>
                      <AlertCircle size={13} />
                      Record altered
                    </span>
                  )}
                </>
              )}
            </div>
            {caseDetail && (
              <p className="mt-0.5 truncate text-xs text-muted">
                {compactNumber(caseDetail.counts.nodes)} entities ·{' '}
                {compactNumber(caseDetail.counts.edges)} connections ·{' '}
                {caseDetail.counts.documents} documents
              </p>
            )}
          </div>

          {focus !== 'none' && (
            <button type="button" className={quietButtonClass} onClick={() => setFocus('none')}>
              Exit focus
            </button>
          )}
        </header>

        {caseQuery.isError && (
          <div
            role="alert"
            className="m-5 flex items-start gap-3 rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-5"
          >
            <AlertCircle size={20} className="mt-0.5 shrink-0 text-danger" />
            <div className="flex-1">
              <h2 className="text-sm font-semibold text-ink">This case could not be opened</h2>
              <p className="mt-1 text-sm leading-6 text-muted">
                It may have been deleted, or the case service is unavailable.
              </p>
            </div>
            <Link to="/" className={quietButtonClass}>
              Back to Cases
            </Link>
          </div>
        )}

        {isTablet ? (
          <>
            <div
              className="flex shrink-0 gap-1 border-b border-line bg-panel px-3 py-2"
              role="tablist"
              aria-label="Workspace panels"
            >
              <TabButton
                active={tabletTab === 'panel'}
                onClick={() => setTabletTab('panel')}
                label={activeLabel}
              />
              <TabButton
                active={tabletTab === 'connections'}
                onClick={() => setTabletTab('connections')}
                label="Connections"
              />
            </div>
            <main className="relative min-h-0 flex-1">
              {tabletTab === 'panel' ? leftPanel : connections}
              <NodeDrawer
                caseId={caseId}
                nodeId={selectedNode}
                onClose={() => setSelectedNode(null)}
                onSelectNode={openNode}
                onOpenSource={setSource}
                onTraceFrom={(nodeId, label) => setTraceFrom({ id: nodeId, label })}
                onTraceTo={(nodeId, label) => void runTrace(nodeId, label)}
                onCancelTrace={() => setTraceFrom(null)}
                traceFrom={traceFrom}
                tracing={tracing}
              />
            </main>
          </>
        ) : (
          <main ref={splitRef} className="relative flex min-h-0 flex-1">
            {focus !== 'right' && (
              <div
                className="min-w-0 border-r border-line"
                style={{
                  width:
                    focus === 'left'
                      ? '100%'
                      : selectedNode
                        // The drawer is a real column, so the split is taken over
                        // what is left after it. Without this the graph — already
                        // the smaller half — absorbs the whole drawer and ends up
                        // a sliver, which is the one panel the officer opened an
                        // entity to look at.
                        ? `calc((100% - ${DRAWER_PX}px) * ${leftWidth / 100})`
                        : `${leftWidth}%`,
                }}
              >
                {leftPanel}
              </div>
            )}

            {focus === 'none' && section !== 'connections' && (
              <div
                role="separator"
                aria-orientation="vertical"
                aria-label="Resize the panels"
                aria-valuenow={Math.round(leftWidth)}
                aria-valuemin={MIN_LEFT}
                aria-valuemax={MAX_LEFT}
                tabIndex={0}
                onKeyDown={onDividerKey}
                onMouseDown={() => {
                  draggingRef.current = true
                  document.body.style.cursor = 'col-resize'
                  document.body.style.userSelect = 'none'
                }}
                className="group relative z-10 -ml-[3px] w-[6px] shrink-0 cursor-col-resize bg-transparent"
              >
                <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-transparent transition-colors group-hover:bg-civic group-focus-visible:bg-civic" />
              </div>
            )}

            {focus !== 'left' && <div className="min-w-0 flex-1">{connections}</div>}

            {selectedNode && (
              <div className="shrink-0" style={{ width: DRAWER_PX }}>
                <NodeDrawer
                  caseId={caseId}
                  nodeId={selectedNode}
                  onClose={() => setSelectedNode(null)}
                  onSelectNode={openNode}
                  onOpenSource={setSource}
                  onTraceFrom={(nodeId, label) => setTraceFrom({ id: nodeId, label })}
                  onTraceTo={(nodeId, label) => void runTrace(nodeId, label)}
                  onCancelTrace={() => setTraceFrom(null)}
                  traceFrom={traceFrom}
                  tracing={tracing}
                  variant="panel"
                />
              </div>
            )}
          </main>
        )}
      </div>

      <SourceDialog
        caseId={caseId}
        request={source}
        onOpenChange={(open) => {
          if (!open) setSource(null)
        }}
      />

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-[70] flex min-w-[280px] items-center gap-3 rounded-[10px] border border-line bg-panel px-4 py-3 text-sm font-medium text-ink shadow-[0_12px_35px_rgba(32,37,43,0.12)]"
        >
          <span className="grid size-7 place-items-center rounded-full bg-success-soft text-success">
            ✓
          </span>
          {toast.message}
        </div>
      )}
    </div>
  )
}

function TabButton({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`h-10 flex-1 rounded-lg text-sm font-semibold transition-colors ${
        active ? 'bg-civic-soft text-civic' : 'text-muted hover:bg-canvas hover:text-ink'
      }`}
    >
      {label}
    </button>
  )
}

function readSplit() {
  try {
    const saved = Number(window.localStorage.getItem(SPLIT_KEY))
    if (Number.isFinite(saved) && saved >= MIN_LEFT && saved <= MAX_LEFT) return saved
  } catch {
    // Fall through to the default split.
  }
  return 60
}
