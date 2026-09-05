import type { EdgeType, NodeType } from '../types'

/**
 * One vocabulary for every entity type, used by the graph canvas, the node
 * drawer, the citation chips and the findings list. It lives here so the same
 * person is the same colour everywhere — an officer learns the palette once.
 *
 * Tints are soft on purpose (§3.5a): this is an investigative tool for people
 * who are not necessarily technical, not a threat console.
 */
export interface EntityStyle {
  /** Plain-language name for the type — what the officer is shown. */
  label: string
  /** Node fill on the canvas and behind an icon. */
  tint: string
  /** Border, and the ring on a selected node. */
  border: string
  /** Text and icon colour. Always ≥4.5:1 on `tint`. */
  ink: string
}

export const entityStyles: Record<NodeType, EntityStyle> = {
  person: { label: 'Person', tint: '#E7EFF7', border: '#A9C4DC', ink: '#245B8A' },
  phone: { label: 'Phone', tint: '#E4F1EF', border: '#A4CCC6', ink: '#2C6E64' },
  account: { label: 'Account', tint: '#FBF1E0', border: '#DDC08A', ink: '#8A5F16' },
  location: { label: 'Location', tint: '#E9F2E8', border: '#B4CFB0', ink: '#3F6B42' },
  organization: { label: 'Organisation', tint: '#EDEAF6', border: '#BFB6DE', ink: '#55499A' },
  vehicle: { label: 'Vehicle', tint: '#E9ECEF', border: '#BCC4CD', ink: '#4B5563' },
  device: { label: 'Device', tint: '#E5EFF4', border: '#A9C6D4', ink: '#35667C' },
  event: { label: 'Prior case', tint: '#F6E9EA', border: '#DCB4B7', ink: '#8A424A' },
  document: { label: 'Document', tint: '#EFF1F3', border: '#CBD1D8', ink: '#5C656F' },
}

const fallbackStyle: EntityStyle = {
  label: 'Entity',
  tint: '#EFF1F3',
  border: '#CBD1D8',
  ink: '#5C656F',
}

export function entityStyle(type: string): EntityStyle {
  return entityStyles[type as NodeType] ?? fallbackStyle
}

/** `person:ravi_kumar` → `person`. Document ids use `doc:` (§5.1). */
export function nodeTypeOf(nodeId: string): NodeType {
  const prefix = nodeId.split(':', 1)[0]
  if (prefix === 'doc') return 'document'
  return (prefix in entityStyles ? prefix : 'document') as NodeType
}

/**
 * Edge labels in an officer's words rather than the wire constant. `CO_OCCURS`
 * is the one that needs it most: it means "named together", and a screen that
 * prints the constant makes the officer learn our schema.
 */
export const edgeLabels: Record<EdgeType, string> = {
  CALLED: 'called',
  MESSAGED: 'messaged',
  TRANSFERRED_TO: 'transferred money to',
  CO_OCCURS: 'appears with',
  OWNS: 'uses',
  LOCATED_AT: 'was at',
  REGISTERED_TO: 'registered to',
  MENTIONED_IN: 'named in',
}

export function edgeLabel(type: string) {
  return edgeLabels[type as EdgeType] ?? type.toLowerCase().replace(/_/g, ' ')
}

/**
 * Confidence below this is drawn dashed and labelled inferred. 0.6 is what
 * text proximity in an FIR earns (§5.1); anything at or above it was stated by
 * a record rather than deduced from one.
 */
export const INFERRED_BELOW = 0.6

const icons: Record<NodeType, string> = {
  person:
    '<circle cx="12" cy="8.5" r="3.6"/><path d="M5.5 19.5c0-3.4 2.9-5.6 6.5-5.6s6.5 2.2 6.5 5.6"/>',
  phone:
    '<rect x="7" y="3" width="10" height="18" rx="2.4"/><path d="M10.8 17.6h2.4"/>',
  account:
    '<rect x="3" y="6" width="18" height="12" rx="2.2"/><circle cx="12" cy="12" r="2.6"/>',
  location:
    '<path d="M12 21s6.5-5.7 6.5-10.2A6.5 6.5 0 0 0 5.5 10.8C5.5 15.3 12 21 12 21Z"/><circle cx="12" cy="10.6" r="2.4"/>',
  organization:
    '<rect x="4.5" y="4" width="15" height="16" rx="1.8"/><path d="M9 8.5h2M13 8.5h2M9 12.5h2M13 12.5h2M10.5 20v-3.4h3V20"/>',
  vehicle:
    '<path d="M4 14.5h16v3.2h-3v-1.4H7v1.4H4Z"/><path d="M5.6 14.5 7.4 9h9.2l1.8 5.5"/><circle cx="8" cy="17.7" r="1.5"/><circle cx="16" cy="17.7" r="1.5"/>',
  device:
    '<rect x="4.5" y="4.5" width="15" height="15" rx="2.4"/><rect x="9" y="9" width="6" height="6" rx="1.2"/>',
  event:
    '<rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M8.6 9h6.8M8.6 12.6h6.8M8.6 16.2h4"/>',
  document:
    '<path d="M6.5 3.5h7l4.5 4.5v12.5h-11.5Z"/><path d="M13.5 3.5V8h4.5"/>',
}

/**
 * A Cytoscape node icon as a data URI. Inline rather than a sprite file so the
 * canvas keeps working with no network at all — the demo machine may be
 * offline (README §13) and an icon that fails to load reads as a broken node.
 */
export function entityIconUri(type: string) {
  const style = entityStyle(type)
  const paths = icons[type as NodeType] ?? icons.document
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ` +
    `stroke="${style.ink}" stroke-width="1.7" stroke-linecap="round" ` +
    `stroke-linejoin="round">${paths}</svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}
