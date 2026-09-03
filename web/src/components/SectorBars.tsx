import { pct, sectorColor } from '@/format'
import type { SectorExposure } from '@/types'

export function SectorBars({ sectors }: { sectors: SectorExposure[] }) {
  const sorted = [...sectors].sort((a, b) => b.weight - a.weight)
  const maxWeight = Math.max(...sorted.map((s) => s.weight), 0.0001)

  return (
    <div className="flex flex-col gap-2">
      {sorted.map((s) => (
        <div key={s.sector} className="flex items-center gap-3">
          <span className="w-40 shrink-0 truncate text-sm">{s.sector}</span>
          <div className="h-3 flex-1 rounded bg-line/40">
            <div
              className="h-3 rounded"
              style={{ width: `${(s.weight / maxWeight) * 100}%`, backgroundColor: sectorColor(s.sector) }}
            />
          </div>
          <span className="font-tabular w-16 shrink-0 text-right text-sm">{pct(s.weight)}</span>
        </div>
      ))}
    </div>
  )
}
