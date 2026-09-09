import { lazy, type ReactNode } from 'react'
import { SharesVsWeight, WeightBasis } from '@/components/Explain'
import { pct, pp } from '@/format'
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
  rows?: object[]
  node: ReactNode
  help: ReactNode
}

// Every average needs to name the population it averages over, or the number is unreadable.
// "Avg Weight 3%" means nothing until you know whether the denominator is holders, buyers, or
// all 34 tracked managers -- and on this page the three tables genuinely differ.

export function buildSections(data: Signals, labelByCik: Map<string, string>): Section[] {
  return [
    {
      id: 'consensus-buys',
      label: 'Consensus Buys',
      node: <ConsensusBuys rows={data.consensusBuys} />,
      rows: data.consensusBuys,
      help: (
        <>
          <p>
            Stocks that at least {data.config?.consensusMinManagers ?? 3} selected managers opened or added to this quarter. <em>New Buyers</em> and{' '}
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
          <WeightBasis />
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
      rows: data.consensusExits,
      help: (
        <>
          <p>
            Stocks that at least {data.config?.consensusMinManagers ?? 3} selected managers trimmed or sold out of. <em>Avg Reduction</em> averages the
            weight change over those sellers only.
          </p>
          <p>
            <strong>Sold Out means the position left the 13F</strong>, which is not the same as the manager selling
            everything: a holding can drop below the reporting threshold, or move to a form a 13F does not cover.
          </p>
          <SharesVsWeight />
        </>
      ),
    },
    {
      id: 'high-conviction',
      label: 'High Conviction',
      node: <HighConviction rows={data.highConviction} />,
      rows: data.highConviction,
      help: (
        <>
          <p>
            Stocks where at least {data.config?.highConvictionMinManagers ?? 3} managers each hold {pct(data.config?.highConvictionMinWeight ?? 0.03)} or more of their reported equity book.{' '}
            <em>Managers</em> counts only those qualifying managers — open it to see them.
          </p>
          <p>
            <em>Avg Weight</em> and <em>Max Weight</em> are over those qualifying managers too, not over every holder,
            so both meet the qualifying weight threshold by construction.
          </p>
          <WeightBasis />
        </>
      ),
    },
    {
      id: 'biggest-new',
      label: 'Biggest New',
      node: <BiggestNew rows={data.biggestNew} />,
      rows: data.biggestNew,
      help: (
        <>
          <p>The largest brand-new positions this quarter, one row per manager and stock, ranked by weight.</p>
          <WeightBasis />
        </>
      ),
    },
    {
      id: 'biggest-adds',
      label: 'Biggest Adds',
      node: <BiggestAdds rows={data.biggestAdds} />,
      rows: data.biggestAdds,
      help: (
        <>
          <p>The largest increases in weight, one row per manager and stock.</p>
          <SharesVsWeight />
          <WeightBasis />
        </>
      ),
    },
    {
      id: 'biggest-trims',
      label: 'Biggest Trims',
      node: <BiggestTrims rows={data.biggestTrims} />,
      rows: data.biggestTrims,
      help: (
        <>
          <p>The largest decreases in weight, including positions that left the 13F entirely.</p>
          <SharesVsWeight />
        </>
      ),
    },
    {
      id: 'sector-rotation',
      label: 'Sector Rotation',
      node: <SectorRotation rows={data.sectorRotation} />,
      rows: data.sectorRotation,
      help: (
        <>
          <p>
            Averages run over managers with a comparable prior quarter — a manager that did not file last quarter is
            left out rather than counted as zero. <em>Increasing</em> and <em>Decreasing</em> count managers whose
            sector weight moved by more than {pp(data.config?.sectorMoveThreshold ?? 0.005)}.
          </p>
          <p>Sectors come from the issuer's SEC SIC code, not GICS, and an ETF is its own sector.</p>
        </>
      ),
    },
    {
      id: 'fastest-growing',
      label: 'Fastest Growing',
      node: <FastestGrowing rows={data.fastestGrowing} />,
      rows: data.fastestGrowing,
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
      rows: data.optionsExposure,
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

