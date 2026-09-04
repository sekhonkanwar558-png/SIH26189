import { ArrowLeft, MessageSquareText, Network } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { BrandMark } from '../components/BrandMark'

export function WorkspacePreview() {
  const { caseId } = useParams()

  return (
    <div className="min-h-screen bg-canvas p-6 text-ink">
      <header className="mx-auto flex max-w-5xl items-center justify-between rounded-[10px] border border-line bg-panel px-5 py-4">
        <div className="flex items-center gap-3">
          <BrandMark size={32} />
          <div>
            <p className="text-sm font-semibold">CaseLens</p>
            <p className="text-xs text-muted">{caseId}</p>
          </div>
        </div>
        <Link
          to="/"
          className="inline-flex h-10 items-center gap-2 rounded-lg border border-line-strong bg-white px-3.5 text-sm font-semibold text-ink hover:bg-canvas"
        >
          <ArrowLeft size={17} />
          Back to Cases
        </Link>
      </header>
      <main className="mx-auto mt-5 grid min-h-[620px] max-w-5xl grid-cols-[3fr_2fr] overflow-hidden rounded-[10px] border border-line bg-panel">
        <section className="flex items-center justify-center border-r border-line p-10 text-center">
          <div>
            <MessageSquareText className="mx-auto text-civic" size={28} strokeWidth={1.7} />
            <h1 className="mt-4 text-xl font-semibold">shikonye workspace</h1>
            <p className="mt-2 max-w-sm text-sm leading-6 text-muted">
              The case list is now live. Chat and evidence behavior are the next implementation milestone.
            </p>
          </div>
        </section>
        <section className="flex items-center justify-center bg-[#FCFDFE] p-10 text-center">
          <div>
            <Network className="mx-auto text-evidence" size={28} strokeWidth={1.7} />
            <h2 className="mt-4 text-xl font-semibold">Connections</h2>
            <p className="mt-2 text-sm leading-6 text-muted">The live case graph will appear here.</p>
          </div>
        </section>
      </main>
    </div>
  )
}
