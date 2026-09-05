import { AlertCircle } from 'lucide-react'
import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { quietButtonClass } from '../../lib/ui'

interface PanelBoundaryProps {
  /** Named in the fallback, so the officer knows which half stopped working. */
  label: string
  children: ReactNode
}

interface PanelBoundaryState {
  error: Error | null
}

/**
 * One panel failing must not take the workspace with it.
 *
 * This exists because it already happened: a case with no documents returns a
 * briefing with no verification block, the answer card read through it, and the
 * entire screen went white — no case, no graph, no way back. On a demo machine
 * that is the whole product gone. A contained failure keeps the other panel,
 * the case header and the navigation alive.
 */
export class PanelBoundary extends Component<PanelBoundaryProps, PanelBoundaryState> {
  state: PanelBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): PanelBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Kept in the console rather than shown: the officer needs to know that
    // this panel failed, not what the stack was.
    console.error(`CaseLens: the ${this.props.label} panel failed`, error, info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="flex h-full min-h-0 items-center justify-center bg-canvas p-6">
        <div
          role="alert"
          className="max-w-sm rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-5 text-center"
        >
          <AlertCircle size={22} className="mx-auto text-danger" />
          <h2 className="mt-3 text-sm font-semibold text-ink">
            The {this.props.label} panel stopped working
          </h2>
          <p className="mt-1.5 text-sm leading-6 text-muted">
            The rest of this case is unaffected — the graph, the documents and the custody record
            are all still there.
          </p>
          <button
            type="button"
            className={`${quietButtonClass} mt-4`}
            onClick={() => this.setState({ error: null })}
          >
            Try this panel again
          </button>
        </div>
      </div>
    )
  }
}
