import { useEffect, useState } from 'react'
import { Check, Download } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useMeta } from '@/context/MetaContext'
import { csv } from '@/csv'

export function CsvExport({ rows, name, accessions = [], period: explicitPeriod, universe, minimum }: {
  rows: object[]; name: string; accessions?: string[]; period?: string; universe?: string[]; minimum?: number
}) {
  const { meta } = useMeta()
  const [params] = useSearchParams()
  const [done, setDone] = useState(false)
  const period = explicitPeriod ?? params.get('period') ?? meta?.latestPeriod

  // A download leaves no trace in the page, so the button is the only place that can confirm it.
  useEffect(() => {
    if (!done) return
    const timer = setTimeout(() => setDone(false), 2500)
    return () => clearTimeout(timer)
  }, [done])

  if (!rows.length || !meta) return null

  function download() {
    // Counts, not rosters. Coverage and the tracked universe are constant for the whole export,
    // and spelling out 34 CIKs twice per row buried the data under ~1,400 characters of identical
    // boilerplate. The managers behind a ranked row are already in that row's own column.
    const inUniverse = (cik: string) => !universe || universe.includes(cik)
    const coverage = meta?.coverage?.find(c => c.period === period)
    const text = csv(rows, {
      period,
      sourceAccessions: accessions.length ? accessions.join(' ') : undefined,
      universeManagers: (universe ?? meta?.managers.map(m => m.cik))?.length,
      managersFiled: coverage?.filed.filter(inUniverse).length,
      managersMissing: coverage?.missing.filter(inUniverse).length,
      minimumManagers: minimum,
      methodologyVersion: meta?.methodologyVersion,
    })
    const url = URL.createObjectURL(new Blob(['\ufeff', text], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${name}-${period}.csv`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    setDone(true)
  }

  // No trailing caption: this sits above every table on Patterns, and the same sentence repeated
  // ten times down one page is noise. The count is the scope, and the title carries the rest.
  return (
    <Button
      variant="ghost"
      size="sm"
      className="my-1 -ml-2.5 text-ink-muted hover:text-ink"
      onClick={download}
      title="Includes period, source filing accessions, tracked coverage and methodology version on every row"
      aria-label={`Export all ${rows.length} rows of this table as CSV`}
    >
      {done ? <Check className="text-status-new" /> : <Download />}
      {done ? 'Downloaded' : <>Export {rows.length.toLocaleString()} rows (CSV)</>}
    </Button>
  )
}
