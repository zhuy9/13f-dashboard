import { ColorBadge } from '@/components/ColorBadge'
import { eventLabel, EVENT_COLORS } from '@/ownership'
import type { OwnershipEventKind, OwnershipForm } from '@/ownershipTypes'

export function EventBadge({ event, form }: { event: OwnershipEventKind; form: OwnershipForm }) {
  if (!event) return <span className="text-ink-muted">—</span>
  return <ColorBadge color={EVENT_COLORS[event]} label={eventLabel(event, form)} />
}
