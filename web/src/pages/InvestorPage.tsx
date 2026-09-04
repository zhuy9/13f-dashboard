import { useParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { ManagerLink } from '@/components/ManagerLink'
import { EventsTable } from '@/components/ownership/EventsTable'
import { StakesTable } from '@/components/ownership/StakesTable'
import { Badge } from '@/components/ui/badge'
import { getOwnershipInvestor } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'

export function InvestorPage() {
  const { cik = '' } = useParams<{ cik: string }>()
  const state = useAsyncData(() => getOwnershipInvestor(cik), [cik])

  if (state.loading) return <LoadingState />
  if (state.error) return <ErrorState message={state.error} />
  if (!state.data) return <EmptyState message="Investor not found." />

  const investor = state.data

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{investor.name}</h1>
        {investor.cluster && <Badge variant="secondary">{investor.cluster}</Badge>}
        {investor.isRoster && <ManagerLink cik={investor.cik} label="13F profile →" />}
      </header>

      <section>
        <h2 className="mb-2 text-lg font-medium">Current Stakes</h2>
        <StakesTable stakes={investor.stakes} hideInvestor />
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Filings</h2>
        <EventsTable events={investor.events} hideInvestor />
      </section>
    </div>
  )
}
