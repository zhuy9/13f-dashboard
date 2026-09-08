import { ColorBadge } from '@/components/ColorBadge'
import { KindBadge } from '@/components/KindBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp, signedPct } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { Position } from '@/types'

export function PositionsTable({ positions }: { positions: Position[] }) {
  const { sorted, SortHead } = useSortableRows(positions, 'weight')
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Symbol', 'symbol')}
          {SortHead('Name', 'name')}
          {SortHead('Weight', 'weight', 'right')}
          {SortHead('Prev', 'prevWeight', 'right')}
          {SortHead('Weight Δ', 'change', 'right')}
          {SortHead('Shares Δ', 'status')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((p) => (
          <TableRow key={p.symbol}>
            <TableCell className="whitespace-nowrap">
              <StockLink symbol={p.symbol} className="font-tabular font-medium text-call hover:underline" />{' '}
              <KindBadge kind={p.kind} />
              {p.disclosedByAmendment && (
                <span title="First disclosed in an amended filing (13F-HR/A), usually because the position was confidential. That is when it was reported, not when it was bought.">
                  {' '}
                  <ColorBadge color="#6639ba" label="AMENDED" />
                </span>
              )}
            </TableCell>
            <TableCell className="max-w-xs truncate">{p.name}</TableCell>
            <TableCell className="font-tabular text-right">{pct(p.weight)}</TableCell>
            <TableCell className="font-tabular text-right">{p.prevWeight != null ? pct(p.prevWeight) : '—'}</TableCell>
            <TableCell className="font-tabular text-right">{p.change != null ? pp(p.change) : '—'}</TableCell>
            <TableCell className="whitespace-nowrap">
              <StatusBadge status={p.status} />{' '}
              {p.shareChange != null && <span className="font-tabular text-ink-muted">{signedPct(p.shareChange)}</span>}{' '}
              {p.splitUnverified === true && (
                <span title="Share count moved like a stock split, but no corporate action on file confirms one. The comparison to last quarter may not be like-for-like.">
                  <ColorBadge color="#9a6700" label="UNADJUSTED?" />
                </span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
