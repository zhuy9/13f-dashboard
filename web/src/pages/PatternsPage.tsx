import { lazy, Suspense, useEffect, useMemo, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { Explain } from '@/components/Explain'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useMeta } from '@/context/MetaContext'
import { getSignals } from '@/data'
import { pct, pp, quarterLabel } from '@/format'
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
import type { Signals } from '@/types'

const SectorRotation = lazy(() => import('@/pages/patterns/SectorRotation').then((m) => ({ default: m.SectorRotation })))

interface Section {
  id: string
  label: string
  node: ReactNode
  help: ReactNode
}

// Every average needs to name the population it averages over, or the number is unreadable.
// "Avg Weight 3%" means nothing until you know whether the denominator is holders, buyers, or
// all 33 tracked managers.
const WEIGHT_BASIS = (
  <p>
    A weight is a position's share of that manager's <strong>reported equity holdings</strong> — not of its total
    assets. Options, convertible notes and warrants are excluded from the denominator.
  </p>
)

const SHARES_VS_WEIGHT = (
  <p>
    <strong>Status is about shares, weight change is about proportion.</strong> A manager can add shares while the
    position's weight falls, because the rest of the book grew faster or the stock lagged it. The two disagreeing is
    not an error.
  </p>
)

function buildSections(data: Signals, labelByCik: Map<string, string>): Section[] {
  return [
    {
      id: 'consensus-buys',
      label: 'Consensus Buys',
      node: <ConsensusBuys rows={data.consensusBuys} />,
      help: (
        <>
          <p>
            Stocks that at least three tracked managers opened or added to this quarter. <em>New Buyers</em> and{' '}
            <em>Added</em> count managers; open <em>Buyers</em> to see which ones.
          </p>
          <p>
            <em>Avg Weight</em> averages over the stock's current holders. <em>Avg Weight Increase</em> averages only
            over the managers who bought or added — the qualifying buyers, not all holders.
          </p>
          <p>
            <em>Score</em> is relative within the quarter: 100 is that quarter's highest raw score, not a probability
            or a rating. Open a score to see its arithmetic. Scores are not comparable across quarters.
          </p>
          {WEIGHT_BASIS}
          <p>
            A manager filing for the first time has no prior quarter to compare against, so its positions count as
            neither new nor added.
          </p>
        </>
      ),
    },
    {
      id: 'consensus-exits',
      label: 'Consensus Exits',
      node: <ConsensusExits rows={data.consensusExits} />,
      help: (
        <>
          <p>
            Stocks that at least three tracked managers trimmed or sold out of. <em>Avg Reduction</em> averages the
            weight change over those sellers only.
          </p>
          <p>
            <strong>Sold Out means the position left the 13F</strong>, which is not the same as the manager selling
            everything: a holding can drop below the reporting threshold, or move to a form a 13F does not cover.
          </p>
          {SHARES_VS_WEIGHT}
        </>
      ),
    },
    {
      id: 'high-conviction',
      label: 'High Conviction',
      node: <HighConviction rows={data.highConviction} />,
      help: (
        <>
          <p>
            Stocks where at least three managers each hold 3% or more of their reported equity book.{' '}
            <em>Managers</em> counts only those qualifying managers — open it to see them.
          </p>
          <p>
            <em>Avg Weight</em> and <em>Max Weight</em> are over those qualifying managers too, not over every holder,
            so both sit above the 3% threshold by construction.
          </p>
          {WEIGHT_BASIS}
        </>
      ),
    },
    {
      id: 'biggest-new',
      label: 'Biggest New',
      node: <BiggestNew rows={data.biggestNew} />,
      help: (
        <>
          <p>The largest brand-new positions this quarter, one row per manager and stock, ranked by weight.</p>
          {WEIGHT_BASIS}
        </>
      ),
    },
    {
      id: 'biggest-adds',
      label: 'Biggest Adds',
      node: <BiggestAdds rows={data.biggestAdds} />,
      help: (
        <>
          <p>The largest increases in weight, one row per manager and stock.</p>
          {SHARES_VS_WEIGHT}
          {WEIGHT_BASIS}
        </>
      ),
    },
    {
      id: 'biggest-trims',
      label: 'Biggest Trims',
      node: <BiggestTrims rows={data.biggestTrims} />,
      help: (
        <>
          <p>The largest decreases in weight, including positions that left the 13F entirely.</p>
          {SHARES_VS_WEIGHT}
        </>
      ),
    },
    {
      id: 'sector-rotation',
      label: 'Sector Rotation',
      node: <SectorRotation rows={data.sectorRotation} />,
      help: (
        <>
          <p>
            Averages run over managers with a comparable prior quarter — a manager that did not file last quarter is
            left out rather than counted as zero. <em>Increasing</em> and <em>Decreasing</em> count managers whose
            sector weight moved by more than half a percentage point.
          </p>
          <p>Sectors come from the issuer's SEC SIC code, not GICS, and an ETF is its own sector.</p>
        </>
      ),
    },
    {
      id: 'fastest-growing',
      label: 'Fastest Growing',
      node: <FastestGrowing rows={data.fastestGrowing} />,
      help: (
        <p>
          Change in the <strong>number of tracked managers holding</strong> the stock, not in its price or value.{' '}
          <em>Exited Managers</em> counts managers whose position left the 13F this quarter.
        </p>
      ),
    },
    {
      id: 'manager-similarity',
      label: 'Manager Similarity',
      node: <ManagerSimilarity similarity={data.managerSimilarity} labelByCik={labelByCik} />,
      help: (
        <p>
          Cosine similarity between managers' equity weight vectors, from 0 (no shared holdings) to 1 (identical
          book). It compares what they report holding, so two managers can look unalike while running the same
          strategy through instruments a 13F never shows.
        </p>
      ),
    },
    {
      id: 'put-call-exposure',
      label: 'Put/Call Exposure',
      node: <PutCallExposure rows={data.optionsExposure} labelByCik={labelByCik} />,
      help: (
        <>
          <p>
            Managers reporting option positions on a stock. An option row's reported value is the value of the{' '}
            <strong>underlying shares</strong> — not the premium paid, not invested capital, and not delta-adjusted
            exposure.
          </p>
          <p>
            A reported put is not evidence of a short bet: it can be a hedge, and a 13F shows neither the strike nor
            the expiry. These rows are excluded from every weight and conviction figure on the site.
          </p>
        </>
      ),
    },
  ]
}

