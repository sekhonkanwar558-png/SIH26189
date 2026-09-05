/**
 * Class strings the workspace reuses. Kept here rather than repeated so the
 * chat, the graph toolbar and the six panels stay visibly one product — the
 * cases screen established these shapes and the workspace inherits them.
 */

export const panelClass = 'rounded-[10px] border border-line bg-panel'

export const inputClass =
  'h-11 w-full rounded-lg border border-line-strong bg-white px-3.5 text-sm text-ink placeholder:text-subtle hover:border-[#AAB2BC]'

export const primaryButtonClass =
  'inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-civic px-4 text-sm font-semibold text-white transition-colors hover:bg-civic-hover disabled:cursor-not-allowed disabled:opacity-45'

export const secondaryButtonClass =
  'inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-line-strong bg-white px-4 text-sm font-semibold text-ink transition-colors hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-45'

export const quietButtonClass =
  'inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-line-strong bg-white px-3 text-[13px] font-semibold text-ink transition-colors hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-45'

export const iconButtonClass =
  'grid size-9 shrink-0 place-items-center rounded-lg border border-line-strong bg-white text-muted transition-colors hover:bg-canvas hover:text-ink disabled:cursor-not-allowed disabled:opacity-45'

export const chipClass =
  'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold'

/** The width below which the workspace stops splitting and shows tabs. */
export const TABLET_BREAKPOINT = 900
