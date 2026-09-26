import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { Explain } from '@/components/Explain'
import { FeedFilters } from '@/components/FeedFilters'
import { ClusterTable, VsThirteenFTable } from '@/components/insider/ClusterTable'
import { TradesTable } from '@/components/insider/TradesTable'
import { StatTile } from '@/components/StatTile'
import { getInsiderFeed } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'
import { useFeedFilter } from '@/hooks/useSearchParam'
import { filterTrades, TRADE_FILTERS } from '@/insider'

export function InsiderPage() {
  const feedState = useAsyncData(getInsiderFeed, [])
  const { filter, query } = useFeedFilter()

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

      <FeedFilters filters={TRADE_FILTERS} placeholder="Search ticker, issuer, or insider…" />

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
