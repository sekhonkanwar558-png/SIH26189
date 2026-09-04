import * as Dialog from '@radix-ui/react-dialog'
import { Check, Settings, X } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import type { AccessibilityPreferences, OfficerProfile } from '../config'

interface SettingsDrawerProps {
  collapsed: boolean
  officer: OfficerProfile
  preferences: AccessibilityPreferences
  onSave: (officer: OfficerProfile, preferences: AccessibilityPreferences) => void
}

export function SettingsDrawer({
  collapsed,
  officer,
  preferences,
  onSave,
}: SettingsDrawerProps) {
  const [draft, setDraft] = useState(officer)
  const [preferenceDraft, setPreferenceDraft] = useState(preferences)
  const [open, setOpen] = useState(false)

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSave(draft, preferenceDraft)
    setOpen(false)
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (nextOpen) {
          setDraft(officer)
          setPreferenceDraft(preferences)
        }
        setOpen(nextOpen)
      }}
    >
      <Dialog.Trigger asChild>
        <button
          type="button"
          className={`flex h-10 w-full items-center rounded-lg text-sm font-medium text-muted transition-colors hover:bg-canvas hover:text-ink ${collapsed ? 'justify-center' : 'gap-3 px-3'}`}
          aria-label="Open settings"
        >
          <Settings size={18} strokeWidth={1.8} />
          {!collapsed && <span>Settings</span>}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[#20252B]/20 data-[state=open]:animate-in" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 w-full max-w-[430px] overflow-y-auto border-l border-line bg-panel p-7 shadow-[-12px_0_36px_rgba(32,37,43,0.08)] focus:outline-none">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-xl font-semibold tracking-[-0.02em] text-ink">
                Settings
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm leading-6 text-muted">
                Keep the active officer and local accessibility preferences clear.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                className="grid size-9 place-items-center rounded-lg border border-line text-muted hover:bg-canvas hover:text-ink"
                aria-label="Close settings"
              >
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>

          <form className="mt-8" onSubmit={handleSubmit}>
            <fieldset className="space-y-5">
              <legend className="mb-4 text-sm font-semibold text-ink">Officer profile</legend>
              <Field
                label="Officer name"
                value={draft.name}
                example="Example: IO 114"
                onChange={(name) => setDraft((current) => ({ ...current, name }))}
              />
              <Field
                label="Role"
                value={draft.role}
                example="Example: Investigation Officer"
                onChange={(role) => setDraft((current) => ({ ...current, role }))}
              />
              <Field
                label="Officer ID"
                value={draft.id}
                example="Used to load only this officer's cases"
                onChange={(id) => setDraft((current) => ({ ...current, id }))}
              />
            </fieldset>

            <div className="my-7 h-px bg-line" />

            <fieldset className="space-y-3">
              <legend className="mb-4 text-sm font-semibold text-ink">Accessibility</legend>
              <label className="block rounded-lg border border-line bg-canvas/60 p-3.5">
                <span className="block text-sm font-medium text-ink">Text size</span>
                <span className="mt-0.5 block text-xs leading-5 text-muted">
                  Choose a comfortable reading size for this device.
                </span>
                <select
                  value={preferenceDraft.textSize}
                  onChange={(event) =>
                    setPreferenceDraft((current) => ({
                      ...current,
                      textSize: event.target.value as AccessibilityPreferences['textSize'],
                    }))
                  }
                  className="mt-3 h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink"
                >
                  <option value="comfortable">Comfortable</option>
                  <option value="large">Large</option>
                </select>
              </label>
              <PreferenceRow
                label="Increased contrast"
                detail="Keep the interface light with stronger borders"
                checked={preferenceDraft.increasedContrast}
                onChange={(increasedContrast) =>
                  setPreferenceDraft((current) => ({ ...current, increasedContrast }))
                }
              />
              <PreferenceRow
                label="Reduced motion"
                detail="Use instant graph and panel changes"
                checked={preferenceDraft.reducedMotion}
                onChange={(reducedMotion) =>
                  setPreferenceDraft((current) => ({ ...current, reducedMotion }))
                }
              />
            </fieldset>

            <button
              type="submit"
              className="mt-8 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-civic px-4 text-sm font-semibold text-white transition-colors hover:bg-civic-hover"
            >
              <Check size={17} />
              Save settings
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

interface FieldProps {
  label: string
  value: string
  example: string
  onChange: (value: string) => void
}

function Field({ label, value, example, onChange }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-ink">{label}</span>
      <input
        className="h-11 w-full rounded-lg border border-line-strong bg-white px-3.5 text-sm text-ink placeholder:text-subtle hover:border-[#AAB2BC]"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <span className="mt-1.5 block text-xs text-muted">{example}</span>
    </label>
  )
}

interface PreferenceRowProps {
  label: string
  detail: string
  checked: boolean
  onChange: (checked: boolean) => void
}

function PreferenceRow({ label, detail, checked, onChange }: PreferenceRowProps) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-line bg-canvas/60 p-3.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 accent-civic"
      />
      <span>
        <span className="block text-sm font-medium text-ink">{label}</span>
        <span className="mt-0.5 block text-xs leading-5 text-muted">{detail}</span>
      </span>
    </label>
  )
}
