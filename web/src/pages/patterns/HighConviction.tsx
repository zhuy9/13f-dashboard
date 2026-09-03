import { SortableTableHead } from '@/components/SortableTableHead'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { pct } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { HighConvictionRow } from '@/types'

export function HighConviction({ rows }: { rows: HighConvictionRow[] }) {
  const { sorted, sortKey, direction, toggleSort } = useSortableRows(rows, 'managers')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No high-conviction names this quarter.</p>

  const head = (label: string, key: keyof HighConvictionRow, align: 'left' | 'right' = 'left') => (
    <SortableTableHead label={label} sortKey={key} activeKey={sortKey} direction={direction} onSort={toggleSort} align={align} />
  )

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {head('Symbol', 'symbol')}
          {head('Name', 'name')}
          {head('Managers', 'managers', 'right')}
          {head('Avg Weight', 'avgWeight', 'right')}
          {head('Max Weight', 'maxWeight', 'right')}
          {head('New', 'new', 'right')}
          {head('Added', 'added', 'right')}
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
