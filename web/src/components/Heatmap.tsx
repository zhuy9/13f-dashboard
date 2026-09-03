import { Fragment } from 'react'
import { CALL_COLOR } from '@/format'

interface HeatmapProps {
  ciks: string[]
  matrix: { values: number[] }[]
  labelByCik: Map<string, string>
}

export function Heatmap({ ciks, matrix, labelByCik }: HeatmapProps) {
  if (ciks.length === 0) return null

  return (
    <div className="overflow-x-auto">
      <div
        className="grid w-fit gap-0.5"
        style={{ gridTemplateColumns: `120px repeat(${ciks.length}, 32px)` }}
      >
        <div />
        {ciks.map((cik) => (
          <div key={cik} className="flex items-end justify-center pb-1 text-[10px] text-ink-muted">
            {labelByCik.get(cik) ?? cik}
          </div>
        ))}
        {ciks.map((rowCik, i) => (
          <Fragment key={rowCik}>
            <div className="flex items-center truncate pr-2 text-xs">{labelByCik.get(rowCik) ?? rowCik}</div>
            {ciks.map((colCik, j) => {
              const value = matrix[i]?.values[j] ?? 0
              return (
                <div
                  key={`${rowCik}-${colCik}`}
                  title={`${labelByCik.get(rowCik) ?? rowCik} vs ${labelByCik.get(colCik) ?? colCik}: ${value.toFixed(2)}`}
                  className="flex h-8 w-8 items-center justify-center text-[9px]"
                  style={{
                    backgroundColor: `${CALL_COLOR}${Math.min(255, Math.max(0, Math.round(value * 255)))
                      .toString(16)
                      .padStart(2, '0')}`,
                  }}
                >
                  {value >= 0.5 ? <span className="text-white">{value.toFixed(2)}</span> : value.toFixed(2)}
                </div>
              )
            })}
          </Fragment>
        ))}
      </div>
    </div>
  )
}
