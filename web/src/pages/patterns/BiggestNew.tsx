import { ManagerLink } from '@/components/ManagerLink'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { money, pct } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { BiggestNewRow } from '@/types'

export function BiggestNew({ rows }: { rows: BiggestNewRow[] }) {
  const { sorted, SortHead } = useSortableRows(rows, 'weight')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No new positions this quarter.</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Manager', 'short')}
          {SortHead('Symbol', 'symbol')}
          {SortHead('Name', 'name')}
          {SortHead('Weight', 'weight', 'right')}
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
            <TableCell className="font-tabular text-right">{money(r.value)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
