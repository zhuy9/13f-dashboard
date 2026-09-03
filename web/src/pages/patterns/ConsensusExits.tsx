import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { pp } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { ConsensusExitRow } from '@/types'

export function ConsensusExits({ rows }: { rows: ConsensusExitRow[] }) {
  const { sorted, SortHead } = useSortableRows(rows, 'soldOut')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No consensus exits this quarter.</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Symbol', 'symbol')}
          {SortHead('Name', 'name')}
          {SortHead('Sold Out', 'soldOut', 'right')}
          {SortHead('Trimmed', 'trimmed', 'right')}
          {SortHead('Avg Reduction', 'avgReduction', 'right')}
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
