import { CartesianGrid, LabelList, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { pct } from '@/format'
import type { Copyability } from '@/types'

export function CopyabilityChart({ rows }: { rows: Copyability[] }) {
  const data = rows.filter((r) => r.turnover != null)
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ScatterChart>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-line)" />
        <XAxis
          dataKey="turnover"
          type="number"
          name="Turnover"
          tickFormatter={(v: number) => pct(v)}
          tick={{ fontSize: 12 }}
        />
        <YAxis
          dataKey="top10Weight"
          type="number"
          name="Top 10 weight"
          tickFormatter={(v: number) => pct(v)}
          tick={{ fontSize: 12 }}
          domain={[0, 1]}
        />
        <Tooltip formatter={(value) => pct(Number(value))} labelFormatter={() => ''} />
        <Scatter data={data} fill="var(--color-call)" isAnimationActive={false}>
          <LabelList dataKey="short" position="right" fontSize={10} fill="var(--color-ink-muted)" />
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  )
}
