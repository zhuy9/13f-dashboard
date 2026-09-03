import { SortableTableHead } from '@/components/SortableTableHead'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { FastestGrowingRow } from '@/types'

export function FastestGrowing({ rows }: { rows: FastestGrowingRow[] }) {
  const { sorted, sortKey, direction, toggleSort } = useSortableRows(rows, 'netChange')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No fast-growing names this quarter.</p>

  const head = (label: string, key: keyof FastestGrowingRow, align: 'left' | 'right' = 'left') => (
    <SortableTableHead label={label} sortKey={key} activeKey={sortKey} direction={direction} onSort={toggleSort} align={align} />
  )

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {head('Symbol', 'symbol')}
          {head('Name', 'name')}
          {head('Prev Count', 'prevCount', 'right')}
          {head('Count', 'count', 'right')}
          {head('New Managers', 'newManagers', 'right')}
          {head('Exited Managers', 'exitedManagers', 'right')}
          {head('Net Change', 'netChange', 'right')}
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
