import type { ReactNode } from 'react'
import { ColorBadge } from '@/components/ColorBadge'
import { ManagerLink } from '@/components/ManagerLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { CALL_COLOR, filedDate, money, NEUTRAL_COLOR, STATUS_COLORS } from '@/format'
import { windowLabel } from '@/quarterly'
import type { CrossRow, DateRange, InsiderBuyRow, InsiderSaleRow, IssueWindow, StakeRow } from '@/quarterlyTypes'
import { Ticker } from './HoldingsTables'

const NUM = 'font-tabular text-right'
const WINDOW_TITLES: Record<IssueWindow, string> = { quarter: 'During the quarter', since: 'Since it ended' }
const SIGNAL_COLORS = { '13F': STATUS_COLORS.NEW, '13D': CALL_COLOR, INSIDER: NEUTRAL_COLOR }

interface ByWindowProps<R> {
  rows: R[]
  noData: IssueWindow[]
  totals: Partial<Record<IssueWindow, number>>
  windows: Record<IssueWindow, DateRange>
  render: (rows: R[]) => ReactNode
}

// Both windows, each under its own dates. A window the log does not cover says so, never "0".
export function ByWindow<R extends { window: IssueWindow }>({ rows, noData, totals, windows, render }: ByWindowProps<R>) {
  return (
    <div className="flex flex-col gap-4">
      {(['quarter', 'since'] as const).map((w) => {
        const inWindow = rows.filter((r) => r.window === w)
        const shown = inWindow.length
        const total = totals[w] ?? shown
        return (
          <div key={w} className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold">
              {WINDOW_TITLES[w]} <span className="font-normal text-ink-muted">· {windowLabel(windows[w])}</span>
            </h3>
            {noData.includes(w) ? (
              <p className="text-sm text-ink-muted">No data for this window: our filing log starts later.</p>
            ) : shown === 0 ? (
              <p className="text-sm text-ink-muted">None filed.</p>
            ) : (
              <>
                {render(inWindow)}
                {total > shown && <p className="text-xs text-ink-muted">Top {shown} of {total.toLocaleString()}.</p>}
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}

function Filer({ isRoster, cik, short, name }: { isRoster: boolean; cik: string; short: string | null; name: string }) {
  return isRoster && short ? <ManagerLink cik={cik} label={short} /> : <span className="text-sm">{name}</span>
}

export function StakesTable({ rows }: { rows: StakeRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Filed</TableHead>
          <TableHead>Ticker</TableHead>
          <TableHead>Filer</TableHead>
          <TableHead>Filing</TableHead>
          <TableHead className="text-right">Stake</TableHead>
          <TableHead className="text-right">13F holders</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={`${r.url}-${r.investorCik}`}>
            <TableCell className="whitespace-nowrap">
              <a href={r.url} target="_blank" rel="noreferrer" className="text-call hover:underline">
                {filedDate(r.filedAt)}
              </a>
            </TableCell>
            <TableCell>
              <Ticker symbol={r.symbol} name={r.issuerName} />
            </TableCell>
            <TableCell className="max-w-[14rem] truncate">
              <Filer isRoster={r.isRoster} cik={r.investorCik} short={r.short} name={r.investorName} />
            </TableCell>
            <TableCell className="whitespace-nowrap">
              {r.form} {r.event.toLowerCase().replaceAll('_', ' ')}
            </TableCell>
            <TableCell className={NUM}>{r.pct == null ? '—' : `${r.pct.toFixed(1)}%`}</TableCell>
            <TableCell className={NUM}>{r.holders13f}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function InsiderBuysTable({ rows }: { rows: InsiderBuyRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead className="text-right">Buyers</TableHead>
          <TableHead className="text-right">Bought</TableHead>
          <TableHead className="text-right">13F holders</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <div className="flex items-start gap-2">
                <Ticker symbol={r.symbol} name={r.issuerName} />
                {r.isCluster && <ColorBadge color={STATUS_COLORS.NEW} label="cluster" />}
              </div>
            </TableCell>
            <TableCell className={NUM}>{r.buyers}</TableCell>
            <TableCell className={NUM}>{money(r.value)}</TableCell>
            <TableCell className={NUM}>{r.holders13f}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function InsiderSalesTable({ rows }: { rows: InsiderSaleRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead className="text-right">Discretionary sellers</TableHead>
          <TableHead className="text-right">Discretionary</TableHead>
          <TableHead className="text-right">Planned sellers</TableHead>
          <TableHead className="text-right">Planned</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <Ticker symbol={r.symbol} name={r.issuerName} />
            </TableCell>
            <TableCell className={NUM}>{r.discretionarySellers}</TableCell>
            <TableCell className={NUM}>{money(r.discretionaryValue)}</TableCell>
            <TableCell className={NUM}>{r.plannedSellers}</TableCell>
            <TableCell className={NUM}>{money(r.plannedValue)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function CrossTable({ rows }: { rows: CrossRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead>Seen in</TableHead>
          <TableHead className="text-right">Net 13F buyers</TableHead>
          <TableHead>13D/13G filer</TableHead>
          <TableHead className="text-right">Insider buyers</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <Ticker symbol={r.symbol} name={r.name} />
            </TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {r.signals.map((s) => (
                  <ColorBadge key={s} color={SIGNAL_COLORS[s]} label={s === 'INSIDER' ? 'insiders' : s} />
                ))}
              </div>
            </TableCell>
            <TableCell className={NUM}>{r.net == null ? '—' : `+${r.net}`}</TableCell>
            <TableCell className="max-w-[14rem] truncate">
              {r.investor && r.investorCik ? (
                <Filer isRoster={Boolean(r.isRoster)} cik={r.investorCik} short={r.investor} name={r.investor} />
              ) : (
                '—'
              )}
            </TableCell>
            <TableCell className={NUM}>{r.insiderBuyers || '—'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
