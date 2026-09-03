import { Badge } from '@/components/ui/badge'
import { CALL_COLOR, PUT_COLOR } from '@/format'

export function SideBadge({ side }: { side: 'PUT' | 'CALL' }) {
  const color = side === 'PUT' ? PUT_COLOR : CALL_COLOR
  const label = side === 'PUT' ? 'Reported Put Exposure' : 'Reported Call Exposure'
  return (
    <Badge variant="outline" style={{ color, borderColor: color, backgroundColor: `${color}1a` }}>
      {label}
    </Badge>
  )
}
