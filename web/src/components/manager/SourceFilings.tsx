import { filedDate } from '@/format'
import type { SourceFiling } from '@/types'

function label(filing: SourceFiling): string {
  if (!filing.isAmendment) return 'Original'
  if (filing.amendmentType === 'RESTATEMENT') return 'Amendment (restated)'
  if (filing.amendmentType === 'NEW HOLDINGS') return 'Amendment (added holdings)'
  return 'Amendment'
}

// The filings a quarter's numbers actually came from. Listed once per quarter rather than per
// position, because one filing normally reports every position; a position's own accession
// picks its row out of this list when a book was split across filings.
export function SourceFilings({ filings, cik }: { filings: SourceFiling[]; cik: string }) {
  if (filings.length === 0) return null
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {filings.map((f) => (
        <li key={f.accession} className="flex flex-wrap items-baseline gap-x-2">
          <a href={f.url} target="_blank" rel="noreferrer" className="font-tabular text-call hover:underline">
            {f.accession}
          </a>
          <span className="text-ink-muted">
            {label(f)}, filed {filedDate(f.filedAt)}
          </span>
          {/* A book filed under another of the firm's CIKs is otherwise unfindable on EDGAR. */}
          {f.filerCik !== cik && <span className="text-xs text-ink-muted">filed under CIK {f.filerCik}</span>}
        </li>
      ))}
    </ul>
  )
}
