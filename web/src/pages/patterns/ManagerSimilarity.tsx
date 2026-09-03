import { Heatmap } from '@/components/Heatmap'
import { ManagerLink } from '@/components/ManagerLink'
import { pct } from '@/format'
import type { ManagerSimilarity as ManagerSimilarityData } from '@/types'

export function ManagerSimilarity({
  similarity,
  labelByCik,
}: {
  similarity: ManagerSimilarityData
  labelByCik: Map<string, string>
}) {
  const { ciks, matrix } = similarity
  if (ciks.length === 0) return <p className="text-sm text-ink-muted">No similarity data this quarter.</p>

  const mostSimilar = ciks.map((cik, i) => {
    const others = ciks
      .map((otherCik, j) => ({ cik: otherCik, score: matrix[i]?.values[j] ?? 0 }))
      .filter((o) => o.cik !== cik)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
    return { cik, others }
  })

  return (
    <div className="flex flex-col gap-6">
      <Heatmap ciks={ciks} matrix={matrix} labelByCik={labelByCik} />
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        {mostSimilar.map(({ cik, others }) => (
          <div key={cik}>
            <h3 className="mb-2 font-medium">{labelByCik.get(cik) ?? cik}</h3>
            <ul className="flex flex-col gap-1 text-sm">
              {others.map((o) => (
                <li key={o.cik} className="flex items-center justify-between gap-2">
                  <ManagerLink cik={o.cik} label={labelByCik.get(o.cik) ?? o.cik} />
                  <span className="font-tabular text-ink-muted">{pct(o.score)}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
