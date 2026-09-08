import { useMeta } from '@/context/MetaContext'
import { filingDue, nextPeriod, quarterLabel } from '@/format'

// A 13F covers a quarter but is not due until 45 days after it ends, so the newest quarter on
// the site is always behind the calendar. Say which one and when the next lands, rather than
// leaving a visitor in September to wonder why the data stops at June.
export function FilingLag() {
  const { meta } = useMeta()
  if (!meta) return null
  const next = nextPeriod(meta.latestPeriod)
  return (
    <p className="border-b border-line bg-paper px-4 py-1.5 text-center text-xs text-ink-muted">
      Showing {quarterLabel(meta.latestPeriod)} filings, which were due {filingDue(meta.latestPeriod)}.{' '}
      {quarterLabel(next)} filings are due {filingDue(next)}.
    </p>
  )
}
