import { ColorBadge } from '@/components/ColorBadge'
import { FORM_COLORS } from '@/ownership'
import type { OwnershipForm } from '@/ownershipTypes'

export function FormBadge({ form }: { form: OwnershipForm }) {
  return <ColorBadge color={FORM_COLORS[form]} label={form} />
}
