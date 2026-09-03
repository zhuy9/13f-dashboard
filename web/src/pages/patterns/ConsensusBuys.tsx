import { SortableTableHead } from '@/components/SortableTableHead'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { ConsensusBuyRow } from '@/types'

export function ConsensusBuys({ rows }: { rows: ConsensusBuyRow[] }) {
  const { sorted, sortKey, direction, toggleSort } = useSortableRows(rows, 'score')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No consensus buys this quarter.</p>

  const head = (label: string, key: keyof ConsensusBuyRow, align: 'left' | 'right' = 'left') => (
    <SortableTableHead label={label} sortKey={key} activeKey={sortKey} direction={direction} onSort={toggleSort} align={align} />
  )

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {head('Symbol', 'symbol')}
          {head('Name', 'name')}
          {head('New Buyers', 'newBuyers', 'right')}
          {head('Added', 'added', 'right')}
          {head('Avg Weight', 'avgWeight', 'right')}
          {head('Avg Weight Increase', 'avgWeightIncrease', 'right')}
          {head('Score', 'score', 'right')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <StockLink symbol={r.symbol} />
            </TableCell>
            <TableCell className="max-w-xs truncate">{r.name}</TableCell>
            <TableCell className="font-tabular text-right">{r.newBuyers}</TableCell>
            <TableCell className="font-tabular text-right">{r.added}</TableCell>
            <TableCell className="font-tabular text-right">{pct(r.avgWeight)}</TableCell>
            <TableCell className="font-tabular text-right">{pp(r.avgWeightIncrease)}</TableCell>
            <TableCell className="font-tabular text-right">{r.score}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
