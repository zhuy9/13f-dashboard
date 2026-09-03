import { SortableTableHead } from '@/components/SortableTableHead'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { pp } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { ConsensusExitRow } from '@/types'

export function ConsensusExits({ rows }: { rows: ConsensusExitRow[] }) {
  const { sorted, sortKey, direction, toggleSort } = useSortableRows(rows, 'soldOut')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No consensus exits this quarter.</p>

  const head = (label: string, key: keyof ConsensusExitRow, align: 'left' | 'right' = 'left') => (
    <SortableTableHead label={label} sortKey={key} activeKey={sortKey} direction={direction} onSort={toggleSort} align={align} />
  )

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {head('Symbol', 'symbol')}
          {head('Name', 'name')}
          {head('Sold Out', 'soldOut', 'right')}
          {head('Trimmed', 'trimmed', 'right')}
          {head('Avg Reduction', 'avgReduction', 'right')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <StockLink symbol={r.symbol} />
            </TableCell>
            <TableCell className="max-w-xs truncate">{r.name}</TableCell>
            <TableCell className="font-tabular text-right">{r.soldOut}</TableCell>
            <TableCell className="font-tabular text-right">{r.trimmed}</TableCell>
            <TableCell className="font-tabular text-right">{pp(r.avgReduction)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
