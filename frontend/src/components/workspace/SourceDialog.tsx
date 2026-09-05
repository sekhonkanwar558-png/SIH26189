import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, FileText, X } from 'lucide-react'
import { getSource } from '../../lib/api'
import { documentKindLabel } from '../../lib/documents'
import { formatBytes } from '../../lib/format'
import { chipClass } from '../../lib/ui'

export interface SourceRequest {
  docId: string
  start?: number
  end?: number
  /** What the officer clicked, so the dialog can say why it opened. */
  context?: string
}

interface SourceDialogProps {
  caseId: string
  request: SourceRequest | null
  onOpenChange: (open: boolean) => void
}

/**
 * A citation is only worth something if it opens. This is the other end of
 * every cited node, edge and finding in the workspace: the original text the
 * fact was read out of, with the exact span the backend recorded marked in it.
 */
export function SourceDialog({ caseId, request, onOpenChange }: SourceDialogProps) {
  const query = useQuery({
    queryKey: ['source', caseId, request?.docId, request?.start, request?.end],
    queryFn: () => getSource(caseId, request!.docId, request?.start, request?.end),
    enabled: Boolean(request),
  })

  const excerpt = query.data

  return (
    <Dialog.Root open={Boolean(request)} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[#20252B]/25" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100vh-48px)] w-[calc(100%-32px)] max-w-[720px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[10px] border border-line bg-panel shadow-[0_24px_70px_rgba(32,37,43,0.16)] focus:outline-none">
          <div className="flex items-start justify-between gap-5 border-b border-line p-6">
            <div className="min-w-0">
              <Dialog.Title className="flex items-center gap-2.5 text-lg font-semibold tracking-[-0.02em] text-ink">
                <FileText size={19} className="shrink-0 text-civic" strokeWidth={1.8} />
                <span className="truncate">{excerpt?.filename ?? 'Source document'}</span>
              </Dialog.Title>
              <Dialog.Description className="mt-1.5 text-sm leading-6 text-muted">
                {request?.context
                  ? `The text behind ${request.context}.`
                  : 'The original text this fact was read from.'}
              </Dialog.Description>
              {excerpt && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
                    {documentKindLabel(excerpt.kind)}
                  </span>
                  <span className={`${chipClass} border-[#E4D3AF] bg-evidence-soft text-[#8A5F16]`}>
                    Characters {excerpt.start}–{excerpt.end}
                  </span>
                </div>
              )}
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                className="grid size-9 shrink-0 place-items-center rounded-lg border border-line text-muted hover:bg-canvas hover:text-ink"
                aria-label="Close source document"
              >
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-6">
            {query.isLoading && (
              <div className="animate-pulse space-y-2.5" aria-label="Loading source text">
                {[0, 1, 2, 3, 4].map((row) => (
                  <div key={row} className="h-4 rounded bg-[#EEF0F2]" style={{ width: `${92 - row * 7}%` }} />
                ))}
              </div>
            )}

            {query.isError && (
              <div role="alert" className="flex items-start gap-3 rounded-lg border border-[#E6C0C0] bg-danger-soft p-4">
                <AlertCircle size={18} className="mt-0.5 shrink-0 text-danger" />
                <div>
                  <p className="text-sm font-semibold text-ink">This source could not be opened</p>
                  <p className="mt-1 text-sm leading-6 text-muted">
                    The document is recorded in the case but its extracted text could not be read.
                  </p>
                </div>
              </div>
            )}

            {excerpt && <Excerpt text={excerpt.text} start={excerpt.start} end={excerpt.end} />}
          </div>

          {excerpt && (
            <div className="border-t border-line px-6 py-3.5 text-xs text-muted">
              {formatBytes(excerpt.text.length)} shown · highlighted span is exactly what the
              extraction recorded, with surrounding lines for context.
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

/**
 * The backend returns the cited span padded by 160 characters either side, so
 * the citation always arrives inside a readable sentence. That padding is what
 * puts the span at this offset inside the returned text.
 */
function Excerpt({ text, start, end }: { text: string; start: number; end: number }) {
  const offset = Math.min(start, 160)
  const length = Math.max(0, end - start)
  const hasSpan = length > 0 && offset + length <= text.length

  if (!hasSpan) {
    return <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-ink">{text}</pre>
  }

  return (
    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-ink">
      <span className="text-muted">{text.slice(0, offset)}</span>
      <mark className="rounded bg-evidence-soft px-0.5 text-ink underline decoration-evidence decoration-2 underline-offset-4">
        {text.slice(offset, offset + length)}
      </mark>
      <span className="text-muted">{text.slice(offset + length)}</span>
    </pre>
  )
}
