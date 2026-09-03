import { ManagerLink } from '@/components/ManagerLink'
import { SortableTableHead } from '@/components/SortableTableHead'
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
  const { sorted, sortKey, direction, toggleSort } = useSortableRows(rows, 'change', defaultDirection)
  if (rows.length === 0) return <p className="text-sm text-ink-muted">{emptyMessage}</p>

  const head = (label: string, key: keyof BiggestChangeRow, align: 'left' | 'right' = 'left') => (
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
          {head('Change', 'change', 'right')}
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
            <TableCell className="font-tabular text-right">{pp(r.change)}</TableCell>
            <TableCell className="font-tabular text-right">{money(r.value)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
