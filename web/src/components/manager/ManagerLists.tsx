import { Link } from 'react-router-dom'
import { pct, pp } from '@/format'
import type { Position } from '@/types'

function PositionList({ title, items }: { title: string; items: Position[] }) {
  return (
    <div>
      <h3 className="mb-2 font-medium">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-ink-muted">None this quarter.</p>
      ) : (
        <ul className="flex flex-col gap-1 text-sm">
          {items.map((p) => (
            <li key={p.symbol} className="flex items-center justify-between gap-2">
              <Link to={`/stock/${p.symbol}`} className="font-tabular text-call hover:underline">
                {p.symbol}
              </Link>
              <span className="font-tabular text-ink-muted">{p.change != null ? pp(p.change) : pct(p.weight)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function ManagerLists({ positions }: { positions: Position[] }) {
  const added = positions
    .filter((p) => p.status === 'ADDED')
    .sort((a, b) => (b.change ?? 0) - (a.change ?? 0))
    .slice(0, 5)
  const trimmed = positions
    .filter((p) => p.status === 'TRIMMED' || p.status === 'SOLD_OUT')
    .sort((a, b) => (a.change ?? 0) - (b.change ?? 0))
    .slice(0, 5)
  const newPositions = positions
    .filter((p) => p.status === 'NEW')
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 5)
  const soldOut = positions
    .filter((p) => p.status === 'SOLD_OUT')
    .sort((a, b) => (a.change ?? 0) - (b.change ?? 0))
    .slice(0, 5)

  return (
    <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
      <PositionList title="Biggest Adds" items={added} />
      <PositionList title="Biggest Trims" items={trimmed} />
      <PositionList title="New Positions" items={newPositions} />
      <PositionList title="Sold Out" items={soldOut} />
    </div>
  )
}
