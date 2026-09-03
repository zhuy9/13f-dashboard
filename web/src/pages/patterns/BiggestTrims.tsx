import { BiggestChangeTable } from '@/pages/patterns/BiggestChangeTable'
import type { BiggestChangeRow } from '@/types'

export function BiggestTrims({ rows }: { rows: BiggestChangeRow[] }) {
  return <BiggestChangeTable rows={rows} emptyMessage="No trims this quarter." />
}
