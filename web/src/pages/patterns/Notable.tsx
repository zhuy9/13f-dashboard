import { StatTile } from '@/components/StatTile'
import { pct, pp } from '@/format'
import type { Signals } from '@/types'

// Picks the top row of the displayed rankings. Each card links to its full table.
export function Notable({ data }: { data: Signals }) {
  const [buy, sold, crowded, rotation] = [
    data.consensusBuys[0],
    data.consensusExits[0],
    data.highConviction[0],
    data.sectorRotation[0],
  ]
  // Keys match StatTile's props so each survivor spreads straight in.
  const cards = [
    buy && {
      href: '#consensus-buys',
      label: 'Most bought',
      value: buy.symbol,
      detail: `${buy.newBuyers} opened, ${buy.added} added`,
    },
    sold && {
      href: '#consensus-exits',
      label: 'Most sold',
      value: sold.symbol,
      detail: `${sold.soldOut} sold out, ${sold.trimmed} trimmed`,
    },
    crowded && {
      href: '#high-conviction',
      label: 'Most crowded',
      value: crowded.symbol,
      detail: `${crowded.managers} managers at ${pct(crowded.avgWeight)} average`,
    },
    rotation && {
      href: '#sector-rotation',
      label: 'Sector moving in',
      value: rotation.sector,
      detail: `${pp(rotation.avgChange)} average weight`,
    },
  ].filter(Boolean)

  if (cards.length === 0) return null
  return (
    // One column below 640 px: two of these side by side at 375 px leaves about 165 px for
    // "15 managers at 7.9% average", which truncates to nothing useful.
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <StatTile key={c.label} {...c} />
      ))}
    </div>
  )
}

