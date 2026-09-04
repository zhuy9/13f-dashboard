import { ColorBadge } from '@/components/ColorBadge'
import { CALL_COLOR, PUT_COLOR } from '@/format'

export function SideBadge({ side }: { side: 'PUT' | 'CALL' }) {
  const color = side === 'PUT' ? PUT_COLOR : CALL_COLOR
  const label = side === 'PUT' ? 'Reported Put Exposure' : 'Reported Call Exposure'
  return <ColorBadge color={color} label={label} />
}
