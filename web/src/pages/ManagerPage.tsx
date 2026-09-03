import { useEffect, useMemo } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { ManagerLists } from '@/components/manager/ManagerLists'
import { PositionsTable } from '@/components/manager/PositionsTable'
import { PositionsTreemap } from '@/components/manager/PositionsTreemap'
import { SectorQoQTable } from '@/components/manager/SectorQoQTable'
import { SimilarManagers } from '@/components/manager/SimilarManagers'
import { SectorBars } from '@/components/SectorBars'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useMeta } from '@/context/MetaContext'
import { getManager, getManagerQuarter } from '@/data'
import { money, quarterLabel } from '@/format'
import { useAsyncData } from '@/hooks/useAsyncData'

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-line px-4 py-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="font-tabular text-xl font-semibold">{value}</div>
    </div>
  )
}

export function ManagerPage() {
  const { cik = '' } = useParams<{ cik: string }>()
  const { meta } = useMeta()
  const [searchParams, setSearchParams] = useSearchParams()

  const managerState = useAsyncData(() => getManager(cik), [cik])
  const manager = managerState.data
  const urlPeriod = searchParams.get('period')
  const period = urlPeriod ?? manager?.periods.at(-1) ?? null

  useEffect(() => {
    if (manager && !urlPeriod) {
      setSearchParams({ period: manager.periods.at(-1) ?? '' }, { replace: true })
    }
  }, [manager, urlPeriod, setSearchParams])

  const mqState = useAsyncData(
    () => (cik && period ? getManagerQuarter(cik, period) : Promise.resolve(null)),
    [cik, period],
  )

  const sectorBySymbol = useMemo(() => {
    const map = new Map<string, string>()
    for (const s of meta?.symbols ?? []) map.set(s.symbol, s.sector)
    return map
  }, [meta])

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
        <Select value={period ?? undefined} onValueChange={(value) => setSearchParams({ period: value })}>
          <SelectTrigger>
            <SelectValue placeholder="Period" />
          </SelectTrigger>
          <SelectContent>
            {manager.periods.map((p) => (
              <SelectItem key={p} value={p}>
                {quarterLabel(p)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </header>

      {mqState.loading && <LoadingState />}
      {mqState.error && <ErrorState message={mqState.error} />}
      {!mqState.loading && !mqState.error && !mqState.data && (
        <EmptyState message="No filing for this quarter." />
      )}

      {mqState.data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
            <StatTile label="Total Value" value={money(mqState.data.totalValue)} />
            <StatTile label="Positions" value={mqState.data.count} />
            <StatTile label="New" value={mqState.data.counts.new} />
            <StatTile label="Added" value={mqState.data.counts.added} />
            <StatTile label="Trimmed" value={mqState.data.counts.trimmed} />
            <StatTile label="Sold Out" value={mqState.data.counts.soldOut} />
          </div>

          <section>
            <h2 className="mb-2 text-lg font-medium">Top 25 Positions by Weight</h2>
            <PositionsTreemap positions={mqState.data.positions} sectorBySymbol={sectorBySymbol} />
          </section>

          <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <h2 className="mb-2 text-lg font-medium">Sector Exposure</h2>
              <SectorBars sectors={mqState.data.sectors} />
            </div>
            <div>
              <h2 className="mb-2 text-lg font-medium">Sector QoQ</h2>
              <SectorQoQTable sectors={mqState.data.sectors} />
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium">Positions</h2>
            <PositionsTable positions={mqState.data.positions} />
          </section>

          <section>
            <ManagerLists positions={mqState.data.positions} />
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium">Most Similar Managers</h2>
            <SimilarManagers managers={mqState.data.mostSimilar} />
          </section>
        </>
      )}
    </div>
  )
}
