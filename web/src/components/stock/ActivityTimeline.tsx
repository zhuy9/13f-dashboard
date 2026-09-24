import {
  CartesianGrid,
  ComposedChart,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { filedDate } from "@/format";
import type { InsiderTrade } from "@/insiderTypes";
import type { OwnershipEvent } from "@/ownershipTypes";

const day = (iso: string) => new Date(`${iso}T00:00:00Z`).getTime();
const label = (ms: number) =>
  filedDate(new Date(ms).toISOString().slice(0, 10));

// One time axis for the two sources that carry their own dates. Form 4 open-market trades sit at
// the price the insider paid; a 13D/13G filing has no price, so it is a dated marker.
export function ActivityTimeline({
  trades,
  events,
}: {
  trades: InsiderTrade[];
  events: OwnershipEvent[];
}) {
  const points = (kind: InsiderTrade["kind"]) =>
    trades
      .filter((t) => t.kind === kind && t.price != null)
      .map((t) => ({
        at: day(t.transactionDate),
        price: t.price,
        who: t.ownerName,
      }));
  const buys = points("BUY");
  const sells = points("SELL");
  if (buys.length + sells.length === 0) return null;

  return (
    <section>
      <h2 className="mb-2 text-lg font-medium">Activity Timeline</h2>
      <p className="mb-2 text-sm text-ink-muted">
        Insider open-market trades at the price paid; 13D/G filings as dated
        markers. Both are days old, where the 13F holdings above are a quarter
        old.
      </p>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-line)" />
          <XAxis
            dataKey="at"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={label}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            dataKey="price"
            type="number"
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => `$${v}`}
            tick={{ fontSize: 12 }}
            width={64}
          />
          <Tooltip
            labelFormatter={(v) => label(Number(v))}
            formatter={(value, _name, item) => [
              `$${Number(value).toFixed(2)} · ${String((item.payload as { who: string }).who)}`,
              "",
            ]}
          />
          <Legend />
          <Scatter
            name="Insider buy"
            data={buys}
            fill="var(--color-call)"
            isAnimationActive={false}
          />
          <Scatter
            name="Insider sell"
            data={sells}
            fill="var(--color-put)"
            isAnimationActive={false}
          />
          {events.map((e) => (
            <ReferenceLine
              key={e.accession}
              x={day(e.filedAt)}
              stroke="var(--color-ink-muted)"
              strokeDasharray="4 2"
              label={{
                value: `${e.form} ${e.event ?? ""}`.trim(),
                position: "top",
                fontSize: 10,
                fill: "var(--color-ink-muted)",
              }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </section>
  );
}
