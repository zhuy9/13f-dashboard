import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp } from '@/format'
import type { ConsensusBuyRow } from '@/types'

export function ConsensusBuys({ rows }: { rows: ConsensusBuyRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No consensus buys this quarter.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Symbol</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="text-right">New Buyers</TableHead>
          <TableHead className="text-right">Added</TableHead>
          <TableHead className="text-right">Avg Weight</TableHead>
          <TableHead className="text-right">Avg Weight Increase</TableHead>
          <TableHead className="text-right">Score</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
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
