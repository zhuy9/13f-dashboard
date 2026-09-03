import { ManagerLink } from '@/components/ManagerLink'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { money, pct, pp } from '@/format'
import { useSortableRows, type SortDirection } from '@/hooks/useSortableRows'
import type { BiggestChangeRow } from '@/types'

export function BiggestChangeTable({
  rows,
  emptyMessage,
  defaultDirection,
}: {
  rows: BiggestChangeRow[]
  emptyMessage: string
  defaultDirection: SortDirection
}) {
  const { sorted, SortHead } = useSortableRows(rows, 'change', defaultDirection)
  if (rows.length === 0) return <p className="text-sm text-ink-muted">{emptyMessage}</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Manager', 'short')}
          {SortHead('Symbol', 'symbol')}
          {SortHead('Name', 'name')}
          {SortHead('Weight', 'weight', 'right')}
          {SortHead('Change', 'change', 'right')}
          {SortHead('Value', 'value', 'right')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((r) => (
          <TableRow key={`${r.cik}-${r.symbol}`}>
            <TableCell>
              <ManagerLink cik={r.cik} label={r.short} />
            </TableCell>
            <TableCell>
              <StockLink symbol={r.symbol} />
            </TableCell>
            <TableCell className="max-w-xs truncate">{r.name}</TableCell>
            <TableCell className="font-tabular text-right">{pct(r.weight)}</TableCell>
            <TableCell className="font-tabular text-right">{pp(r.change)}</TableCell>
            <TableCell className="font-tabular text-right">{money(r.value)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
