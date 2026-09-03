import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pp } from '@/format'
import type { ConsensusExitRow } from '@/types'

export function ConsensusExits({ rows }: { rows: ConsensusExitRow[] }) {
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No consensus exits this quarter.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Symbol</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="text-right">Sold Out</TableHead>
          <TableHead className="text-right">Trimmed</TableHead>
          <TableHead className="text-right">Avg Reduction</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <StockLink symbol={r.symbol} />
            </TableCell>
            <TableCell className="max-w-xs truncate">{r.name}</TableCell>
            <TableCell className="font-tabular text-right">{r.soldOut}</TableCell>
            <TableCell className="font-tabular text-right">{r.trimmed}</TableCell>
            <TableCell className="font-tabular text-right">{pp(r.avgReduction)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
