import { KindBadge } from '@/components/KindBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { Position } from '@/types'

export function PositionsTable({ positions }: { positions: Position[] }) {
  const { sorted, SortHead } = useSortableRows(positions, 'weight')
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Symbol', 'symbol')}
          {SortHead('Name', 'name')}
          {SortHead('Weight', 'weight', 'right')}
          {SortHead('Prev', 'prevWeight', 'right')}
          {SortHead('Weight Δ', 'change', 'right')}
          {SortHead('Shares Δ', 'status')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((p) => (
          <TableRow key={p.symbol}>
            <TableCell className="whitespace-nowrap">
              <StockLink symbol={p.symbol} className="font-tabular font-medium text-call hover:underline" />{' '}
              <KindBadge kind={p.kind} />
            </TableCell>
            <TableCell className="max-w-xs truncate">{p.name}</TableCell>
            <TableCell className="font-tabular text-right">{pct(p.weight)}</TableCell>
            <TableCell className="font-tabular text-right">{p.prevWeight != null ? pct(p.prevWeight) : '—'}</TableCell>
            <TableCell className="font-tabular text-right">{p.change != null ? pp(p.change) : '—'}</TableCell>
            <TableCell>
              <StatusBadge status={p.status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
