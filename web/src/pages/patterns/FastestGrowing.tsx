import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { FastestGrowingRow } from '@/types'

export function FastestGrowing({ rows }: { rows: FastestGrowingRow[] }) {
  const { sorted, SortHead } = useSortableRows(rows, 'netChange')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No fast-growing names this quarter.</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Symbol', 'symbol')}
          {SortHead('Name', 'name')}
          {SortHead('Prev Count', 'prevCount', 'right')}
          {SortHead('Count', 'count', 'right')}
          {SortHead('New Managers', 'newManagers', 'right')}
          {SortHead('Exited Managers', 'exitedManagers', 'right')}
          {SortHead('Net Change', 'netChange', 'right')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <StockLink symbol={r.symbol} />
            </TableCell>
            <TableCell className="max-w-xs truncate">{r.name}</TableCell>
            <TableCell className="font-tabular text-right">{r.prevCount}</TableCell>
            <TableCell className="font-tabular text-right">{r.count}</TableCell>
            <TableCell className="font-tabular text-right">{r.newManagers}</TableCell>
            <TableCell className="font-tabular text-right">{r.exitedManagers}</TableCell>
            <TableCell className="font-tabular text-right">{r.netChange}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
