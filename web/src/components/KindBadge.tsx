import { ColorBadge } from '@/components/ColorBadge'
import { KIND_COLORS } from '@/format'
import type { SecurityKind } from '@/types'

const LABELS: Record<Exclude<SecurityKind, 'EQUITY'>, string> = {
  NOTE: 'Note',
  WARRANT: 'Warrant',
}

// EQUITY renders nothing: it is the overwhelming majority, and a badge on every row would be
// noise that hides the handful of rows where the instrument is not stock.
export function KindBadge({ kind }: { kind: SecurityKind | null }) {
  if (!kind || kind === 'EQUITY') return null
  return <ColorBadge color={KIND_COLORS[kind]} label={LABELS[kind]} />
}
