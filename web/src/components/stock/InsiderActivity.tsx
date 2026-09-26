import { Link } from 'react-router-dom'
import { ColorBadge } from '@/components/ColorBadge'
import { TradesTable } from '@/components/insider/TradesTable'
import { StatTile } from '@/components/StatTile'
import { getInsiderClusters } from '@/data'
import type { InsiderIssuer } from '@/insiderTypes'
import { money, STATUS_COLORS } from '@/format'
import { useAsyncData } from '@/hooks/useAsyncData'

// The issuer doc is read by the stock page outside its loading gate: a missing, slow, or failed
// insider read must never hold up the 13F sections above it -- useAsyncData already catches into
// an error string rather than throwing, so a rejection just leaves this section absent.
export function InsiderActivity({ symbol, issuer }: { symbol: string; issuer: InsiderIssuer | null }) {
  const clustersState = useAsyncData(getInsiderClusters, [])

  if (!issuer) return null
  const { summary } = issuer
  const hasCluster = clustersState.data?.symbols.includes(symbol) ?? false

  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-center gap-2 text-lg font-medium">
        Insider Activity (Form 4)
        {hasCluster && <ColorBadge color={STATUS_COLORS.NEW} label="Cluster buying" />}
      </h2>
      <p className="text-sm text-ink-muted">
        Each row is the insider's own transaction date, independently of the selected 13F quarter.{' '}
        <Link to={`/insiders?q=${encodeURIComponent(symbol)}`} className="text-call hover:underline">
          View all on the Insiders page →
        </Link>
      </p>

      {summary && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Open-market buyers" value={summary.buyers} />
          <StatTile label="Open-market sellers" value={summary.sellers} />
          <StatTile label="Bought" value={money(summary.boughtValue)} />
          <StatTile label="Sold" value={money(summary.soldValue)} />
        </div>
      )}

      <TradesTable trades={issuer.trades} hideIssuer />
    </section>
  )
}
