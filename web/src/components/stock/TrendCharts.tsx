import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { pct, quarterLabel } from '@/format'
import type { StockTrendPoint } from '@/types'

export function TrendCharts({ trend }: { trend: StockTrendPoint[] }) {
  const data = trend.map((t) => ({ ...t, label: quarterLabel(t.period) }))

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div>
        <h3 className="mb-2 font-medium">Manager Count</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-line)" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="managerCount" name="Managers" fill="var(--color-call)" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div>
        <h3 className="mb-2 font-medium">Average Weight</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-line)" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={(v: number) => pct(v)} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value) => pct(Number(value))} />
            <Line
              type="monotone"
              dataKey="avgWeight"
              name="Avg Weight"
              stroke="var(--color-call)"
              strokeWidth={2}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
