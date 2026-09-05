import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { AlertCircle, Check, Paperclip, SendHorizontal, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { documentKinds } from '../../lib/documents'
import { formatBytes } from '../../lib/format'
import { iconButtonClass } from '../../lib/ui'

export interface PendingAttachment {
  id: string
  file: File
  /** Empty means the backend classifies it from the content. */
  kind: string
  progress: number
  status: 'ready' | 'uploading' | 'done' | 'failed'
  error?: string
}

interface ComposerProps {
  text: string
  onTextChange: (text: string) => void
  attachments: PendingAttachment[]
  onAttach: (files: FileList) => void
  onRemove: (id: string) => void
  onChangeKind: (id: string, kind: string) => void
  onSubmit: () => void
  busy: boolean
  disabled?: boolean
}

const MAX_ROWS = 6
const LINE_HEIGHT = 24

export function Composer({
  text,
  onTextChange,
  attachments,
  onAttach,
  onRemove,
  onChangeKind,
  onSubmit,
  busy,
  disabled = false,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Grow with the question, up to six lines, then scroll.
  useEffect(() => {
    const field = textareaRef.current
    if (!field) return
    field.style.height = 'auto'
    field.style.height = `${Math.min(field.scrollHeight, MAX_ROWS * LINE_HEIGHT + 22)}px`
  }, [text])

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!busy && !disabled) onSubmit()
    }
  }

  const canSend = !busy && !disabled && (text.trim().length > 0 || attachments.length > 0)

  return (
    <div className="border-t border-line bg-panel p-3">
      {attachments.length > 0 && (
        <ul className="mb-2.5 space-y-2">
          {attachments.map((attachment) => (
            <li
              key={attachment.id}
              className="rounded-lg border border-line bg-canvas px-3 py-2.5"
            >
              <div className="flex items-center gap-3">
                <Paperclip size={16} className="shrink-0 text-muted" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">{attachment.file.name}</p>
                  <p className="text-xs text-muted">
                    {formatBytes(attachment.file.size)} ·{' '}
                    {documentKinds.find((kind) => kind.value === attachment.kind)?.label ??
                      'Detect automatically'}
                  </p>
                </div>

                {attachment.status === 'done' && (
                  <span className="grid size-6 place-items-center rounded-full bg-success-soft text-success">
                    <Check size={14} strokeWidth={3} />
                  </span>
                )}

                {attachment.status === 'ready' && (
                  <DropdownMenu.Root>
                    <DropdownMenu.Trigger asChild>
                      <button
                        type="button"
                        className="h-8 rounded-lg border border-line-strong bg-white px-2.5 text-xs font-semibold text-ink hover:bg-canvas"
                      >
                        Change Type
                      </button>
                    </DropdownMenu.Trigger>
                    <DropdownMenu.Portal>
                      <DropdownMenu.Content
                        align="end"
                        sideOffset={6}
                        className="z-50 w-[220px] rounded-lg border border-line bg-panel p-1.5 shadow-[0_14px_35px_rgba(32,37,43,0.12)]"
                      >
                        {documentKinds.map((kind) => (
                          <DropdownMenu.Item
                            key={kind.value || 'auto'}
                            onSelect={() => onChangeKind(attachment.id, kind.value)}
                            className="flex h-9 cursor-pointer select-none items-center justify-between rounded-md px-2.5 text-sm text-ink outline-none hover:bg-canvas focus:bg-canvas"
                          >
                            {kind.label}
                            {attachment.kind === kind.value && <Check size={15} className="text-civic" />}
                          </DropdownMenu.Item>
                        ))}
                      </DropdownMenu.Content>
                    </DropdownMenu.Portal>
                  </DropdownMenu.Root>
                )}

                {attachment.status !== 'uploading' && (
                  <button
                    type="button"
                    onClick={() => onRemove(attachment.id)}
                    aria-label={`Remove ${attachment.file.name}`}
                    className="grid size-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-white hover:text-ink"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>

              {attachment.status === 'uploading' && (
                <div className="mt-2.5">
                  <div
                    className="h-1.5 overflow-hidden rounded-full bg-[#E4E8EC]"
                    role="progressbar"
                    aria-valuenow={attachment.progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Uploading ${attachment.file.name}`}
                  >
                    <div
                      className="h-full rounded-full bg-civic transition-[width] duration-200"
                      style={{ width: `${attachment.progress}%` }}
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-muted">
                    {attachment.progress < 100
                      ? `Uploading ${attachment.progress}%`
                      : 'Reading the document and updating the case...'}
                  </p>
                </div>
              )}

              {attachment.status === 'failed' && (
                <p className="mt-2 flex items-start gap-2 text-xs leading-5 text-danger">
                  <AlertCircle size={14} className="mt-0.5 shrink-0" />
                  {attachment.error}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-end gap-2">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(event) => {
            if (event.target.files?.length) onAttach(event.target.files)
            event.target.value = ''
          }}
        />
        <button
          type="button"
          className={iconButtonClass}
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          aria-label="Attach a document"
          title="Attach a document"
        >
          <Paperclip size={17} />
        </button>

        <label className="min-w-0 flex-1">
          <span className="sr-only">Ask shikonye about this case</span>
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={(event) => onTextChange(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Ask about this case, or attach a document"
            className="block w-full resize-none rounded-xl border border-line-strong bg-white px-3.5 py-2.5 text-[15px] leading-6 text-ink placeholder:text-subtle hover:border-[#AAB2BC] disabled:bg-canvas"
          />
        </label>

        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSend}
          className="inline-flex h-11 shrink-0 items-center gap-2 rounded-lg bg-civic px-4 text-sm font-semibold text-white transition-colors hover:bg-civic-hover disabled:cursor-not-allowed disabled:opacity-45"
        >
          <SendHorizontal size={17} />
          Send
        </button>
      </div>

      <p className="mt-2 px-1 text-[11px] text-muted">
        Enter sends · Shift + Enter adds a line
      </p>
    </div>
  )
}
