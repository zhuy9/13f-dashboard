import { useSearchParams } from 'react-router-dom'
import { useMeta } from '@/context/MetaContext'
import { csv } from '@/csv'

export function CsvExport({ rows, name, accessions = [], period: explicitPeriod }: {
  rows: object[]; name: string; accessions?: string[]; period?: string
}) {
  const { meta } = useMeta()
  const [params] = useSearchParams()
  const period = explicitPeriod ?? params.get('period') ?? meta?.latestPeriod
  if (!rows.length || !meta) return null
  function download() {
    const text = csv(rows, { period, sourceAccessions: accessions, coverage: meta?.coverage?.find(c => c.period === period),
      trackedManagers: meta?.managers.map(m => m.cik), methodologyVersion: meta?.methodologyVersion })
    const url = URL.createObjectURL(new Blob(['\ufeff', text], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${name}-${period}.csv`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <button className="my-2 text-sm text-call underline" onClick={download}>Export all {rows.length} rows in this table (CSV)</button>
}
