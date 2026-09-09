import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { CsvExport } from '@/components/CsvExport'
import { KindBadge } from '@/components/insider/KindBadge'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { filedDate, money } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import { personHref, roleLabel, saleBasisLabel, tradeKeys } from '@/insider'
import type { InsiderTrade } from '@/insiderTypes'

export function TradesTable({ trades, hideOwner, hideIssuer }: { trades: InsiderTrade[]; hideOwner?: boolean; hideIssuer?: boolean }) {
  const { sorted, SortHead } = useSortableRows(trades, 'filedAt')
  if (trades.length === 0) return <p className="text-sm text-ink-muted">No trades.</p>

  const columnCount = 7 + Number(!hideOwner) + Number(!hideIssuer)
  const keys = tradeKeys(sorted)

  return (
    <>
      <CsvExport rows={sorted} name="insider-trades" />
      <Table>
        <TableHeader>
          <TableRow>
            {SortHead('Filed', 'filedAt')}
            {!hideOwner && SortHead('Insider', 'ownerName')}
            {!hideIssuer && SortHead('Ticker', 'symbol')}
            <TableHead>Role</TableHead>
            <TableHead>Type</TableHead>
            {SortHead('Shares', 'shares', 'right')}
            {SortHead('Value', 'value', 'right')}
            <TableHead>SEC</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((t, i) => {
            const basis = saleBasisLabel(t)
            return (
              <Fragment key={keys[i]}>
                <TableRow className={t.priority === 'HIGH' ? 'border-l-2 border-l-call' : undefined}>
                  <TableCell className="font-tabular whitespace-nowrap">{filedDate(t.filedAt)}</TableCell>
                  {!hideOwner && (
                    <TableCell className="max-w-xs truncate">
                      <Link to={personHref(t.ownerCik)} className="text-call hover:underline">
                        {t.ownerName}
                      </Link>
                    </TableCell>
                  )}
                  {!hideIssuer && (
                    <TableCell>{t.symbol.startsWith('_') ? t.symbol : <StockLink symbol={t.symbol} />}</TableCell>
                  )}
                  <TableCell>
                    <Badge variant="outline">{roleLabel(t.role)}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <KindBadge kind={t.kind} />
                      {basis && <span className="text-xs text-ink-muted">{basis}</span>}
                    </div>
                  </TableCell>
                  <TableCell className="font-tabular text-right">{t.shares?.toLocaleString() ?? '—'}</TableCell>
                  <TableCell className="font-tabular text-right">{t.value === null ? '—' : money(t.value)}</TableCell>
                  <TableCell>
                    <a href={t.url} target="_blank" rel="noopener noreferrer" className="text-call hover:underline">
                      SEC
                    </a>
                  </TableCell>
                </TableRow>
                {t.footnotes && (
                  <TableRow>
                    <TableCell colSpan={columnCount} className="whitespace-normal">
                      <details>
                        <summary className="cursor-pointer text-xs text-ink-muted">Footnote</summary>
                        <p className="mt-1 text-sm">{t.footnotes}</p>
                      </details>
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            )
          })}
        </TableBody>
      </Table>
    </>
  )
}
