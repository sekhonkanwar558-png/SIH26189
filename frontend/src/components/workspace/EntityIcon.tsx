import {
  Banknote,
  Building2,
  Car,
  Cpu,
  FileText,
  Gavel,
  MapPin,
  Phone,
  User,
} from 'lucide-react'
import { entityStyle, nodeTypeOf } from '../../lib/entities'
import type { NodeType } from '../../types'

const glyphs: Record<NodeType, typeof User> = {
  person: User,
  phone: Phone,
  account: Banknote,
  location: MapPin,
  organization: Building2,
  vehicle: Car,
  device: Cpu,
  event: Gavel,
  document: FileText,
}

interface EntityIconProps {
  /** Either a node type (`person`) or a full node id (`person:ravi_kumar`). */
  type: string
  size?: number
  /** Draw the tinted circle behind the glyph. Off for inline use in prose. */
  chrome?: boolean
}

export function EntityIcon({ type, size = 18, chrome = true }: EntityIconProps) {
  const resolved = type.includes(':') ? nodeTypeOf(type) : type
  const style = entityStyle(resolved)
  const Glyph = glyphs[resolved as NodeType] ?? FileText

  if (!chrome) {
    return <Glyph size={size} strokeWidth={1.8} style={{ color: style.ink }} aria-hidden="true" />
  }

  return (
    <span
      aria-hidden="true"
      className="grid shrink-0 place-items-center rounded-full border"
      style={{
        width: size + 14,
        height: size + 14,
        background: style.tint,
        borderColor: style.border,
        color: style.ink,
      }}
    >
      <Glyph size={size} strokeWidth={1.8} />
    </span>
  )
}
