import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { IssueSection } from '@/quarterlyTypes'
import { IssueSectionBlock } from './IssueSectionBlock'

const WINDOWS = { quarter: { start: '2026-07-01', end: '2026-09-30' }, since: { start: '2026-10-01', end: '2026-11-18' } }
const M = [{ cik: '1', short: 'Alpha' }]
const base = { title: 'T', summary: 'S', total: 1, noData: [] }

const SECTIONS: IssueSection[] = [
  { ...base, id: 'bought', rows: [{ symbol: 'AAA', name: 'Aaa Inc', buyers: 5, sellers: 3, net: 2, newCount: 3, addedCount: 2, trimmedCount: 3, soldOutCount: 0, managerCount: 8, avgWeight: 0.02, buyerManagers: M, contested: true }] },
  { ...base, id: 'split', rows: [{ symbol: 'BBB', name: null, buyers: 5, sellers: 5, net: 0, buyerManagers: M, sellerManagers: M }] },
  { ...base, id: 'new_positions', rows: [{ cik: '1', short: 'Alpha', symbol: 'CCC', name: 'Ccc', weight: 0.05, value: 1e6 }] },
  { ...base, id: 'conviction', rows: [{ symbol: 'DDD', name: 'Ddd', managers: 3, avgWeight: 0.04, maxWeight: 0.06, change: 'LEFT' }] },
  { ...base, id: 'sectors', rows: [{ sector: 'Technology', avgWeight: 0.3, avgPrevWeight: 0.28, avgChange: 0.02, increasing: 5, decreasing: 1 }] },
  { ...base, id: 'stakes', windowTotals: { quarter: 1, since: 0 }, rows: [{ window: 'quarter', filedAt: '2026-08-01', form: '13D', event: 'SWITCHED_TO_13D', priority: 'HIGH', investorCik: '9', investorName: 'Outside LP', short: null, isRoster: false, isActivist: false, symbol: 'EEE', issuerName: 'Eee', pct: 6.2, changePp: null, holders13f: 2, url: 'https://www.sec.gov/x' }] },
  { ...base, id: 'insider_buys', noData: ['quarter'], windowTotals: { since: 1 }, rows: [{ window: 'since', symbol: 'FFF', issuerName: 'Fff', buyers: 3, value: 5e5, holders13f: 1, isCluster: true }] },
  { ...base, id: 'insider_sales', windowTotals: { quarter: 1, since: 0 }, rows: [{ window: 'quarter', symbol: 'GGG', issuerName: 'Ggg', discretionarySellers: 1, discretionaryValue: 2e5, plannedSellers: 2, plannedValue: 1e5, holders13f: 1 }] },
  { ...base, id: 'cross', rows: [{ symbol: 'AAA', name: 'Aaa Inc', signals: ['13F', '13D'], buyers: 5, net: 2, investor: 'Alpha', investorCik: '1', isRoster: true, insiderBuyers: 0 }] },
]

function render(section: IssueSection, note: string | null = null): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <IssueSectionBlock section={section} number={1} note={note} windows={WINDOWS} />
    </MemoryRouter>,
  )
}

describe('IssueSectionBlock', () => {
  it('renders every section kind with its rows', () => {
    for (const section of SECTIONS) {
      const symbol = 'symbol' in section.rows[0] ? section.rows[0].symbol : 'Technology'
      expect(render(section)).toContain(symbol)
    }
  })

  it('says "no data" for a window the log does not cover, never an empty table', () => {
    const html = render(SECTIONS.find((s) => s.id === 'insider_buys')!)
    expect(html).toContain('No data for this window')
    expect(html).toContain('FFF')
  })

  it('renders an AI note as text, never as markup', () => {
    const html = render(SECTIONS[0], '<img src=x onerror=alert(1)>')
    expect(html).toContain('&lt;img')
    expect(html).not.toContain('<img')
  })
})
