export function formatCaseDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Date unavailable'

  const day = new Intl.DateTimeFormat('en-IN', { day: '2-digit' }).format(date)
  const month = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ][date.getMonth()]
  const year = date.getFullYear()
  const time = new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)

  return `${day} ${month} ${year}, ${time}`
}

export function sentenceCase(value: string) {
  if (!value) return 'Unspecified'
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function compactNumber(value: number) {
  return new Intl.NumberFormat('en-IN').format(value)
}

export function formatDayLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Earlier'

  const today = new Date()
  const startOf = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const dayMs = 86_400_000
  const diff = Math.round((startOf(today) - startOf(date)) / dayMs)

  if (diff === 0) return 'Today'
  if (diff === 1) return 'Yesterday'
  return formatCaseDate(value).split(',')[0]
}

export function formatClockTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 KB'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function shortHash(hash: string, length = 10) {
  if (!hash) return '—'
  return hash.slice(0, length)
}

/**
 * A phone or an account number is the kind of identifier that should not sit
 * on a shared screen until someone asks for it, so the workspace masks these
 * until Reveal. Enough tail is kept for an officer to recognise the one they
 * already know.
 */
export function maskIdentifier(value: string) {
  const digits = value.replace(/\D/g, '')
  if (digits.length < 5) return value
  const tail = digits.slice(-4)
  return `${'•'.repeat(Math.min(6, digits.length - 4))} ${tail}`
}

export function isSensitiveType(type: string) {
  return type === 'phone' || type === 'account'
}

/** Indian currency grouping — §3.5a. Amounts arrive as plain numbers. */
export function formatAmount(value: number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value)
}

export function titleCase(value: string) {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase())
}
