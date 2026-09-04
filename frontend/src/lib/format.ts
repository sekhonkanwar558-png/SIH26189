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