// Picks the top row of tables that Python already ranked -- selection and rendering, not a
// signal computed in the browser. Each card is a way into the full table below it.
function Notable({ data }: { data: Signals }) {
  const cards: { href: string; label: string; symbol: string; detail: string }[] = []
  const buy = data.consensusBuys[0]
  if (buy) {
    cards.push({
      href: '#consensus-buys',
      label: 'Most bought',
      symbol: buy.symbol,
      detail: `${buy.newBuyers} opened, ${buy.added} added`,
    })
  }
  const exit = data.consensusExits[0]
  if (exit) {
    cards.push({
      href: '#consensus-exits',
      label: 'Most sold',
      symbol: exit.symbol,
      detail: `${exit.soldOut} sold out, ${exit.trimmed} trimmed`,
    })
  }
  const crowded = data.highConviction[0]
  if (crowded) {
    cards.push({
      href: '#high-conviction',
      label: 'Most crowded',
      symbol: crowded.symbol,
      detail: `${crowded.managers} managers at ${pct(crowded.avgWeight)} average`,
    })
  }
  const rotation = data.sectorRotation[0]
  if (rotation) {
    cards.push({
      href: '#sector-rotation',
      label: 'Sector moving in',
      symbol: rotation.sector,
      detail: `${pp(rotation.avgChange)} average weight`,
    })
  }
  if (cards.length === 0) return null

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {cards.map((c) => (
        <a key={c.label} href={c.href} className="rounded border border-line px-4 py-3 hover:border-ink-muted">
          <div className="text-xs text-ink-muted">{c.label}</div>
          <div className="truncate font-tabular text-lg font-semibold">{c.symbol}</div>
          <div className="truncate text-xs text-ink-muted">{c.detail}</div>
        </a>
      ))}
    </div>
  )
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

  const sections = useMemo(
    () => (signalsState.data ? buildSections(signalsState.data, labelByCik) : []),
    [signalsState.data, labelByCik],
  )
  const coverage = meta?.coverage?.find((c) => c.period === period)
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

      <div className="flex flex-col gap-3">
        <p className="max-w-3xl text-sm text-ink-muted">
          Every signal on this page is computed across the {meta.managers.length} tracked managers for one quarter, from
          their 13F filings. Each table explains what it counts, and ranked rows open to name the managers behind them.
          Start with a card below, or jump to any table.
        </p>
        {signalsState.data && <Notable data={signalsState.data} />}
      </div>

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
          <Suspense fallback={<LoadingState />}>{s.node}</Suspense>
        </section>
      ))}
    </div>
  )
}
