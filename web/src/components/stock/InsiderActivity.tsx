import { Link } from 'react-router-dom'
import { ColorBadge } from '@/components/ColorBadge'
import { TradesTable } from '@/components/insider/TradesTable'
import { StatTile } from '@/components/StatTile'
import { getInsiderFeed, getInsiderIssuer } from '@/data'
import { money } from '@/format'
import { useAsyncData } from '@/hooks/useAsyncData'

// Its own fetches, not lifted into the stock page's shared loading gate: a missing, slow, or
// failed insider read must never hold up the 13F sections above it -- useAsyncData already
// catches into an error string rather than throwing, so a rejection here just leaves this
// section absent.
export function InsiderActivity({ symbol }: { symbol: string }) {
  const issuerState = useAsyncData(() => getInsiderIssuer(symbol), [symbol])
  const feedState = useAsyncData(() => getInsiderFeed(), [])

  if (!issuerState.data) return null
  const issuer = issuerState.data
  const { summary } = issuer
  const hasCluster = feedState.data?.clusters.some((c) => c.symbol === symbol) ?? false

  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-center gap-2 text-lg font-medium">
        Insider Activity (Form 4)
        {hasCluster && <ColorBadge color="#1a7f37" label="Cluster buying" />}
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
