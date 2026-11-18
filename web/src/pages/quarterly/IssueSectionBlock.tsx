import type { ReactNode } from 'react'
import type { DateRange, IssueSection, IssueWindow, SectionId } from '@/quarterlyTypes'
import { ByWindow, CrossTable, InsiderBuysTable, InsiderSalesTable, StakesTable } from './FilingTables'
import { ConvictionTable, NetTable, NewPositionsTable, SectorTable, SplitTable } from './HoldingsTables'

// Side by side at lg and up; every other section spans both columns.
const PAIRED = new Set<SectionId>(['bought', 'sold', 'insider_buys', 'insider_sales'])

type Windows = Record<IssueWindow, DateRange>

function body(section: IssueSection, windows: Windows): ReactNode {
  const timed = { noData: section.noData, totals: section.windowTotals ?? {}, windows }
  switch (section.id) {
    case 'bought':
    case 'sold':
      return section.rows.length > 0 && <NetTable rows={section.rows} side={section.id === 'bought' ? 'buy' : 'sell'} />
    case 'split':
      return section.rows.length > 0 && <SplitTable rows={section.rows} />
    case 'new_positions':
      return section.rows.length > 0 && <NewPositionsTable rows={section.rows} />
    case 'conviction':
      return section.rows.length > 0 && <ConvictionTable rows={section.rows} />
    case 'sectors':
      return section.rows.length > 0 && <SectorTable rows={section.rows} />
    case 'stakes':
      return <ByWindow rows={section.rows} {...timed} render={(rows) => <StakesTable rows={rows} />} />
    case 'insider_buys':
      return <ByWindow rows={section.rows} {...timed} render={(rows) => <InsiderBuysTable rows={rows} />} />
    case 'insider_sales':
      return <ByWindow rows={section.rows} {...timed} render={(rows) => <InsiderSalesTable rows={rows} />} />
    case 'cross':
      return section.rows.length > 0 && <CrossTable rows={section.rows} />
  }
}

interface Props {
  section: IssueSection
  number: number
  note: string | null
  windows: Windows
}

export function IssueSectionBlock({ section, number, note, windows }: Props) {
  const headingId = `q-${section.id}`
  const capped = !section.windowTotals && section.total > section.rows.length
  return (
    <section
      aria-labelledby={headingId}
      className={`flex min-w-0 flex-col gap-2 border-t border-ink pt-4 ${PAIRED.has(section.id) ? '' : 'lg:col-span-2'}`}
    >
      <p className="font-tabular text-xs font-semibold tracking-widest text-ink-muted">{String(number).padStart(2, '0')}</p>
      <h2 id={headingId} className="text-xl font-semibold leading-tight">
        {section.title}
      </h2>
      <p className="max-w-3xl text-sm">{section.summary}</p>
      {note && (
        <p className="max-w-3xl text-sm text-ink-muted">
          <span className="mr-1.5 text-[10px] font-semibold uppercase tracking-wider">AI note</span>
          {note}
        </p>
      )}
      <div className="mt-1 min-w-0">{body(section, windows)}</div>
      {capped && (
        <p className="text-xs text-ink-muted">
          Top {section.rows.length} of {section.total.toLocaleString()}.
        </p>
      )}
    </section>
  )
}
