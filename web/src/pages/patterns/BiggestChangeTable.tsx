import { ManagerLink } from '@/components/ManagerLink'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { money, pct, pp } from '@/format'
import type { BiggestChangeRow } from '@/types'

export function BiggestChangeTable({ rows, emptyMessage }: { rows: BiggestChangeRow[]; emptyMessage: string }) {
  if (rows.length === 0) return <p className="text-sm text-ink-muted">{emptyMessage}</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Manager</TableHead>
          <TableHead>Symbol</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="text-right">Weight</TableHead>
          <TableHead className="text-right">Change</TableHead>
          <TableHead className="text-right">Value</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
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
