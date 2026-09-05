import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  CircleAlert,
  FileText,
  Upload,
} from 'lucide-react'
import { useState } from 'react'
import type { DragEvent } from 'react'
import { ApiError, getDocuments, uploadDocument } from '../../lib/api'
import { documentKindLabel } from '../../lib/documents'
import { formatBytes, formatCaseDate, shortHash } from '../../lib/format'
import { chipClass, quietButtonClass } from '../../lib/ui'
import type { CaseDocument, IngestResult } from '../../types'
import { PanelBody, PanelHeader, PanelShell } from './PanelShell'
import type { SourceRequest } from './SourceDialog'

interface DocumentsPanelProps {
  caseId: string
  officerId: string
  onOpenSource: (request: SourceRequest) => void
  onToast: (message: string) => void
  focused: boolean
  onFocusToggle: () => void
}

export function DocumentsPanel({
  caseId,
  officerId,
  onOpenSource,
  onToast,
  focused,
  onFocusToggle,
}: DocumentsPanelProps) {
  const queryClient = useQueryClient()
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [lastResult, setLastResult] = useState<{ filename: string; result: IngestResult } | null>(null)

  const documentsQuery = useQuery({
    queryKey: ['documents', caseId],
    queryFn: () => getDocuments(caseId),
  })

  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadDocument(caseId, file, undefined, officerId, setProgress),
    onSuccess: async (response, file) => {
      setProgress(null)
      setLastResult({ filename: file.name, result: response.document })
      await queryClient.invalidateQueries({ queryKey: ['documents', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['graph', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['analytics', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['custody', caseId] })
      onToast(`${file.name} added to the case`)
    },
    onError: () => setProgress(null),
  })

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files?.[0]
    if (file) upload.mutate(file)
  }

  return (
    <PanelShell label="Documents">
      <PanelHeader title="Documents" focused={focused} onFocusToggle={onFocusToggle}>
        <span className="text-xs text-muted">
          {documentsQuery.data?.length ?? 0} in this case
        </span>
      </PanelHeader>

      <PanelBody>
        <div
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`rounded-[10px] border border-dashed p-6 text-center transition-colors ${
            dragging ? 'border-civic bg-civic-soft' : 'border-line-strong bg-panel'
          }`}
        >
          <div className="mx-auto grid size-11 place-items-center rounded-lg bg-civic-soft text-civic">
            <Upload size={20} strokeWidth={1.8} />
          </div>
          <h3 className="mt-3.5 text-base font-semibold text-ink">Add evidence to this case</h3>
          <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-muted">
            FIRs, call records, bank statements, criminal history, social exports and intelligence
            reports. The type is worked out from the contents.
          </p>

          <label className={`${quietButtonClass} mt-4 cursor-pointer`}>
            Choose a document
            <input
              type="file"
              className="hidden"
              disabled={upload.isPending}
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) upload.mutate(file)
                event.target.value = ''
              }}
            />
          </label>

          {progress !== null && (
            <div className="mx-auto mt-4 max-w-sm">
              <div
                className="h-1.5 overflow-hidden rounded-full bg-[#E4E8EC]"
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full rounded-full bg-civic transition-[width] duration-200"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="mt-1.5 text-xs text-muted">
                {progress < 100 ? `Uploading ${progress}%` : 'Reading and updating the case...'}
              </p>
            </div>
          )}
        </div>

        {upload.isError && (
          <div role="alert" className="mt-4 flex items-start gap-3 rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-4">
            <AlertCircle size={19} className="mt-0.5 shrink-0 text-danger" />
            <div>
              <p className="text-sm font-semibold text-ink">That document was not added</p>
              <p className="mt-1 text-sm leading-6 text-muted">
                {upload.error instanceof ApiError
                  ? upload.error.message
                  : 'The case service could not be reached.'}
              </p>
            </div>
          </div>
        )}

        {/* D18 — a document the extractor could not read must say so here too,
            not only in the conversation. A silent green tick is the failure. */}
        {lastResult && lastResult.result.warnings.length > 0 && (
          <div className="mt-4 rounded-[10px] border border-[#E9D1A8] bg-warning-soft p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <CircleAlert size={17} className="shrink-0 text-warning" />
              {lastResult.filename} was not fully read
            </p>
            <ul className="mt-2 space-y-1.5">
              {lastResult.result.warnings.map((warning) => (
                <li key={warning} className="text-[13px] leading-6 text-ink">
                  {warning}
                </li>
              ))}
            </ul>
          </div>
        )}

        <section className="mt-6" aria-labelledby="documents-heading">
          <h3 id="documents-heading" className="mb-3 text-sm font-semibold text-ink">
            In this case
          </h3>

          {documentsQuery.isLoading && (
            <div className="animate-pulse space-y-2.5" aria-label="Loading documents">
              {[0, 1, 2].map((row) => (
                <div key={row} className="h-[68px] rounded-[10px] bg-[#EFF1F3]" />
              ))}
            </div>
          )}

          {documentsQuery.isError && (
            <div role="alert" className="rounded-[10px] border border-[#E7C7C7] bg-danger-soft p-4">
              <p className="text-sm font-semibold text-ink">The document list is unavailable</p>
              <button
                type="button"
                className={`${quietButtonClass} mt-3`}
                onClick={() => void documentsQuery.refetch()}
              >
                Retry
              </button>
            </div>
          )}

          {documentsQuery.data?.length === 0 && (
            <p className="rounded-[10px] border border-dashed border-line-strong bg-panel px-5 py-8 text-center text-sm text-muted">
              No documents yet. The case graph fills in as you add them.
            </p>
          )}

          <ul className="space-y-2.5">
            {documentsQuery.data?.map((document) => (
              <DocumentRow
                key={document.doc_id}
                document={document}
                onOpen={() => onOpenSource({ docId: document.doc_id, context: document.filename })}
              />
            ))}
          </ul>
        </section>
      </PanelBody>
    </PanelShell>
  )
}

function DocumentRow({ document, onOpen }: { document: CaseDocument; onOpen: () => void }) {
  const grading = typeof document.meta.grading === 'object' && document.meta.grading !== null
    ? (document.meta.grading as { source_grading?: string })
    : null
  const factor =
    typeof document.meta.confidence_factor === 'number' ? document.meta.confidence_factor : null

  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="flex w-full items-start gap-3.5 rounded-[10px] border border-line bg-panel p-4 text-left transition-colors hover:border-[#BCC5CE] hover:bg-canvas"
      >
        <span className="grid size-10 shrink-0 place-items-center rounded-lg border border-[#CDDAE6] bg-civic-soft text-civic">
          <FileText size={19} strokeWidth={1.8} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="truncate text-[15px] font-semibold text-ink">{document.filename}</span>
            <span className={`${chipClass} border-line-strong bg-canvas text-muted`}>
              {documentKindLabel(document.kind)}
            </span>
            {grading?.source_grading && (
              <span className={`${chipClass} border-[#E4D3AF] bg-evidence-soft text-[#8A5F16]`}>
                Source {grading.source_grading}
              </span>
            )}
          </span>
          <span className="mt-1.5 block text-xs text-muted">
            {formatBytes(document.char_len)} of text · added {formatCaseDate(document.ingested_at)}
          </span>
          <span className="mt-1 block font-mono text-[11px] text-subtle">
            sha256 {shortHash(document.sha256, 16)}
          </span>
          {factor !== null && factor < 1 && (
            <span className="mt-1.5 block text-xs leading-5 text-muted">
              Everything inferred from this report enters the case at {Math.round(factor * 100)}%
              confidence because of its source grading.
            </span>
          )}
        </span>
      </button>
    </li>
  )
}
