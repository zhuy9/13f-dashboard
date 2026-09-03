import { ManagerLink } from '@/components/ManagerLink'
import { SortableTableHead } from '@/components/SortableTableHead'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { money, pct } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { BiggestNewRow } from '@/types'

export function BiggestNew({ rows }: { rows: BiggestNewRow[] }) {
  const { sorted, sortKey, direction, toggleSort } = useSortableRows(rows, 'weight')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No new positions this quarter.</p>

  const head = (label: string, key: keyof BiggestNewRow, align: 'left' | 'right' = 'left') => (
    <SortableTableHead label={label} sortKey={key} activeKey={sortKey} direction={direction} onSort={toggleSort} align={align} />
  )

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {head('Manager', 'short')}
          {head('Symbol', 'symbol')}
          {head('Name', 'name')}
          {head('Weight', 'weight', 'right')}
          {head('Value', 'value', 'right')}
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
