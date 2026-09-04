import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Plus, X } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import type { OfficerProfile } from '../config'
import { createCase, deleteCase, updateCase } from '../lib/api'
import type { CaseSummary, NewCaseInput } from '../types'

const caseTypes = [
  'Human trafficking',
  'Financial fraud',
  'Cybercrime',
  'Organized crime',
  'Missing person',
  'Narcotics',
  'Other',
]

interface NewCaseDialogProps {
  officer: OfficerProfile
  onCreated: (createdCase: CaseSummary) => void
}

export function NewCaseDialog({ officer, onCreated }: NewCaseDialogProps) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [caseType, setCaseType] = useState('')
  const [brief, setBrief] = useState('')

  const mutation = useMutation({
    mutationFn: (input: NewCaseInput) => createCase(input),
    onSuccess: async (createdCase) => {
      await queryClient.invalidateQueries({ queryKey: ['cases'] })
      setOpen(false)
      setTitle('')
      setCaseType('')
      setBrief('')
      onCreated(createdCase)
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    mutation.mutate({
      case_id: generateCaseId(title),
      title: title.trim(),
      officer: officer.id,
      case_type: caseType.trim().toLowerCase(),
      brief: brief.trim(),
    })
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex h-11 items-center justify-center gap-2 whitespace-nowrap rounded-lg bg-civic px-4 text-sm font-semibold text-white transition-colors hover:bg-civic-hover"
        >
          <Plus size={18} strokeWidth={2} />
          New Case
        </button>
      </Dialog.Trigger>
      <CaseDialogContent
        title="Create a new case"
        description="Start with only the details your team already knows. Documents can be added after creation."
      >
        <form onSubmit={handleSubmit} className="mt-7 space-y-5">
          <FormField
            label="Case title"
            example="Example: Missing persons network - Ludhiana"
            value={title}
            onChange={setTitle}
            placeholder="Enter a clear case title"
            autoFocus
            required
          />

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-ink">Case type</span>
            <input
              list="case-types"
              className={inputClass}
              value={caseType}
              onChange={(event) => setCaseType(event.target.value)}
              placeholder="Search or enter a case type"
              required
            />
            <datalist id="case-types">
              {caseTypes.map((item) => (
                <option value={item} key={item} />
              ))}
            </datalist>
            <span className="mt-1.5 block text-xs text-muted">
              Start typing to search. Choose Other when needed.
            </span>
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium text-ink">Case brief</span>
            <textarea
              className={`${inputClass} min-h-[112px] resize-y py-3 leading-6`}
              rows={4}
              value={brief}
              onChange={(event) => setBrief(event.target.value)}
              placeholder="Summarize what happened and what the team needs to establish."
            />
            <span className="mt-1.5 block text-xs text-muted">
              Optional. Use plain language and avoid assumptions.
            </span>
          </label>

          {mutation.isError && <InlineError message={mutation.error.message} />}

          <div className="flex items-center justify-end gap-3 pt-2">
            <Dialog.Close asChild>
              <button type="button" className={secondaryButtonClass}>
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="submit"
              className={primaryButtonClass}
              disabled={!title.trim() || !caseType.trim() || mutation.isPending}
            >
              {mutation.isPending ? 'Creating case...' : 'Create Case'}
            </button>
          </div>
        </form>
      </CaseDialogContent>
    </Dialog.Root>
  )
}

interface EditCaseDialogProps {
  caseItem: CaseSummary
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

export function EditCaseDialog({ caseItem, open, onOpenChange, onSaved }: EditCaseDialogProps) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState(caseItem.title)
  const [caseType, setCaseType] = useState(caseItem.case_type)
  const [brief, setBrief] = useState(caseItem.brief)

  const mutation = useMutation({
    mutationFn: () =>
      updateCase(caseItem.case_id, {
        title: title.trim(),
        case_type: caseType.trim().toLowerCase(),
        brief: brief.trim(),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['cases'] })
      onOpenChange(false)
      onSaved()
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <CaseDialogContent
        title="Edit case details"
        description="Changes are saved only when you choose Save Changes."
      >
        <form onSubmit={handleSubmit} className="mt-7 space-y-5">
          <FormField
            label="Case title"
            example="Use a title officers can recognize quickly"
            value={title}
            onChange={setTitle}
            required
          />
          <FormField
            label="Case type"
            example="Example: Human trafficking"
            value={caseType}
            onChange={setCaseType}
            required
          />
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-ink">Case brief</span>
            <textarea
              className={`${inputClass} min-h-[112px] resize-y py-3 leading-6`}
              rows={4}
              value={brief}
              onChange={(event) => setBrief(event.target.value)}
            />
          </label>
          {mutation.isError && <InlineError message={mutation.error.message} />}
          <div className="flex items-center justify-end gap-3 pt-2">
            <Dialog.Close asChild>
              <button type="button" className={secondaryButtonClass}>
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="submit"
              className={primaryButtonClass}
              disabled={!title.trim() || !caseType.trim() || mutation.isPending}
            >
              {mutation.isPending ? 'Saving changes...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </CaseDialogContent>
    </Dialog.Root>
  )
}

interface DeleteCaseDialogProps {
  caseItem: CaseSummary
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted: () => void
}

export function DeleteCaseDialog({ caseItem, open, onOpenChange, onDeleted }: DeleteCaseDialogProps) {
  const queryClient = useQueryClient()
  const [confirmation, setConfirmation] = useState('')
  const mutation = useMutation({
    mutationFn: () => deleteCase(caseItem.case_id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['cases'] })
      setConfirmation('')
      onOpenChange(false)
      onDeleted()
    },
  })

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <CaseDialogContent
        title="Delete this case?"
        description="This permanently removes the case, its documents, connections, memory and custody log."
      >
        <form
          className="mt-6"
          onSubmit={(event) => {
            event.preventDefault()
            mutation.mutate()
          }}
        >
          <div className="flex gap-3 rounded-lg border border-[#E6C0C0] bg-danger-soft p-4 text-sm leading-6 text-danger">
            <AlertTriangle size={19} className="mt-0.5 shrink-0" />
            This action cannot be undone. Type the full case title to confirm.
          </div>
          <label className="mt-5 block">
            <span className="mb-2 block text-sm font-medium text-ink">Case title</span>
            <input
              className={inputClass}
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              placeholder={caseItem.title}
              autoComplete="off"
            />
          </label>
          {mutation.isError && <InlineError message={mutation.error.message} />}
          <div className="mt-6 flex items-center justify-end gap-3">
            <Dialog.Close asChild>
              <button type="button" className={secondaryButtonClass}>
                Keep Case
              </button>
            </Dialog.Close>
            <button
              type="submit"
              className="inline-flex h-11 items-center justify-center rounded-lg bg-danger px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
              disabled={confirmation !== caseItem.title || mutation.isPending}
            >
              {mutation.isPending ? 'Deleting...' : 'Delete Case'}
            </button>
          </div>
        </form>
      </CaseDialogContent>
    </Dialog.Root>
  )
}

