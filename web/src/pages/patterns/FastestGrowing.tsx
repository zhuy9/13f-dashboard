import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { FastestGrowingRow } from '@/types'

export function FastestGrowing({ rows }: { rows: FastestGrowingRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No fast-growing names this quarter.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Symbol</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="text-right">Prev Count</TableHead>
          <TableHead className="text-right">Count</TableHead>
          <TableHead className="text-right">New Managers</TableHead>
          <TableHead className="text-right">Exited Managers</TableHead>
          <TableHead className="text-right">Net Change</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
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
