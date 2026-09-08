import { useMeta } from '@/context/MetaContext'
import { filedDate, filingDue, nextPeriod, quarterLabel } from '@/format'

// A 13F covers a quarter but is not due until 45 days after it ends, so the newest quarter on
// the site is always behind the calendar. Say which one and when the next lands, rather than
// leaving a visitor in September to wonder why the data stops at June.
export function FilingLag() {
  const { meta } = useMeta()
  if (!meta) return null
  const next = nextPeriod(meta.latestPeriod)
  const refreshed = meta.updatedAt ? filedDate(meta.updatedAt.toDate().toISOString().slice(0, 10)) : null
  return (
    <p className="border-b border-line bg-paper px-4 py-1.5 text-center text-xs text-ink-muted">
      Showing {quarterLabel(meta.latestPeriod)} filings, which were due {filingDue(meta.latestPeriod)}.{' '}
      {quarterLabel(next)} filings are due {filingDue(next)}.
      {/* The quarter covered, the due date, and our own last refresh are three different
          things. Naming the refresh separately is what keeps "showing Q2" from reading as
          "updated moments ago". */}
      {refreshed && <> Site data last refreshed {refreshed}.</>}
    </p>
  )
}
