import { Fragment } from 'react'
import { CALL_COLOR } from '@/format'

interface HeatmapProps {
  ciks: string[]
  matrix: { values: number[] }[]
  labelByCik: Map<string, string>
}

const ROW_LABEL_WIDTH = 140
const CELL_SIZE = 52

export function Heatmap({ ciks, matrix, labelByCik }: HeatmapProps) {
  if (ciks.length === 0) return null

  return (
    <div className="overflow-x-auto">
      <div
        className="grid w-fit gap-0.5"
        style={{ gridTemplateColumns: `${ROW_LABEL_WIDTH}px repeat(${ciks.length}, ${CELL_SIZE}px)` }}
      >
        <div />
        {ciks.map((cik) => (
          <div
            key={cik}
            className="flex min-h-12 items-end justify-center px-0.5 pb-1 text-center text-[11px] leading-tight text-ink-muted"
          >
            {labelByCik.get(cik) ?? cik}
          </div>
        ))}
        {ciks.map((rowCik, i) => (
          <Fragment key={rowCik}>
            <div className="flex items-center truncate pr-2 text-sm">{labelByCik.get(rowCik) ?? rowCik}</div>
            {ciks.map((colCik, j) => {
              const value = matrix[i]?.values[j] ?? 0
              return (
                <div
                  key={`${rowCik}-${colCik}`}
                  title={`${labelByCik.get(rowCik) ?? rowCik} vs ${labelByCik.get(colCik) ?? colCik}: ${value.toFixed(2)}`}
                  className="flex items-center justify-center text-xs"
                  style={{
                    height: CELL_SIZE,
                    width: CELL_SIZE,
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
