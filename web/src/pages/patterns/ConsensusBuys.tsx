import { InfoPopover, ManagerList } from '@/components/Explain'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { ConsensusBuyRow } from '@/types'

export function ConsensusBuys({ rows }: { rows: ConsensusBuyRow[] }) {
  const { sorted, SortHead } = useSortableRows(rows, 'score')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No consensus buys this quarter.</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Symbol', 'symbol')}
          {SortHead('Name', 'name')}
          {SortHead('New Buyers', 'newBuyers', 'right')}
          {SortHead('Added', 'added', 'right')}
          {SortHead('Avg Weight', 'avgWeight', 'right')}
          {SortHead('Avg Weight Increase', 'avgWeightIncrease', 'right')}
          {SortHead('Score', 'score', 'right')}
          <TableHead>Buyers</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <StockLink symbol={r.symbol} />
            </TableCell>
            <TableCell className="max-w-xs truncate">{r.name}</TableCell>
            <TableCell className="font-tabular text-right">{r.newBuyers}</TableCell>
            <TableCell className="font-tabular text-right">{r.added}</TableCell>
            <TableCell className="font-tabular text-right">{pct(r.avgWeight)}</TableCell>
            <TableCell className="font-tabular text-right">{pp(r.avgWeightIncrease)}</TableCell>
            <TableCell className="font-tabular text-right">
              {r.raw != null && r.scorePeak ? (
                <InfoPopover label={r.score} heading={`${r.symbol} conviction score`}>
                  <p>
                    {r.raw.toFixed(1)} raw ÷ {r.scorePeak.toFixed(1)} highest raw score this quarter × 100 ={' '}
                    {r.score}.
                  </p>
                  <p className="mt-1">
                    The scale is relative to this quarter only, so 100 means top of the quarter rather than a rating,
                    and scores are not comparable between quarters.
                  </p>
                </InfoPopover>
              ) : (
                r.score
              )}
            </TableCell>
            <TableCell>
              <ManagerList names={r.managers} heading={`${r.symbol} — opened or added`} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
