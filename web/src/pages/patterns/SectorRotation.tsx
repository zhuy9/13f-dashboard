import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp, STATUS_COLORS } from '@/format'
import type { SectorRotationRow } from '@/types'

const RISING_COLOR = STATUS_COLORS.ADDED
const FALLING_COLOR = STATUS_COLORS.SOLD_OUT

export function SectorRotation({ rows }: { rows: SectorRotationRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No sector data this quarter.</p>

  return (
    <div className="flex flex-col gap-4">
      <ResponsiveContainer width="100%" height={Math.max(200, rows.length * 32)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 24 }}>
          <XAxis type="number" tickFormatter={(v: number) => pp(v)} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="sector" width={140} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => pp(Number(value))} />
          <Bar dataKey="avgChange" isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.sector} fill={r.avgChange >= 0 ? RISING_COLOR : FALLING_COLOR} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Sector</TableHead>
            <TableHead className="text-right">Avg Weight</TableHead>
            <TableHead className="text-right">Avg Prev Weight</TableHead>
            <TableHead className="text-right">Avg Change</TableHead>
            <TableHead className="text-right">Increasing</TableHead>
            <TableHead className="text-right">Decreasing</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.sector}>
              <TableCell>{r.sector}</TableCell>
              <TableCell className="font-tabular text-right">{pct(r.avgWeight)}</TableCell>
              <TableCell className="font-tabular text-right">{pct(r.avgPrevWeight)}</TableCell>
              <TableCell className="font-tabular text-right">{pp(r.avgChange)}</TableCell>
              <TableCell className="font-tabular text-right">{r.increasing}</TableCell>
              <TableCell className="font-tabular text-right">{r.decreasing}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
