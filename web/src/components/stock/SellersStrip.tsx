import { useState } from 'react'
import { StatTile } from '@/components/StatTile'
import { discretionarySellersSince } from '@/insider'
import type { InsiderIssuer } from '@/insiderTypes'
import type { OwnershipIssuer } from '@/ownershipTypes'
import type { StockLatest } from '@/types'

// ponytail: fixed 90-day window, the same span insider clusters use; read it from the feed
// config if the two ever need to move together.
const WINDOW_DAYS = 90

function Light({ n, unit }: { n: number | null | undefined; unit: string }) {
  if (n == null) return <span className="text-ink-muted">no data</span>
  if (n === 0) return <span className="text-ink-muted">none</span>
  return <span className="text-put">{n} {unit}{n === 1 ? '' : 's'}</span>
}

// Three sources, three lights, never summed: a 13F trim is a quarter old, a 13D/G cut days old,
// and a planned 10b5-1 sale is not a seller's opinion, so only discretionary sales count.
export function SellersStrip({ latest, issuer, insider }: { latest: StockLatest | null; issuer: OwnershipIssuer | null; insider: InsiderIssuer | null }) {
  // Fixed at mount: the window must not creep while the page sits open.
  const [since] = useState(() => new Date(Date.now() - WINDOW_DAYS * 86_400_000).toISOString().slice(0, 10))
  const cuts = issuer?.events.filter((e) => e.filedAt >= since && (e.event === 'DECREASED' || e.event === 'EXITED')).length
  const sellers = insider && discretionarySellersSince(insider.trades, since)
  const managers = latest && latest.trimmedCount + latest.soldOutCount

  return (
    <section>
      <h2 className="mb-2 text-lg font-medium">Sellers Appearing</h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <StatTile
          label="13F managers cutting, selected quarter"
          value={<Light n={managers} unit="manager" />}
          detail={latest ? `${latest.trimmedCount} trimmed · ${latest.soldOutCount} sold out` : undefined}
        />
        <StatTile label={`13D/G stake cuts, last ${WINDOW_DAYS} days`} value={<Light n={cuts} unit="filing" />} detail="Decreased or exited" />
        <StatTile
          label={`Discretionary insider sellers, last ${WINDOW_DAYS} days`}
          value={<Light n={sellers} unit="insider" />}
          detail="Planned 10b5-1 sales excluded"
        />
      </div>
    </section>
  )
}
