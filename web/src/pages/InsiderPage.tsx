import { useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { ClusterTable, VsThirteenFTable } from '@/components/insider/ClusterTable'
import { TradesTable } from '@/components/insider/TradesTable'
import { Explain } from '@/components/Explain'
import { StatTile } from '@/components/StatTile'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getInsiderFeed } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'
import { filterTrades } from '@/insider'
import type { InsiderFilter } from '@/insiderTypes'

const FILTERS: { value: InsiderFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'buys', label: 'Buys' },
  { value: 'sells', label: 'Sells' },
  { value: 'planned', label: 'Planned' },
  { value: 'discretionary', label: 'Discretionary' },
  { value: 'awards', label: 'Awards' },
  { value: 'exercises', label: 'Exercises' },
]

export function InsiderPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const feedState = useAsyncData(getInsiderFeed, [])

  const filter = (searchParams.get('filter') as InsiderFilter | null) ?? 'all'
  const query = searchParams.get('q') ?? ''

  function setFilter(value: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('filter', value)
      return next
    })
  }

  function setQuery(value: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set('q', value)
      else next.delete('q')
      return next
    })
  }

  if (feedState.loading) return <LoadingState />
  if (feedState.error) return <ErrorState message={feedState.error} />
  if (!feedState.data) return <EmptyState message="No insider data yet." />

  const feed = feedState.data
  const filtered = filterTrades(feed.trades, filter, query)
  const { headline } = feed

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold">Insiders</h1>
        <p className="text-sm text-ink-muted">
          Form 4 transactions by officers, directors, and 10% owners of {feed.universe.symbols.toLocaleString()} tracked issuers,
          since {feed.startDate}. Counts below are as of {headline.asOf}.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile
          label={`Open-market buys, ${headline.windowDays} days to ${headline.asOf}`}
          value={headline.openMarketBuys}
        />
        <StatTile
          label={`Discretionary sales, ${headline.windowDays} days to ${headline.asOf}`}
          value={headline.discretionarySales}
        />
        <StatTile
          label={`Symbols with cluster buying, ${headline.windowDays} days to ${headline.asOf}`}
          value={headline.clusterBuys}
        />
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={filter} onValueChange={setFilter} className="min-w-0">
          <TabsList className="flex-wrap group-data-horizontal/tabs:h-auto">
            {FILTERS.map((f) => (
              <TabsTrigger key={f.value} value={f.value}>
                {f.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Input
          placeholder="Search ticker, issuer, or insider…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="sm:w-64"
        />
      </div>

      <Explain>
        <p>
          <strong>Code, not label.</strong> An award (code A) or option exercise (M/X) is never a purchase; tax
          withholding (F) or a gift (G) is never a sale. Sells split into <strong>Planned</strong> (a Rule 10b5-1
          trading plan) and <strong>Discretionary</strong> -- an unchecked or missing box reads "Not stated", never
          discretionary.
        </p>
      </Explain>
      <TradesTable trades={filtered} />

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">Cluster buying</h2>
        <Explain>
          <p>Three or more distinct insiders buying the same stock in the same window -- the one insider signal with real published support. A single buy is noise more often than not.</p>
        </Explain>
        <ClusterTable clusters={feed.clusters} />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">Insiders buying tracked names</h2>
        <Explain>
          <p>Open-market buying on a stock at least one tracked manager already holds -- a signal neither pipeline can state alone.</p>
        </Explain>
        <VsThirteenFTable rows={feed.vsThirteenF} />
      </section>
    </div>
  )
}
