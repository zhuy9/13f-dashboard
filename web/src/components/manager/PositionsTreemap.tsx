import { ResponsiveContainer, Treemap } from 'recharts'
import { pct, sectorColor } from '@/format'
import type { Position } from '@/types'

interface StockNode {
  name: string
  size: number
  sector: string
  [key: string]: unknown
}

interface SectorNode {
  name: string
  children: StockNode[]
  [key: string]: unknown
}

interface CellProps {
  x?: number
  y?: number
  width?: number
  height?: number
  name?: string
  value?: number
  depth?: number
  children?: unknown[] | null
  sector?: string
}

function Cell({ x = 0, y = 0, width = 0, height = 0, name = '', value = 0, depth = 0, children, sector }: CellProps) {
  if (width < 1 || height < 1) return null

  // depth 0 is the invisible whole-chart root; nothing to draw there.
  if (depth === 0) return null

  const isSectorGroup = children != null

  if (isSectorGroup) {
    const showLabel = width > 50 && height > 14
    return (
      <g>
        <rect x={x} y={y} width={width} height={height} fill="none" stroke="var(--color-ink)" strokeOpacity={0.3} strokeWidth={1.5} />
        {showLabel && (
          <text x={x + 4} y={y + 12} fontSize={11} fontWeight={700} fill="var(--color-ink)" opacity={0.75}>
            {name} · {pct(value)}
          </text>
        )}
      </g>
    )
  }

  const showLabel = width > 42 && height > 20
  const showWeight = width > 42 && height > 34
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={sectorColor(sector ?? 'Unknown')} stroke="#faf9f6" strokeWidth={1} />
      {showLabel && (
        <text x={x + 4} y={y + 16} fill="#fff" fontSize={12} fontWeight={600}>
          {name}
        </text>
      )}
      {showWeight && (
        <text x={x + 4} y={y + 30} fill="#fff" fontSize={10} opacity={0.9}>
          {pct(value)}
        </text>
      )}
    </g>
  )
}

export function PositionsTreemap({
  positions,
  sectorBySymbol,
}: {
  positions: Position[]
  sectorBySymbol: Map<string, string>
}) {
  const top25 = positions
    .filter((p) => p.value > 0)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 25)

  const bySector = new Map<string, StockNode[]>()
  for (const p of top25) {
    const sector = sectorBySymbol.get(p.symbol) ?? 'Unknown'
    const group = bySector.get(sector) ?? []
    group.push({ name: p.symbol, size: p.weight, sector })
    bySector.set(sector, group)
  }

  const data: SectorNode[] = Array.from(bySector.entries())
    .map(([sector, children]) => ({ name: sector, children: children.sort((a, b) => b.size - a.size) }))
    .sort((a, b) => b.children.reduce((s, c) => s + c.size, 0) - a.children.reduce((s, c) => s + c.size, 0))

  if (data.length === 0) return null

  return (
    <ResponsiveContainer width="100%" height={340}>
      <Treemap
        data={data}
        dataKey="size"
        aspectRatio={4 / 3}
        nodeGap={2}
        nodeInset={16}
        content={<Cell />}
        isAnimationActive={false}
      />
    </ResponsiveContainer>
  )
}
