import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, RefreshCw, Star, X } from 'lucide-react'
import { ColorBadge } from '@/components/ColorBadge'
import { Button } from '@/components/ui/button'
import { useMeta } from '@/context/MetaContext'
import { useWatchlist } from '@/hooks/useWatchlist'
import { eventId, type WatchEvent } from '@/watchlist'
import { quarterLabel } from '@/format'

// A revision to a quarter already published is a different thing from a new quarter, and a
// recalculation is a change in our arithmetic rather than in anyone's holdings. Colour says
// which before the text does.
const CHANGE_COLORS: Record<WatchEvent['change'], string> = {
  'New quarterly report': '#1a7f37',
  'Revised quarterly report': '#9a6700',
  'Methodology recalculation': '#6b6759',
}

export function WatchlistPage() {
  const { meta } = useMeta()
  const { state, check, remove } = useWatchlist()
  const [status, setStatus] = useState('Checking saved reports…')
  const [checking, setChecking] = useState(false)
  useEffect(() => {
    if (!meta) return
    setChecking(true)
    void check(meta)
      .then(() => setStatus('Checked against the dataset loaded for this visit.'))
      .catch((e: Error) => setStatus(e.message))
      .finally(() => setChecking(false))
    // Check once per dataset; local updates must not trigger another check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta])

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header className="flex flex-col gap-3 border-b border-line pb-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
          <h1 className="text-2xl font-semibold">
            Watchlist
            {state.items.length > 0 && (
              <span className="ml-2 font-tabular text-lg font-normal text-ink-muted">{state.items.length}</span>
            )}
          </h1>
          <Button variant="outline" size="sm" onClick={() => window.location.reload()} disabled={checking}>
            <RefreshCw className={checking ? 'animate-spin' : ''} />
            Check latest data
          </Button>
        </div>
        <p className="max-w-3xl text-sm text-ink-muted">
          Saved only in this browser. Saving a name sets its latest-report baseline; changes appear on later visits.
          Clearing browser storage removes your list and digest.
        </p>
        <p role="status" className={`text-sm ${state.error ? 'text-put' : 'text-ink-muted'}`}>
          {state.error || status}
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">Saved names</h2>
        {state.items.length === 0 ? (
          <EmptyPanel>
            <Star className="mx-auto mb-2 block size-5 text-ink-muted" />
            Open a stock or manager and choose <strong className="font-medium text-ink">Watch this name</strong> to
            start a baseline.
          </EmptyPanel>
        ) : (
          <ul className="border-b border-line">
            {state.items.map((i) => (
              <li key={`${i.kind}:${i.id}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line py-2">
                <ColorBadge color={i.kind === 'stock' ? '#0969da' : '#6b6759'} label={i.kind === 'stock' ? 'Stock' : 'Manager'} />
                <Link
                  className="font-medium text-call hover:underline"
                  to={`/${i.kind}/${encodeURIComponent(i.id)}?period=${i.report.period}`}
                >
                  {i.label}
                </Link>
                <span className="font-tabular text-sm text-ink-muted">{quarterLabel(i.report.period)}</span>
                <span className="ml-auto truncate text-sm text-ink-muted">{i.report.summary}</span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Remove ${i.label} from your watchlist`}
                  onClick={() => remove(i.kind, i.id)}
                >
                  <X />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">Changes since saving</h2>
        {state.events.length === 0 ? (
          <EmptyPanel>No changed reports since your saved baseline.</EmptyPanel>
        ) : (
          <ul className="flex flex-col gap-3">
            {state.events.map((e) => (
              <li key={eventId(e)} className="rounded border border-line bg-paper p-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <ColorBadge color={CHANGE_COLORS[e.change]} label={e.change} />
                  <Link
                    className="font-medium text-call hover:underline"
                    to={`/${e.kind}/${encodeURIComponent(e.id)}?period=${e.report.period}`}
                  >
                    {e.label}
                  </Link>
                  <span className="font-tabular text-sm text-ink-muted">{quarterLabel(e.report.period)}</span>
                </div>
                <p className="mt-2 font-tabular text-sm">{e.report.summary}</p>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                  {e.report.sources.length ? (
                    e.report.sources.map((url, index) => (
                      <a
                        key={url}
                        href={url}
                        className="inline-flex items-center gap-1 text-call hover:underline"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Source filing {index + 1}
                        <ExternalLink className="size-3" />
                      </a>
                    ))
                  ) : (
                    <span className="text-ink-muted">Source links unavailable in this dataset.</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function EmptyPanel({ children }: { children: ReactNode }) {
  return (
    <p className="rounded border border-dashed border-line px-4 py-6 text-center text-sm text-ink-muted">{children}</p>
  )
}
