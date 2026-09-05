/**
 * The document kinds the backend recognises (README §1.2a), plus letting it
 * decide for itself — which is the default, because it classifies from the
 * contents and an officer should not have to know our vocabulary to file an
 * FIR. Overriding is there for the case where it guesses wrong.
 */
export const documentKinds = [
  { value: '', label: 'Detect automatically' },
  { value: 'fir', label: 'FIR' },
  { value: 'cdr', label: 'Call records (CDR)' },
  { value: 'financial', label: 'Bank statement' },
  { value: 'history', label: 'Criminal history' },
  { value: 'social', label: 'Social media' },
  { value: 'intelligence', label: 'Intelligence report' },
  { value: 'surveillance', label: 'Surveillance report' },
  { value: 'note', label: 'Note' },
] as const

/**
 * The officer's name for a document kind. `titleCase` would render the wire
 * values as "Cdr" and "Fir", which are not words — these are the labels the
 * upload menu already uses, so a document reads the same everywhere.
 */
export function documentKindLabel(kind: string) {
  const known = documentKinds.find((entry) => entry.value === kind)
  if (known && known.value) return known.label
  if (!kind || kind === 'other') return 'Unclassified'
  return kind.charAt(0).toUpperCase() + kind.slice(1)
}
