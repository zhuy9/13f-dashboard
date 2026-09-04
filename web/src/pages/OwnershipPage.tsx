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

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000

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

  const cutoff = feed.lastFiledAt ? new Date(feed.lastFiledAt).getTime() - SEVEN_DAYS_MS : null
  const recentCount = cutoff === null ? 0 : feed.events.filter((e) => new Date(e.filedAt).getTime() >= cutoff).length
  const new13dCount = feed.events.filter((e) => e.event === 'NEW' && e.form === '13D').length
  const activistCount = feed.events.filter(
    (e) => e.isActivist && (e.event === 'NEW' || e.event === 'SWITCHED_TO_13D'),
  ).length

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold">Ownership</h1>
        <p className="text-sm text-ink-muted">Schedule 13D and 13G filings, since {feed.startDate}.</p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile label="Filings, last 7 days" value={recentCount} />
        <StatTile label="New 13Ds" value={new13dCount} />
        <StatTile label="Activist entries" value={activistCount} />
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={filter} onValueChange={setFilter} className="min-w-0 overflow-x-auto">
          <TabsList>
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
