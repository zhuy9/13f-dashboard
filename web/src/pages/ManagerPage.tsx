import { lazy, Suspense } from 'react'
import { useParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { WatchButton } from '@/components/WatchButton'
import { CsvExport } from '@/components/CsvExport'
import { Explain, SharesVsWeight, SplitBasis, WeightBasis } from '@/components/Explain'
import { ManagerLists } from '@/components/manager/ManagerLists'
import { OwnershipFilings } from '@/components/manager/OwnershipFilings'
import { PositionsTable } from '@/components/manager/PositionsTable'
import { SectorQoQTable } from '@/components/manager/SectorQoQTable'
import { SimilarManagers } from '@/components/manager/SimilarManagers'
import { SourceFilings } from '@/components/manager/SourceFilings'
import { QuarterSelect } from '@/components/QuarterSelect'
import { SectorBars } from '@/components/SectorBars'
import { StatTile } from '@/components/StatTile'
import { Badge } from '@/components/ui/badge'
import { useMeta } from '@/context/MetaContext'
import { getManager, getManagerQuarter } from '@/data'
import { filedDate, money, quarterLabel } from '@/format'
import { useAsyncData } from '@/hooks/useAsyncData'
import { usePeriodParam } from '@/hooks/useSearchParam'

// Recharts is the heaviest dependency in the app and only three views draw a chart.
const PositionsTreemap = lazy(() =>
  import('@/components/manager/PositionsTreemap').then((m) => ({ default: m.PositionsTreemap })),
)

export function ManagerPage() {
  const { cik = '' } = useParams<{ cik: string }>()
  const { meta } = useMeta()
  const managerState = useAsyncData(() => getManager(cik), [cik])
  const manager = managerState.data
  const [period, setPeriod] = usePeriodParam(manager?.periods.at(-1))

  const mqState = useAsyncData(
    () => (cik && period ? getManagerQuarter(cik, period) : Promise.resolve(null)),
    [cik, period],
  )

  const missingThisQuarter = meta?.coverage.find((c) => c.period === period)?.missing.includes(cik) ?? false

  if (managerState.loading) return <LoadingState />
  if (managerState.error) return <ErrorState message={managerState.error} />
  if (!manager) return <EmptyState message="Manager not found." />

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">{manager.name}</h1>
          <Badge variant="secondary">{manager.cluster}</Badge>
        </div>
        <div className="flex flex-col items-end gap-1">
          <QuarterSelect periods={manager.periods} value={period} onChange={setPeriod} />
          {/* The quarter the holdings describe and the day the filing appeared are different
              dates; the last pipeline refresh is a third, stated once in the bar at the top. */}
          {mqState.data && (
            <span className="text-xs text-ink-muted">
              Holdings as of {period && quarterLabel(period)} · filed {filedDate(mqState.data.filedAt)}
            </span>
          )}
          <WatchButton kind="manager" id={cik} label={manager.short} />
        </div>
      </header>

      {mqState.loading && <LoadingState />}
      {/* An error is not an empty portfolio. Saying "no filing" when the read failed invents a
          fact about the manager out of a network problem. */}
      {mqState.error && <ErrorState message={mqState.error} />}
      {!mqState.loading && !mqState.error && !mqState.data && (
        <EmptyState
          message={
            missingThisQuarter
              ? `No 13F filing from ${manager.short} for this quarter. That is missing data, not a portfolio of zero.`
              : 'No filing for this quarter.'
          }
        />
      )}

      {mqState.data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
            <StatTile label="Reported Total" value={money(mqState.data.totalValue)} />
            <StatTile label="Equity Value" value={money(mqState.data.equityValue)} />
            <StatTile label="Positions" value={mqState.data.count} />
            <StatTile label="New" value={mqState.data.counts.new} />
            <StatTile label="Added" value={mqState.data.counts.added} />
            <StatTile label="Trimmed" value={mqState.data.counts.trimmed} />
            <StatTile label="Sold Out" value={mqState.data.counts.soldOut} />
          </div>

          <section>
            <h2 className="mb-2 text-lg font-medium">Top 25 Positions by Weight</h2>
            <Suspense fallback={<LoadingState />}>
              <PositionsTreemap positions={mqState.data.positions} />
            </Suspense>
          </section>

          <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <h2 className="mb-2 text-lg font-medium">Sector Exposure</h2>
              <SectorBars sectors={mqState.data.sectors} />
            </div>
            <div>
              <h2 className="mb-2 text-lg font-medium">Sector QoQ</h2>
              <CsvExport rows={mqState.data.sectors} name={`${manager.short}-sectors`} accessions={mqState.data.filings.map(f => f.accession)} />
              <SectorQoQTable sectors={mqState.data.sectors} />
            </div>
          </section>

          <section>
            <h2 className="mb-1 text-lg font-medium">Positions</h2>
            <Explain>
              <SharesVsWeight />
              <SplitBasis />
              <p>
                <em>UNADJUSTED?</em> marks a share count that moved like a split with no corporate action on file to
                confirm one, so that comparison may not be like-for-like.
              </p>
              <p>
                <em>AMENDED</em> means the holding was first reported in an amended filing, usually because it was
                confidential. That is when it was disclosed, not when it was bought.
              </p>
              <WeightBasis />
              <p>
                Notes and warrants are listed here and badged; option positions are not listed at all. A{' '}
                <em>Reported Put Exposure</em> or <em>Reported Call Exposure</em> badge means the manager also reported
                that option side on the same name, so the long may be hedged. Put exposure is not a short.
              </p>
            </Explain>
            <CsvExport rows={mqState.data.positions} name={`${manager.short}-positions`} accessions={mqState.data.filings.map(f => f.accession)} />
            <PositionsTable positions={mqState.data.positions} options={mqState.data.options} />
          </section>

          {mqState.data.filings.length > 0 && (
            <section>
              <h2 className="mb-1 text-lg font-medium">Source Filings</h2>
              <Explain summary="Why more than one filing?">
                <p>
                  A quarter normally has one filing. It has more when the manager amended it, or when the firm reports
                  one book under several CIKs — both are combined into the numbers above.
                </p>
              </Explain>
              <SourceFilings filings={mqState.data.filings} cik={cik} />
            </section>
          )}

          <section>
            <ManagerLists positions={mqState.data.positions} />
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium">Most Similar Managers</h2>
            <SimilarManagers managers={mqState.data.mostSimilar} />
          </section>
        </>
      )}

      <OwnershipFilings cik={cik} latestPeriod={manager.periods.at(-1)} />
    </div>
  )
}
