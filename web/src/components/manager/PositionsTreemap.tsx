import { ResponsiveContainer, Treemap } from 'recharts'
import { sectorColor } from '@/format'
import type { Position } from '@/types'

interface TreemapNode {
  name: string
  size: number
  sector: string
  [key: string]: unknown
}

interface CellProps {
  x?: number
  y?: number
  width?: number
  height?: number
  name?: string
  sector?: string
}

function Cell({ x = 0, y = 0, width = 0, height = 0, name = '', sector = 'Unknown' }: CellProps) {
  if (width < 2 || height < 2) return null
  const showLabel = width > 42 && height > 20
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={sectorColor(sector)} stroke="#faf9f6" strokeWidth={1} />
      {showLabel && (
        <text x={x + 4} y={y + 16} fill="#fff" fontSize={12} fontWeight={600}>
          {name}
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
  const data: TreemapNode[] = positions
    .filter((p) => p.value > 0)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 25)
    .map((p) => ({ name: p.symbol, size: p.weight, sector: sectorBySymbol.get(p.symbol) ?? 'Unknown' }))

  if (data.length === 0) return null

  return (
    <ResponsiveContainer width="100%" height={320}>
      <Treemap data={data} dataKey="size" aspectRatio={4 / 3} content={<Cell />} isAnimationActive={false} />
    </ResponsiveContainer>
  )
}
