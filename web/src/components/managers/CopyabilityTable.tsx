import { ManagerLink } from '@/components/ManagerLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { pct } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { Copyability } from '@/types'

export function CopyabilityTable({ rows }: { rows: Copyability[] }) {
  const { sorted, SortHead } = useSortableRows(rows, 'turnover', 'asc')
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Manager', 'short')}
          {SortHead('Turnover / qtr', 'turnover', 'right')}
          {SortHead('Top 10 weight', 'top10Weight', 'right')}
          {SortHead('New still held after 4 qtrs', 'newHeldAfter4', 'right')}
          {SortHead('Quarters', 'quarters', 'right')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((r) => (
          <TableRow key={r.cik}>
            <TableCell><ManagerLink cik={r.cik} label={r.short} /></TableCell>
            <TableCell className="font-tabular text-right">{r.turnover != null ? pct(r.turnover) : '—'}</TableCell>
            <TableCell className="font-tabular text-right">{pct(r.top10Weight)}</TableCell>
            <TableCell className="font-tabular text-right">{r.newHeldAfter4 != null ? pct(r.newHeldAfter4) : '—'}</TableCell>
            <TableCell className="font-tabular text-right">{r.quarters}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
