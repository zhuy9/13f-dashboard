import { EventsTable } from '@/components/ownership/EventsTable'
import { StakesTable } from '@/components/ownership/StakesTable'
import { getOwnershipInvestor } from '@/data'
import { quarterLabel } from '@/format'
import { useAsyncData } from '@/hooks/useAsyncData'

export function OwnershipFilings({ cik, latestPeriod }: { cik: string; latestPeriod?: string }) {
  const state = useAsyncData(() => getOwnershipInvestor(cik), [cik])
  if (state.loading || state.error || !state.data) return null

  const investor = state.data
  const sinceCount = latestPeriod ? investor.events.filter((e) => e.filedAt > latestPeriod).length : 0

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-medium">Ownership Filings</h2>
      {latestPeriod && (
        <p className="text-sm text-ink-muted">
          {sinceCount} ownership filing{sinceCount === 1 ? '' : 's'} since the {quarterLabel(latestPeriod)} 13F.
        </p>
      )}
      <StakesTable stakes={investor.stakes} hideInvestor />
      <EventsTable events={investor.events} hideInvestor />
    </section>
  )
}
