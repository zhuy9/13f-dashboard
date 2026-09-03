import { Link } from 'react-router-dom'
import { StatusBadge } from '@/components/StatusBadge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp } from '@/format'
import type { Holder } from '@/types'

export function HoldersTable({ holders }: { holders: Holder[] }) {
  const sorted = [...holders].sort((a, b) => b.weight - a.weight)
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Manager</TableHead>
          <TableHead className="text-right">Weight</TableHead>
          <TableHead className="text-right">Change</TableHead>
          <TableHead>Status</TableHead>
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
            <TableCell>
              <StatusBadge status={h.status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
