import { Link } from 'react-router-dom'
import { FormBadge } from '@/components/ownership/FormBadge'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHeader, TableRow } from '@/components/ui/table'
import { filedDate } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import { changePpLabel, investorHref, pctLabel } from '@/ownership'
import type { OwnershipStake } from '@/ownershipTypes'

export function StakesTable({
  stakes,
  hideInvestor,
  hideIssuer,
}: {
  stakes: OwnershipStake[]
  hideInvestor?: boolean
  hideIssuer?: boolean
}) {
  const { sorted, SortHead } = useSortableRows(stakes, 'pct')
  if (stakes.length === 0) return <p className="text-sm text-ink-muted">No current stakes.</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {!hideInvestor && SortHead('Investor', 'investorName')}
          {!hideIssuer && SortHead('Ticker', 'symbol')}
          {SortHead('Own %', 'pct', 'right')}
          {SortHead('Form', 'form')}
          {SortHead('Change', 'changePp', 'right')}
          {SortHead('Filed', 'filedAt')}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((s) => (
          <TableRow key={`${s.investorCik}-${s.symbol}`}>
            {!hideInvestor && (
              <TableCell className="max-w-xs truncate">
                <Link to={investorHref(s)} className="text-call hover:underline">
                  {s.short ?? s.investorName}
                </Link>
              </TableCell>
            )}
            {!hideIssuer && (
              <TableCell>{s.symbol.startsWith('_') ? s.symbol : <StockLink symbol={s.symbol} />}</TableCell>
            )}
            <TableCell className="font-tabular text-right">{pctLabel(s.pct)}</TableCell>
            <TableCell>
              <FormBadge form={s.form} />
            </TableCell>
            <TableCell className="font-tabular text-right">{changePpLabel(s.changePp)}</TableCell>
            <TableCell className="font-tabular whitespace-nowrap">{filedDate(s.filedAt)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
