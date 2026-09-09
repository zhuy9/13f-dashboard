import { useParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { TradesTable } from '@/components/insider/TradesTable'
import { StockLink } from '@/components/StockLink'
import { Badge } from '@/components/ui/badge'
import { getInsiderPerson } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'

export function InsiderPersonPage() {
  const { cik = '' } = useParams<{ cik: string }>()
  const state = useAsyncData(() => getInsiderPerson(cik), [cik])

  if (state.loading) return <LoadingState />
  if (state.error) return <ErrorState message={state.error} />
  if (!state.data) return <EmptyState message="No Form 4 transactions on file for this person." />

  const person = state.data

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-semibold">{person.name}</h1>
        {person.roles.map((role) => (
          <Badge key={role} variant="secondary">
            {role}
          </Badge>
        ))}
      </header>

      <section>
        <h2 className="mb-2 text-lg font-medium">Issuers</h2>
        {person.issuers.length === 0 ? (
          <p className="text-sm text-ink-muted">No issuers on file.</p>
        ) : (
          <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
            {person.issuers.map((i) => (
              <li key={i.symbol}>
                <StockLink symbol={i.symbol} /> <span className="text-ink-muted">{i.role}</span>{' '}
                <span className="font-tabular text-ink-muted">{i.netShares.toLocaleString()} net shares</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium">Trades</h2>
        <TradesTable trades={person.trades} hideOwner />
      </section>
    </div>
  )
}
