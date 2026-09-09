import { ManagerLink } from '@/components/ManagerLink'
import { pct } from '@/format'
import type { SimilarManager } from '@/types'

export function SimilarManagers({ managers }: { managers: SimilarManager[] }) {
  if (managers.length === 0) {
    return <p className="text-sm text-ink-muted">No comparable managers this quarter.</p>
  }
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {managers.map((m) => (
        <li key={m.cik} className="flex items-center justify-between gap-2">
          <ManagerLink cik={m.cik} label={m.short} />
          <span className="font-tabular text-ink-muted">{pct(m.score)}</span>
        </li>
      ))}
    </ul>
  )
}
