import { EventsTable } from '@/components/ownership/EventsTable'
import { StakesTable } from '@/components/ownership/StakesTable'
import type { OwnershipIssuer } from '@/ownershipTypes'

export function MajorShareholders({ issuer }: { issuer: OwnershipIssuer }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-medium">Major Shareholders (13D/G)</h2>
      <StakesTable stakes={issuer.holders} hideIssuer />
      <EventsTable events={issuer.events} hideIssuer />
    </section>
  )
}
