import { BiggestChangeTable } from '@/pages/patterns/BiggestChangeTable'
import type { BiggestChangeRow } from '@/types'

export function BiggestAdds({ rows }: { rows: BiggestChangeRow[] }) {
  return <BiggestChangeTable rows={rows} emptyMessage="No additions this quarter." defaultDirection="desc" />
}
