import { Badge } from '@/components/ui/badge'
import { STATUS_COLORS } from '@/format'
import type { PositionStatus } from '@/types'

const LABELS: Record<PositionStatus, string> = {
  NEW: 'New',
  ADDED: 'Added',
  TRIMMED: 'Trimmed',
  UNCHANGED: 'Unchanged',
  SOLD_OUT: 'Sold Out',
}

export function StatusBadge({ status }: { status: PositionStatus | null }) {
  if (!status) return <span className="text-ink-muted">—</span>
  const color = STATUS_COLORS[status]
  return (
    <Badge
      variant="outline"
      style={{ color, borderColor: color, backgroundColor: `${color}1a` }}
    >
      {LABELS[status]}
    </Badge>
  )
}
