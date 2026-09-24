import { lazy, Suspense } from 'react'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { Explain } from '@/components/Explain'
import { CopyabilityTable } from '@/components/managers/CopyabilityTable'
import { ManagerLink } from '@/components/ManagerLink'
import { StockLink } from '@/components/StockLink'
import { useMeta } from '@/context/MetaContext'

const CopyabilityChart = lazy(() =>
  import('@/components/managers/CopyabilityChart').then((m) => ({ default: m.CopyabilityChart })),
)

export function ManagersPage() {
  const { meta, loading, error } = useMeta()

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />
  if (!meta) return <EmptyState message="No data available." />

  const shortByCik = new Map(meta.managers.map((m) => [m.cik, m.short]))

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <h1 className="text-2xl font-semibold">Managers</h1>
      {meta.copyability && meta.copyability.length > 0 && (
        <section>
          <h2 className="mb-1 text-lg font-medium">Copyability</h2>
          <Explain>
            <p>
              How well a copy of the last 13F can track the manager, mechanically. A filing is 45 to 135 days
              old when you read it, so a copy works best for managers who trade rarely and hold a few names in
              size. This says nothing about whether the book is any good.
            </p>
            <p>
              <em>Turnover</em> is half the sum of absolute weight changes in a quarter, averaged over the
              window. <em>Top 10 weight</em> is the share of equity in the ten largest positions at the latest
              quarter. <em>New still held</em> is the share of new positions still on the book four quarters
              later, where the window can tell.
            </p>
          </Explain>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <Suspense fallback={<LoadingState />}>
              <CopyabilityChart rows={meta.copyability} />
            </Suspense>
            <CopyabilityTable rows={meta.copyability} />
          </div>
        </section>
      )}
      {meta.clusters.length === 0 ? (
        <EmptyState message="No clusters available." />
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {meta.clusters.map((cluster) => (
            <div key={cluster.label} className="rounded border border-line p-4">
              <h2 className="text-lg font-medium">{cluster.label}</h2>
              <p className="mt-1 text-xs text-ink-muted">Top sector: {cluster.topSector ?? '—'}</p>

              <h3 className="mt-3 text-sm font-medium">Members</h3>
              <ul className="mt-1 flex flex-col gap-1 text-sm">
                {cluster.members.map((cik) => (
                  <li key={cik}>
                    <ManagerLink cik={cik} label={shortByCik.get(cik) ?? cik} />
                  </li>
                ))}
              </ul>

              <h3 className="mt-3 text-sm font-medium">Common Holdings</h3>
              {cluster.commonHoldings.length === 0 ? (
                <p className="mt-1 text-sm text-ink-muted">None.</p>
              ) : (
                <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm">
                  {cluster.commonHoldings.map((symbol) => (
                    <li key={symbol}>
                      <StockLink symbol={symbol} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
