import { ColorBadge } from '@/components/ColorBadge'
import { ManagerLink } from '@/components/ManagerLink'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { money, NEUTRAL_COLOR, pct, pp, STATUS_COLORS } from '@/format'
import type { ConvictionRow, ManagerRef, NetRow, NewPositionRow, SectorRow, SplitRow } from '@/quarterlyTypes'

const NUM = 'font-tabular text-right'
const CHANGE_COLORS: Record<ConvictionRow['change'], string> = {
  ENTERED: STATUS_COLORS.NEW,
  STAYED: NEUTRAL_COLOR,
  LEFT: STATUS_COLORS.SOLD_OUT,
}

export function Ticker({ symbol, name }: { symbol: string; name?: string | null }) {
  return (
    <div className="min-w-0">
      <StockLink symbol={symbol} />
      {name && <div className="max-w-[12rem] truncate text-xs text-ink-muted">{name}</div>}
    </div>
  )
}

function Managers({ list }: { list: ManagerRef[] }) {
  return (
    <span className="text-sm">
      {list.slice(0, 3).map((m, i) => (
        <span key={m.cik}>
          {i > 0 && ', '}
          <ManagerLink cik={m.cik} label={m.short} />
        </span>
      ))}
      {list.length > 3 && <span className="text-ink-muted"> +{list.length - 3}</span>}
    </span>
  )
}

export function NetTable({ rows, side }: { rows: NetRow[]; side: 'buy' | 'sell' }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead className="text-right">Buying</TableHead>
          <TableHead className="text-right">Selling</TableHead>
          <TableHead className="text-right">Net</TableHead>
          <TableHead>{side === 'buy' ? 'Bought or added' : 'Trimmed or sold'}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <div className="flex items-start gap-2">
                <Ticker symbol={r.symbol} name={r.name} />
                {r.contested && <ColorBadge color={STATUS_COLORS.TRIMMED} label="contested" />}
              </div>
            </TableCell>
            <TableCell className={NUM}>{r.buyers}</TableCell>
            <TableCell className={NUM}>{r.sellers}</TableCell>
            <TableCell className={`${NUM} font-semibold`}>{r.net > 0 ? `+${r.net}` : r.net}</TableCell>
            <TableCell>
              <Managers list={(side === 'buy' ? r.buyerManagers : r.sellerManagers) ?? []} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function SplitTable({ rows }: { rows: SplitRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead className="text-right">Buying</TableHead>
          <TableHead className="text-right">Selling</TableHead>
          <TableHead>Bought or added</TableHead>
          <TableHead>Trimmed or sold</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <Ticker symbol={r.symbol} name={r.name} />
            </TableCell>
            <TableCell className={NUM}>{r.buyers}</TableCell>
            <TableCell className={NUM}>{r.sellers}</TableCell>
            <TableCell>
              <Managers list={r.buyerManagers} />
            </TableCell>
            <TableCell>
              <Managers list={r.sellerManagers} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function NewPositionsTable({ rows }: { rows: NewPositionRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Manager</TableHead>
          <TableHead>Ticker</TableHead>
          <TableHead className="text-right">Portfolio weight</TableHead>
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
              <Ticker symbol={r.symbol} name={r.name} />
            </TableCell>
            <TableCell className={NUM}>{pct(r.weight)}</TableCell>
            <TableCell className={NUM}>{money(r.value)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function ConvictionTable({ rows }: { rows: ConvictionRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead>Change</TableHead>
          <TableHead className="text-right">Managers</TableHead>
          <TableHead className="text-right">Avg weight</TableHead>
          <TableHead className="text-right">Max weight</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.symbol}>
            <TableCell>
              <Ticker symbol={r.symbol} name={r.name} />
            </TableCell>
            <TableCell>
              <ColorBadge color={CHANGE_COLORS[r.change]} label={r.change.toLowerCase()} />
            </TableCell>
            <TableCell className={NUM}>{r.managers}</TableCell>
            <TableCell className={NUM}>{pct(r.avgWeight)}</TableCell>
            <TableCell className={NUM}>{pct(r.maxWeight)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function SectorTable({ rows }: { rows: SectorRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Sector</TableHead>
          <TableHead className="text-right">Avg weight</TableHead>
          <TableHead className="text-right">Change</TableHead>
          <TableHead className="text-right">Managers up</TableHead>
          <TableHead className="text-right">Managers down</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.sector}>
            <TableCell>{r.sector}</TableCell>
            <TableCell className={NUM}>{pct(r.avgWeight)}</TableCell>
            <TableCell className={NUM}>{pp(r.avgChange)}</TableCell>
            <TableCell className={NUM}>{r.increasing}</TableCell>
            <TableCell className={NUM}>{r.decreasing}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
