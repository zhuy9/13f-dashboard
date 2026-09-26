import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { FeedFilters } from '@/components/FeedFilters'
import { EventsTable } from '@/components/ownership/EventsTable'
import { StatTile } from '@/components/StatTile'
import { getOwnershipFeed } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'
import { useFeedFilter } from '@/hooks/useSearchParam'
import { EVENT_FILTERS, filterEvents } from '@/ownership'

export function OwnershipPage() {
  const feedState = useAsyncData(getOwnershipFeed, [])
  const { filter, query } = useFeedFilter()

  if (feedState.loading) return <LoadingState />
  if (feedState.error) return <ErrorState message={feedState.error} />
  if (!feedState.data) return <EmptyState message="No ownership data yet." />

  const feed = feedState.data
  // Counted in the pipeline over every event on file. Counting them here meant counting the
  // newest `recent_events` rows only, and the 7-day window was measured back from the newest
  // filing rather than from today, so it could never report a quiet week.
  const { headline } = feed

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold">Ownership</h1>
        <p className="text-sm text-ink-muted">
          Schedule 13D and 13G filings, since {feed.startDate}. Counts below are as of {headline.asOf}.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile label={`Filings, ${headline.windowDays} days to ${headline.asOf}`} value={headline.filingsInWindow} />
        <StatTile label={`New 13Ds since ${headline.startDate}`} value={headline.new13dSinceStart} />
        <StatTile label={`Activist entries since ${headline.startDate}`} value={headline.activistEntriesSinceStart} />
      </div>

      <FeedFilters filters={EVENT_FILTERS} placeholder="Search ticker, issuer, or investor…" />
      <EventsTable events={filterEvents(feed.events, filter, query)} />
    </div>
  )
}
