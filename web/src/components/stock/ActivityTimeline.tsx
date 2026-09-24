import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'
import { filedDate } from '@/format'
import type { InsiderTrade } from '@/insiderTypes'
import type { OwnershipEvent } from '@/ownershipTypes'
import type { StockTrendPoint } from '@/types'

const day = (iso: string) => new Date(`${iso}T00:00:00Z`).getTime()
const label = (ms: number) => filedDate(new Date(ms).toISOString().slice(0, 10))

interface Point {
  at: number
  price: number
  who: string
}

// One time axis for everything that carries a date and a price. Form 4 open-market trades sit at
// the price the insider paid; the 13F line is the quarter-end price the filers' value/shares imply,
// stepped because it is only known once a quarter; a 13D/13G filing has no price, so it is a marker.
export function ActivityTimeline({ trades, events, trend }: { trades: InsiderTrade[]; events: OwnershipEvent[]; trend: StockTrendPoint[] }) {
  const points = (kind: InsiderTrade['kind']): Point[] =>
    trades.filter((t) => t.kind === kind && t.price != null).map((t) => ({ at: day(t.transactionDate), price: t.price as number, who: t.ownerName }))
  const buys = points('BUY')
  const sells = points('SELL')
  const implied: Point[] = trend
    .filter((t) => t.impliedPrice != null)
    .map((t) => ({ at: day(t.period), price: t.impliedPrice as number, who: 'Quarter-end implied (13F)' }))
  if (buys.length + sells.length + implied.length === 0) return null
  // The axis spans every dated item, or a 13D/G filed after the newest trade would fall off the chart.
  const dates = [...buys, ...sells, ...implied].map((p) => p.at).concat(events.map((e) => day(e.filedAt)))
  const domain: [number, number] = [Math.min(...dates), Math.max(...dates)]

  return (
    <section>
      <h2 className="mb-2 text-lg font-medium">Activity Timeline</h2>
      <p className="mb-2 text-sm text-ink-muted">
        Insider open-market trades at the price paid; the 13F line is the quarter-end price the filings imply; 13D/G
        filings are dated markers. Trades and filings are days old, where the 13F holdings above are a quarter old.
      </p>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-line)" />
          <XAxis dataKey="at" type="number" domain={domain} tickFormatter={label} tick={{ fontSize: 12 }} />
          <YAxis dataKey="price" type="number" domain={['auto', 'auto']} tickFormatter={(v: number) => `$${v}`} tick={{ fontSize: 12 }} width={64} />
          <Tooltip
            labelFormatter={(v) => label(Number(v))}
            formatter={(value, _name, item) => [`$${Number(value).toFixed(2)} · ${(item.payload as Point).who}`, '']}
          />
          <Legend />
          {implied.length > 0 && (
            <Line data={implied} dataKey="price" name="13F implied price" type="stepAfter" stroke="var(--color-ink-muted)" dot={{ r: 3 }} isAnimationActive={false} />
          )}
          <Scatter name="Insider buy" data={buys} fill="var(--color-call)" isAnimationActive={false} />
          <Scatter name="Insider sell" data={sells} fill="var(--color-put)" isAnimationActive={false} />
          {events.map((e) => (
            <ReferenceLine
              key={e.accession}
              x={day(e.filedAt)}
              stroke="var(--color-ink-muted)"
              strokeDasharray="4 2"
              label={{ value: `${e.form} ${e.event ?? ''}`.trim(), position: 'insideTopLeft', fontSize: 10, fill: 'var(--color-ink-muted)' }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </section>
  )
}
