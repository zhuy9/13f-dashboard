import { ManagerLink } from '@/components/ManagerLink'
import { StockLink } from '@/components/StockLink'
import { CALL_COLOR, PUT_COLOR } from '@/format'
import type { OptionsExposureRow } from '@/types'

function NameList({ ciks, labelByCik }: { ciks: string[]; labelByCik: Map<string, string> }) {
  if (ciks.length === 0) return <p className="text-sm text-ink-muted">None.</p>
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {ciks.map((cik) => (
        <li key={cik}>
          <ManagerLink cik={cik} label={labelByCik.get(cik) ?? cik} />
        </li>
      ))}
    </ul>
  )
}

export function PutCallExposure({
  rows,
  labelByCik,
}: {
  rows: OptionsExposureRow[]
  labelByCik: Map<string, string>
}) {
  if (rows.length === 0) return <p className="text-sm text-ink-muted">No options activity this quarter.</p>

  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-4 px-2 py-1.5 text-xs font-medium text-ink-muted">
        <span className="flex-1">Symbol</span>
        <span className="w-20 text-right">Equity</span>
        <span className="w-20 text-right">Calls</span>
        <span className="w-20 text-right">Puts</span>
      </div>
      {rows.map((r) => (
        <details key={r.symbol} className="rounded border border-line">
          <summary className="flex cursor-pointer items-center gap-4 px-2 py-1.5 text-sm">
            <span className="flex-1">
              <StockLink symbol={r.symbol} />
            </span>
            <span className="font-tabular w-20 text-right">{r.equityHolders.length}</span>
            <span className="font-tabular w-20 text-right">{r.callHolders.length}</span>
            <span className="font-tabular w-20 text-right">{r.putHolders.length}</span>
          </summary>
          <div className="grid grid-cols-1 gap-4 border-t border-line px-3 py-2 md:grid-cols-3">
            <div>
              <h4 className="mb-1 text-xs font-medium text-ink-muted">Equity Long</h4>
              <NameList ciks={r.equityHolders} labelByCik={labelByCik} />
            </div>
            <div>
              <h4 className="mb-1 text-xs font-medium" style={{ color: CALL_COLOR }}>
                Reported Calls
              </h4>
              <NameList ciks={r.callHolders} labelByCik={labelByCik} />
            </div>
            <div>
              <h4 className="mb-1 text-xs font-medium" style={{ color: PUT_COLOR }}>
                Reported Puts
              </h4>
              <NameList ciks={r.putHolders} labelByCik={labelByCik} />
            </div>
          </div>
        </details>
      ))}
    </div>
  )
}
