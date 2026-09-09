import { Suspense, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { CsvExport } from '@/components/CsvExport'
import { Explain } from '@/components/Explain'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useMeta } from '@/context/MetaContext'
import { quarterLabel } from '@/format'
import { useActiveSection } from '@/hooks/useActiveSection'
import { useAsyncData } from '@/hooks/useAsyncData'
import { getSubsetSignals } from '@/subsetData'
import { buildSections } from './patterns/sections'
import { Notable } from './patterns/Notable'
import { UniverseFilter } from './patterns/UniverseFilter'

export function PatternsPage() {
  const { meta, loading: metaLoading, error: metaError } = useMeta()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlPeriod = searchParams.get('period')
  const period = urlPeriod ?? meta?.latestPeriod ?? null
  const universe = searchParams.get('managers')
  const minimumParam = searchParams.get('min')
  const selected = universe == null ? meta?.managers.map(m => m.cik) ?? [] : [...new Set(universe.split(',').filter(Boolean))]
  const minimum = minimumParam == null ? undefined : Number(minimumParam)

  useEffect(() => {
    if (meta && !urlPeriod) {
      setSearchParams(prev => { const next = new URLSearchParams(prev); next.set('period', meta.latestPeriod); return next }, { replace: true })
    }
  }, [meta, urlPeriod, setSearchParams])

  const signalsState = useAsyncData(() => (period ? getSubsetSignals(period, universe == null ? null : selected, minimum) : Promise.resolve(null)), [period, universe, minimum])

  const labelByCik = useMemo(() => {
    const map = new Map<string, string>()
    for (const m of meta?.managers ?? []) map.set(m.cik, m.short)
    return map
  }, [meta])

  const sections = useMemo(
    () => (signalsState.data ? buildSections(signalsState.data, labelByCik) : []),
    [signalsState.data, labelByCik],
  )
  const fullCoverage = meta?.coverage?.find((c) => c.period === period)
  const coverage = fullCoverage && { period, filed: fullCoverage.filed.filter(c => selected.includes(c)), missing: fullCoverage.missing.filter(c => selected.includes(c)) }
  const threshold = (minimum != null && Number.isFinite(minimum) ? minimum : undefined) ?? signalsState.data?.config?.consensusMinManagers ?? 3
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
          <Select value={period ?? undefined} onValueChange={(value) => setSearchParams(prev => { const next = new URLSearchParams(prev); next.set('period', value); return next })}>
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

      <div className="flex flex-col gap-3">
        <p className="max-w-3xl text-sm text-ink-muted">
          Every signal on this page is computed across the {selected.length} selected managers for one quarter, from
          their 13F filings. Each table explains what it counts, and ranked rows open to name the managers behind them.
          Start with a card below, or jump to any table.
        </p>
        {signalsState.data && <Notable data={signalsState.data} />}
      </div>

      <UniverseFilter managers={meta.managers} selected={selected} minimum={threshold} />
      {selected.length === 0 ? <p role="status">No managers selected. Choose a manager or style.</p>
        : (coverage?.filed.length ?? selected.length) < threshold && <p role="status">Fewer filing managers than the minimum of {threshold}; consensus tables may be empty.</p>}
      {coverage && (
        <p className="text-sm text-ink-muted">
          {coverage.filed.length} of {coverage.filed.length + coverage.missing.length} tracked managers have a filing
          for this quarter.
          {coverage.missing.length > 0 && (
            <>
              {' '}
              No filing from {coverage.missing.map((c) => labelByCik.get(c) ?? c).join(', ')} — that is missing data,
              not a portfolio of zero, and those managers are left out of the averages rather than counted as holding
              nothing.
            </>
          )}
        </p>
      )}

      {signalsState.loading && <LoadingState />}
      {signalsState.error && <ErrorState message={signalsState.error} />}
      {!signalsState.loading && !signalsState.error && !signalsState.data && (
        <EmptyState message="No signals for this quarter." />
      )}

      {sections.map((s) => (
        <section key={s.id} id={s.id} className="scroll-mt-40">
          <h2 className="mb-1 text-lg font-medium">{s.label}</h2>
          <Explain>{s.help}</Explain>
          {s.rows && <CsvExport rows={s.rows} name={s.id} accessions={signalsState.data?.filings?.map(f => f.accession)} universe={selected} minimum={threshold} />}
          <Suspense fallback={<LoadingState />}>{s.node}</Suspense>
        </section>
      ))}
    </div>
  )
}
