import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { pct, pp } from '@/format'
import type { SectorExposure } from '@/types'

export function SectorQoQTable({ sectors }: { sectors: SectorExposure[] }) {
  const sorted = [...sectors].sort((a, b) => b.weight - a.weight)
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Sector</TableHead>
          <TableHead className="text-right">Prev</TableHead>
          <TableHead className="text-right">Current</TableHead>
          <TableHead className="text-right">Change</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((s) => (
          <TableRow key={s.sector}>
            <TableCell>{s.sector}</TableCell>
            <TableCell className="font-tabular text-right">{s.prevWeight != null ? pct(s.prevWeight) : '—'}</TableCell>
            <TableCell className="font-tabular text-right">{pct(s.weight)}</TableCell>
            <TableCell className="font-tabular text-right">{s.change != null ? pp(s.change) : '—'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