interface CaseDialogContentProps {
  title: string
  description: string
  children: React.ReactNode
}

function CaseDialogContent({ title, description, children }: CaseDialogContentProps) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-[#20252B]/25" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[calc(100vh-48px)] w-[calc(100%-32px)] max-w-[560px] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[10px] border border-line bg-panel p-7 shadow-[0_24px_70px_rgba(32,37,43,0.16)] focus:outline-none">
        <div className="flex items-start justify-between gap-5">
          <div>
            <Dialog.Title className="text-xl font-semibold tracking-[-0.02em] text-ink">
              {title}
            </Dialog.Title>
            <Dialog.Description className="mt-1.5 text-sm leading-6 text-muted">
              {description}
            </Dialog.Description>
          </div>
          <Dialog.Close asChild>
            <button
              type="button"
              className="grid size-9 shrink-0 place-items-center rounded-lg border border-line text-muted hover:bg-canvas hover:text-ink"
              aria-label="Close dialog"
            >
              <X size={18} />
            </button>
          </Dialog.Close>
        </div>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  )
}

interface FormFieldProps {
  label: string
  example: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  required?: boolean
  autoFocus?: boolean
}

function FormField({
  label,
  example,
  value,
  onChange,
  placeholder,
  required,
  autoFocus,
}: FormFieldProps) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-ink">{label}</span>
      <input
        className={inputClass}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        autoFocus={autoFocus}
      />
      <span className="mt-1.5 block text-xs text-muted">{example}</span>
    </label>
  )
}

function InlineError({ message }: { message: string }) {
  return (
    <div role="alert" className="mt-4 rounded-lg border border-[#E6C0C0] bg-danger-soft p-3 text-sm text-danger">
      {message} Try again, or check that the case service is available.
    </div>
  )
}

function generateCaseId(title: string) {
  const slug = title
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 28)
  const suffix = Date.now().toString().slice(-6)
  return `case-${slug || 'new'}-${suffix}`
}

const inputClass =
  'h-11 w-full rounded-lg border border-line-strong bg-white px-3.5 text-sm text-ink placeholder:text-subtle hover:border-[#AAB2BC]'

const primaryButtonClass =
  'inline-flex h-11 items-center justify-center rounded-lg bg-civic px-4 text-sm font-semibold text-white transition-colors hover:bg-civic-hover disabled:cursor-not-allowed disabled:opacity-45'

const secondaryButtonClass =
  'inline-flex h-11 items-center justify-center rounded-lg border border-line-strong bg-white px-4 text-sm font-semibold text-ink transition-colors hover:bg-canvas'
