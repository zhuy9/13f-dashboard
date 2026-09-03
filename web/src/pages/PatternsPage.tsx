import { useEffect, useMemo, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useMeta } from '@/context/MetaContext'
import { getSignals } from '@/data'
import { quarterLabel } from '@/format'
import { useActiveSection } from '@/hooks/useActiveSection'
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
import type { Signals } from '@/types'

interface Section {
  id: string
  label: string
  node: ReactNode
}

function buildSections(data: Signals, labelByCik: Map<string, string>): Section[] {
  return [
    { id: 'consensus-buys', label: 'Consensus Buys', node: <ConsensusBuys rows={data.consensusBuys} /> },
    { id: 'consensus-exits', label: 'Consensus Exits', node: <ConsensusExits rows={data.consensusExits} /> },
    { id: 'high-conviction', label: 'High Conviction', node: <HighConviction rows={data.highConviction} /> },
    { id: 'biggest-new', label: 'Biggest New', node: <BiggestNew rows={data.biggestNew} /> },
    { id: 'biggest-adds', label: 'Biggest Adds', node: <BiggestAdds rows={data.biggestAdds} /> },
    { id: 'biggest-trims', label: 'Biggest Trims', node: <BiggestTrims rows={data.biggestTrims} /> },
    { id: 'sector-rotation', label: 'Sector Rotation', node: <SectorRotation rows={data.sectorRotation} /> },
    { id: 'fastest-growing', label: 'Fastest Growing', node: <FastestGrowing rows={data.fastestGrowing} /> },
    {
      id: 'manager-similarity',
      label: 'Manager Similarity',
      node: <ManagerSimilarity similarity={data.managerSimilarity} labelByCik={labelByCik} />,
    },
    {
      id: 'put-call-exposure',
      label: 'Put/Call Exposure',
      node: <PutCallExposure rows={data.optionsExposure} labelByCik={labelByCik} />,
    },
  ]
}

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

  const sections = signalsState.data ? buildSections(signalsState.data, labelByCik) : []
  const sectionIds = useMemo(() => sections.map((s) => s.id), [sections])
  const activeId = useActiveSection(sectionIds)

  if (metaLoading) return <LoadingState />
  if (metaError) return <ErrorState message={metaError} />
  if (!meta) return <EmptyState message="No data available." />

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <div className="sticky top-14 z-10 -mx-4 flex flex-col gap-3 border-b border-line bg-paper px-4 py-3">
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

        <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {sections.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className={s.id === activeId ? 'font-medium text-ink' : 'text-ink-muted hover:text-ink'}
            >
              {s.label}
            </a>
          ))}
        </nav>
      </div>

      {signalsState.loading && <LoadingState />}
      {signalsState.error && <ErrorState message={signalsState.error} />}
      {!signalsState.loading && !signalsState.error && !signalsState.data && (
        <EmptyState message="No signals for this quarter." />
      )}

      {sections.map((s) => (
        <section key={s.id} id={s.id} className="scroll-mt-40">
          <h2 className="mb-2 text-lg font-medium">{s.label}</h2>
          {s.node}
        </section>
      ))}
    </div>
  )
}
