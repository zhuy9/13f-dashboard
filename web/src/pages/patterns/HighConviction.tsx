import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct } from '@/format'
import type { HighConvictionRow } from '@/types'

export function HighConviction({ rows }: { rows: HighConvictionRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No high-conviction names this quarter.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Symbol</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="text-right">Managers</TableHead>
          <TableHead className="text-right">Avg Weight</TableHead>
          <TableHead className="text-right">Max Weight</TableHead>
          <TableHead className="text-right">New</TableHead>
          <TableHead className="text-right">Added</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <StockLink symbol={r.symbol} />
            </TableCell>
            <TableCell className="max-w-xs truncate">{r.name}</TableCell>
            <TableCell className="font-tabular text-right">{r.managers}</TableCell>
            <TableCell className="font-tabular text-right">{pct(r.avgWeight)}</TableCell>
            <TableCell className="font-tabular text-right">{pct(r.maxWeight)}</TableCell>
            <TableCell className="font-tabular text-right">{r.new}</TableCell>
            <TableCell className="font-tabular text-right">{r.added}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
