import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useMeta } from '@/context/MetaContext'
import { getSignals } from '@/data'
import { quarterLabel } from '@/format'
import { useAsyncData } from '@/hooks/useAsyncData'
import { BiggestAdds } from '@/pages/patterns/BiggestAdds'
import { BiggestNew } from '@/pages/patterns/BiggestNew'
import { BiggestTrims } from '@/pages/patterns/BiggestTrims'
import { ConsensusBuys } from '@/pages/patterns/ConsensusBuys'
import { ConsensusExits } from '@/pages/patterns/ConsensusExits'
import { FastestGrowing } from '@/pages/patterns/FastestGrowing'
import { HighConviction } from '@/pages/patterns/HighConviction'
import { ManagerSimilarity } from '@/pages/patterns/ManagerSimilarity'
import { PutCallExposure } from '@/pages/patterns/PutCallExposure'
import { SectorRotation } from '@/pages/patterns/SectorRotation'

const SECTIONS = [
  { id: 'consensus-buys', label: 'Consensus Buys' },
  { id: 'consensus-exits', label: 'Consensus Exits' },
  { id: 'high-conviction', label: 'High Conviction' },
  { id: 'biggest-new', label: 'Biggest New' },
  { id: 'biggest-adds', label: 'Biggest Adds' },
  { id: 'biggest-trims', label: 'Biggest Trims' },
  { id: 'sector-rotation', label: 'Sector Rotation' },
  { id: 'fastest-growing', label: 'Fastest Growing' },
  { id: 'manager-similarity', label: 'Manager Similarity' },
  { id: 'put-call-exposure', label: 'Put/Call Exposure' },
]

export function PatternsPage() {
  const { meta, loading: metaLoading, error: metaError } = useMeta()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlPeriod = searchParams.get('period')
  const period = urlPeriod ?? meta?.latestPeriod ?? null

  useEffect(() => {
    if (meta && !urlPeriod) {
      setSearchParams({ period: meta.latestPeriod }, { replace: true })
    }
  }, [meta, urlPeriod, setSearchParams])

  const signalsState = useAsyncData(() => (period ? getSignals(period) : Promise.resolve(null)), [period])

  const labelByCik = useMemo(() => {
    const map = new Map<string, string>()
    for (const m of meta?.managers ?? []) map.set(m.cik, m.short)
    return map
  }, [meta])

  if (metaLoading) return <LoadingState />
  if (metaError) return <ErrorState message={metaError} />
  if (!meta) return <EmptyState message="No data available." />

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Patterns</h1>
        <Select value={period ?? undefined} onValueChange={(value) => setSearchParams({ period: value })}>
          <SelectTrigger>
            <SelectValue placeholder="Period" />
          </SelectTrigger>
          <SelectContent>
            {meta.periods.map((p) => (
              <SelectItem key={p} value={p}>
                {quarterLabel(p)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </header>

      <nav className="sticky top-14 z-10 flex flex-wrap gap-x-4 gap-y-1 border-b border-line bg-paper py-2 text-sm">
        {SECTIONS.map((s) => (
          <a key={s.id} href={`#${s.id}`} className="text-ink-muted hover:text-ink">
            {s.label}
          </a>
        ))}
      </nav>

      {signalsState.loading && <LoadingState />}
      {signalsState.error && <ErrorState message={signalsState.error} />}
      {!signalsState.loading && !signalsState.error && !signalsState.data && (
        <EmptyState message="No signals for this quarter." />
      )}

      {signalsState.data && (
        <>
          <section id="consensus-buys" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Consensus Buys</h2>
            <ConsensusBuys rows={signalsState.data.consensusBuys} />
          </section>
          <section id="consensus-exits" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Consensus Exits</h2>
            <ConsensusExits rows={signalsState.data.consensusExits} />
          </section>
          <section id="high-conviction" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">High Conviction</h2>
            <HighConviction rows={signalsState.data.highConviction} />
          </section>
          <section id="biggest-new" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Biggest New</h2>
            <BiggestNew rows={signalsState.data.biggestNew} />
          </section>
          <section id="biggest-adds" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Biggest Adds</h2>
            <BiggestAdds rows={signalsState.data.biggestAdds} />
          </section>
          <section id="biggest-trims" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Biggest Trims</h2>
            <BiggestTrims rows={signalsState.data.biggestTrims} />
          </section>
          <section id="sector-rotation" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Sector Rotation</h2>
            <SectorRotation rows={signalsState.data.sectorRotation} />
          </section>
          <section id="fastest-growing" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Fastest Growing</h2>
            <FastestGrowing rows={signalsState.data.fastestGrowing} />
          </section>
          <section id="manager-similarity" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Manager Similarity</h2>
            <ManagerSimilarity similarity={signalsState.data.managerSimilarity} labelByCik={labelByCik} />
          </section>
          <section id="put-call-exposure" className="scroll-mt-28">
            <h2 className="mb-2 text-lg font-medium">Put/Call Exposure</h2>
            <PutCallExposure rows={signalsState.data.optionsExposure} labelByCik={labelByCik} />
          </section>
        </>
      )}
    </div>
  )
}
