import { CsvExport } from '@/components/CsvExport'
import { StockLink } from '@/components/StockLink'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { money } from '@/format'
import { useSortableRows } from '@/hooks/useSortableRows'
import type { InsiderCluster } from '@/insiderTypes'

export function ClusterTable({ clusters }: { clusters: InsiderCluster[] }) {
  const { sorted, SortHead } = useSortableRows(clusters, 'buyerCount')
  if (clusters.length === 0) return <p className="text-sm text-ink-muted">No clustered buying in the current window.</p>

  return (
    <>
      <CsvExport rows={sorted} name="insider-clusters" />
      <Table>
        <TableHeader>
          <TableRow>
            {SortHead('Ticker', 'symbol')}
            {SortHead('Issuer', 'issuerName')}
            {SortHead('Distinct buyers', 'buyerCount', 'right')}
            {SortHead('Window (days)', 'windowDays', 'right')}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((c) => (
            <TableRow key={c.symbol}>
              <TableCell>
                <StockLink symbol={c.symbol} />
              </TableCell>
              <TableCell className="max-w-xs truncate">{c.issuerName}</TableCell>
              <TableCell className="font-tabular text-right">{c.buyerCount}</TableCell>
              <TableCell className="font-tabular text-right">{c.windowDays}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  )
}

export function VsThirteenFTable({ rows }: { rows: { symbol: string; issuerName: string; buyers: number; boughtValue: number; holders13f: number; hasCluster: boolean }[] }) {
  const { sorted, SortHead } = useSortableRows(rows, 'holders13f')
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No open-market buying on a tracked 13F name right now.</p>

  return (
    <>
      <CsvExport rows={sorted} name="insider-vs-13f" />
      <Table>
        <TableHeader>
          <TableRow>
            {SortHead('Ticker', 'symbol')}
            {SortHead('Issuer', 'issuerName')}
            {SortHead('13F Holders', 'holders13f', 'right')}
            {SortHead('Buyers', 'buyers', 'right')}
            {SortHead('Bought', 'boughtValue', 'right')}
            <TableHead>Cluster</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((r) => (
            <TableRow key={r.symbol}>
              <TableCell>
                <StockLink symbol={r.symbol} />
              </TableCell>
              <TableCell className="max-w-xs truncate">{r.issuerName}</TableCell>
              <TableCell className="font-tabular text-right">{r.holders13f}</TableCell>
              <TableCell className="font-tabular text-right">{r.buyers}</TableCell>
              <TableCell className="font-tabular text-right">{money(r.boughtValue)}</TableCell>
              <TableCell>{r.hasCluster ? 'Yes' : '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  )
}
