import { KindBadge } from '@/components/KindBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp } from '@/format'
import type { Position } from '@/types'

export function PositionsTable({ positions }: { positions: Position[] }) {
  const sorted = [...positions].sort((a, b) => b.weight - a.weight)
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Symbol</TableHead>
          <TableHead>Name</TableHead>
          <TableHead className="text-right">Weight</TableHead>
          <TableHead className="text-right">Prev</TableHead>
          <TableHead className="text-right">Weight Δ</TableHead>
          <TableHead>Shares Δ</TableHead>
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
