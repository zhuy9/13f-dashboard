import { EventsTable } from '@/components/ownership/EventsTable'
import { StakesTable } from '@/components/ownership/StakesTable'
import { getOwnershipIssuer } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'

export function MajorShareholders({ symbol }: { symbol: string }) {
  const state = useAsyncData(() => getOwnershipIssuer(symbol), [symbol])
  if (state.loading || state.error || !state.data) return null

  const issuer = state.data
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-medium">Major Shareholders (13D/G)</h2>
      <StakesTable stakes={issuer.holders} hideIssuer />
      <EventsTable events={issuer.events} hideIssuer />
    </section>
  )
}
