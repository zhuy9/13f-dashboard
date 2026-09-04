import { Badge } from '@/components/ui/badge'

export function ColorBadge({ color, label }: { color: string; label: string }) {
  return (
    <Badge variant="outline" style={{ color, borderColor: color, backgroundColor: `${color}1a` }}>
      {label}
    </Badge>
  )
}
