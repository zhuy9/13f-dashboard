import { ColorBadge } from '@/components/ColorBadge'
import { KIND_COLORS, kindLabel } from '@/insider'
import type { InsiderKind } from '@/insiderTypes'

export function KindBadge({ kind }: { kind: InsiderKind }) {
  return <ColorBadge color={KIND_COLORS[kind]} label={kindLabel(kind)} />
}
