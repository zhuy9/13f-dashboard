import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMeta } from '@/context/MetaContext'
import { useWatchlist } from '@/hooks/useWatchlist'
import { quarterLabel } from '@/format'

export function WatchlistPage() {
  const { meta } = useMeta()
  const { state, check, remove } = useWatchlist()
  const [status, setStatus] = useState('Checking saved reports…')
  useEffect(() => {
    if (meta) void check(meta).then(() => setStatus('Checked against the dataset loaded for this visit.')).catch(e => setStatus(e.message))
    // Check once per dataset; local updates must not trigger another check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta])
  return <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4">
    <h1 className="text-2xl font-semibold">Watchlist</h1>
    <p className="text-sm text-ink-muted">Saved only in this browser. Saving a name sets its latest-report baseline; changes appear on later visits. Clearing browser storage removes your list and digest.</p>
    <button className="self-start text-call underline" onClick={() => window.location.reload()}>Reload to check latest data</button>
    <p role="status">{state.error || status}</p>
    {!state.items.length && <p>Open a stock or manager and choose “Watch this name”.</p>}
    <ul>{state.items.map(i => <li key={`${i.kind}:${i.id}`} className="flex flex-wrap gap-4 py-1">
      <Link className="text-call underline" to={`/${i.kind}/${encodeURIComponent(i.id)}?period=${i.report.period}`}>{i.label}</Link>
      <button className="text-sm text-ink-muted underline" onClick={() => remove(i.kind, i.id)}>Remove {i.label}</button>
    </li>)}</ul>
    <h2 className="text-lg font-medium">Changes since saving</h2>
    {!state.events.length && <p>No changed reports since your saved baseline.</p>}
    {state.events.map(e => <article key={e.eventId} className="border-t border-line py-3">
      <p><Link className="text-call underline" to={`/${e.kind}/${encodeURIComponent(e.id)}?period=${e.report.period}`}>{e.label}</Link> · {e.change} · {quarterLabel(e.report.period)}</p>
      <p className="text-sm">{e.report.summary}</p>
      <p className="text-sm">{e.report.sources.length ? e.report.sources.map((url, i) => <a key={url} href={url} className="mr-3 text-call underline" target="_blank" rel="noreferrer">Source filing {i + 1}</a>) : 'Source links unavailable in this dataset.'}</p>
    </article>)}
  </div>
}
