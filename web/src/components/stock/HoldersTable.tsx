import { Link } from 'react-router-dom'
import { Explain, SharesVsWeight, SplitBasis, WeightBasis } from '@/components/Explain'
import { StatusBadge } from '@/components/StatusBadge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp, signedPct } from '@/format'
import type { Holder } from '@/types'

export function HoldersTable({ holders }: { holders: Holder[] }) {
  const sorted = [...holders].sort((a, b) => b.weight - a.weight)
  return (
    <>
      <Explain>
        <SharesVsWeight />
        <WeightBasis />
        <SplitBasis />
        <p>
          The weight shown is each manager's own weight in this stock — not a share of the company, and not a
          comparison of dollar amounts between managers. Managers who sold out are listed below rather than shown
          here at a weight of zero.
        </p>
      </Explain>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Manager</TableHead>
            <TableHead className="text-right">Weight</TableHead>
            <TableHead className="text-right">Weight Δ</TableHead>
            <TableHead>Shares Δ</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((h) => (
            <TableRow key={h.cik}>
              <TableCell>
                <Link to={`/manager/${h.cik}`} className="text-call hover:underline">
                  {h.short}
                </Link>
              </TableCell>
              <TableCell className="font-tabular text-right">{pct(h.weight)}</TableCell>
              <TableCell className="font-tabular text-right">{h.change != null ? pp(h.change) : '—'}</TableCell>
              <TableCell className="whitespace-nowrap">
                <StatusBadge status={h.status} />{' '}
                {h.shareChange != null && (
                  <span className="font-tabular text-ink-muted">{signedPct(h.shareChange)}</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  )
}
