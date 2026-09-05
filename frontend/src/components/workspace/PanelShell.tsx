import { Maximize2, Minimize2 } from 'lucide-react'
import { iconButtonClass } from '../../lib/ui'

/**
 * The frame every left-hand section shares — Documents, Findings, Memory and
 * Custody. Keeping it in one place is what stops four panels drifting into
 * four slightly different headers.
 */

export function PanelShell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="flex h-full min-h-0 flex-col bg-panel" aria-label={label}>
      {children}
    </section>
  )
}

interface PanelHeaderProps {
  title: string
  focused: boolean
  onFocusToggle: () => void
  children?: React.ReactNode
}

export function PanelHeader({ title, focused, onFocusToggle, children }: PanelHeaderProps) {
  return (
    <header className="flex items-center gap-3 border-b border-line px-4 py-3">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {children}
      <button
        type="button"
        className={`${iconButtonClass} ml-auto`}
        onClick={onFocusToggle}
        aria-label={focused ? 'Exit focus mode' : `Focus the ${title} panel`}
        title={focused ? 'Exit focus mode' : 'Focus'}
      >
        {focused ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
      </button>
    </header>
  )
}

export function PanelBody({ children }: { children: React.ReactNode }) {
  return <div className="min-h-0 flex-1 overflow-y-auto bg-canvas p-4">{children}</div>
}
