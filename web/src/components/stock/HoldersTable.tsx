import { Link } from 'react-router-dom'
import { Explain } from '@/components/Explain'
import { StatusBadge } from '@/components/StatusBadge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp, signedPct } from '@/format'
import type { Holder } from '@/types'

export function HoldersTable({ holders }: { holders: Holder[] }) {
  const sorted = [...holders].sort((a, b) => b.weight - a.weight)
  return (
    <>
      <Explain>
        <p>
          <strong>Shares Δ is about shares, Weight Δ is about proportion.</strong> A manager can appear as Added with
          a falling weight, or Trimmed with a rising one — status compares its share count against last quarter, while
          weight compares the position's share of that manager's portfolio. The rest of the book moving is enough to
          separate them, with no trade in this stock at all.
        </p>
        <p>
          <em>Weight</em> is each manager's own weight in this stock, as a share of its reported equity holdings — not
          a share of the company, and not comparable across managers as a dollar amount.
        </p>
        <p>
          Share counts are compared on a consistent basis, with recorded stock splits undone first. Managers who sold
          out are listed separately below rather than shown here at a weight of zero.
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
