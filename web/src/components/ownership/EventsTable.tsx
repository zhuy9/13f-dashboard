import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { EventBadge } from '@/components/ownership/EventBadge'
import { FormBadge } from '@/components/ownership/FormBadge'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { filedDate } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import { changePpLabel, investorHref, pctLabel } from '@/ownership'
import type { OwnershipEvent } from '@/ownershipTypes'

export function EventsTable({
  events,
  hideInvestor,
  hideIssuer,
}: {
  events: OwnershipEvent[]
  hideInvestor?: boolean
  hideIssuer?: boolean
}) {
  const { sorted, SortHead } = useSortableRows(events, 'filedAt')
  if (events.length === 0) return <p className="text-sm text-ink-muted">No filings.</p>

  const columnCount = 6 + Number(!hideInvestor) + Number(!hideIssuer)

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {SortHead('Filed', 'filedAt')}
          {!hideInvestor && SortHead('Investor', 'investorName')}
          {!hideIssuer && SortHead('Ticker', 'symbol')}
          {SortHead('Form', 'form')}
          {SortHead('Event', 'event')}
          {SortHead('Own %', 'pct', 'right')}
          {SortHead('Change', 'changePp', 'right')}
          <TableHead>SEC</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((e) => (
          <Fragment key={e.accession}>
            <TableRow className={e.priority === 'HIGH' ? 'border-l-2 border-l-call' : undefined}>
              <TableCell className="font-tabular whitespace-nowrap">{filedDate(e.filedAt)}</TableCell>
              {!hideInvestor && (
                <TableCell className="max-w-xs truncate">
                  <Link to={investorHref(e)} className="text-call hover:underline">
                    {e.short ?? e.investorName}
                  </Link>
                </TableCell>
              )}
              {!hideIssuer && (
                <TableCell>{e.symbol.startsWith('_') ? e.symbol : <StockLink symbol={e.symbol} />}</TableCell>
              )}
              <TableCell>
                <FormBadge form={e.form} />
              </TableCell>
              <TableCell>
                <EventBadge event={e.event} form={e.form} />
              </TableCell>
              <TableCell className="font-tabular text-right">{pctLabel(e.pct)}</TableCell>
              <TableCell className="font-tabular text-right">{changePpLabel(e.changePp)}</TableCell>
              <TableCell>
                <a href={e.url} target="_blank" rel="noopener noreferrer" className="text-call hover:underline">
                  SEC
                </a>
              </TableCell>
            </TableRow>
            {e.purpose && (
              <TableRow>
                <TableCell colSpan={columnCount} className="whitespace-normal">
                  <details>
                    <summary className="cursor-pointer text-xs text-ink-muted">Purpose</summary>
                    <p className="mt-1 text-sm">{e.purpose}</p>
                  </details>
                </TableCell>
              </TableRow>
            )}
          </Fragment>
        ))}
      </TableBody>
    </Table>
  )
}
