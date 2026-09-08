import { useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { EventsTable } from '@/components/ownership/EventsTable'
import { StatTile } from '@/components/StatTile'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getOwnershipFeed } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'
import { filterEvents } from '@/ownership'
import type { OwnershipFilter } from '@/ownershipTypes'

const FILTERS: { value: OwnershipFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: '13d', label: '13D' },
  { value: '13g', label: '13G' },
  { value: 'new', label: 'New' },
  { value: 'increased', label: 'Increased' },
  { value: 'decreased', label: 'Decreased' },
  { value: 'activists', label: 'Activists' },
]

export function OwnershipPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const feedState = useAsyncData(getOwnershipFeed, [])

  const filter = (searchParams.get('filter') as OwnershipFilter | null) ?? 'all'
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
  if (!feedState.data) return <EmptyState message="No ownership data yet." />

  const feed = feedState.data
  const filtered = filterEvents(feed.events, filter, query)

  // Counted in the pipeline over every event on file. Counting them here meant counting the
  // newest `recent_events` rows only, and the 7-day window was measured back from the newest
  // filing rather than from today, so it could never report a quiet week.
  const { headline } = feed

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold">Ownership</h1>
        <p className="text-sm text-ink-muted">
          Schedule 13D and 13G filings, since {feed.startDate}.
          {headline && ` Counts below are as of ${headline.asOf}.`}
        </p>
      </header>

      {/* No headline block means the feed predates these counts. Showing a dash beats
          recomputing them here from the truncated event list, which is the bug this replaced. */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile
          label={headline ? `Filings, ${headline.windowDays} days to ${headline.asOf}` : 'Filings, last 7 days'}
          value={headline ? headline.filingsInWindow : '—'}
        />
        <StatTile
          label={`New 13Ds since ${headline?.startDate ?? feed.startDate}`}
          value={headline ? headline.new13dSinceStart : '—'}
        />
        <StatTile
          label={`Activist entries since ${headline?.startDate ?? feed.startDate}`}
          value={headline ? headline.activistEntriesSinceStart : '—'}
        />
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Wrap rather than scroll. overflow-x-auto forces overflow-y to auto too, so the
            horizontal scrollbar's own height produced a second, vertical one -- and a hidden
            scrollbar would leave the last filters unreachable without a shift-scroll. */}
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
          placeholder="Search ticker, issuer, or investor…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="sm:w-64"
        />
      </div>

      <EventsTable events={filtered} />
    </div>
  )
}
