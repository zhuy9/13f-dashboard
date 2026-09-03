import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { pct } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { HighConvictionRow } from '@/types'

export function HighConviction({ rows }: { rows: HighConvictionRow[] }) {
  const { sorted, SortHead } = useSortableRows(rows, 'managers')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No high-conviction names this quarter.</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Symbol', 'symbol')}
          {SortHead('Name', 'name')}
          {SortHead('Managers', 'managers', 'right')}
          {SortHead('Avg Weight', 'avgWeight', 'right')}
          {SortHead('Max Weight', 'maxWeight', 'right')}
          {SortHead('New', 'new', 'right')}
          {SortHead('Added', 'added', 'right')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((r) => (
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
