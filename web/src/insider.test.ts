import { describe, expect, it } from 'vitest'
import { filterTrades, kindLabel, personHref, roleLabel, saleBasisLabel, tradeKeys } from './insider'
import type { InsiderKind, InsiderTrade } from './insiderTypes'

function trade(overrides: Partial<InsiderTrade>): InsiderTrade {
  return {
    accession: 'acc',
    form: '4',
    isAmendment: false,
    filedAt: '2026-08-14',
    transactionDate: '2026-08-13',
    issuerCik: '1234567890',
    issuerName: 'Widget Corp',
    symbol: 'WDGT',
    ownerCik: '9876543210',
    ownerName: 'Jane Doe',
    role: 'Officer (CEO)',
    isDerivative: false,
    security: 'Common Stock',
    code: 'P',
    kind: 'BUY',
    shares: 1000,
    price: 50,
    value: 50000,
    acquiredDisposed: 'A',
    sharesAfter: 5000,
    aff10b5One: null,
    isPlanned: false,
    isDiscretionarySale: false,
    firstBuyInWindow: true,
    holders13f: 3,
    priority: 'HIGH',
    footnotes: '',
    url: 'https://www.sec.gov/example',
    ...overrides,
  }
}

const trades: InsiderTrade[] = [
  trade({ accession: 'a', kind: 'BUY', code: 'P', symbol: 'WDGT', issuerName: 'Widget Corp', ownerName: 'Jane Doe' }),
  trade({ accession: 'b', kind: 'SELL', code: 'S', isPlanned: true, symbol: 'GDGT', issuerName: 'Gadget Corp', ownerName: 'Passive Insider' }),
  trade({ accession: 'c', kind: 'SELL', code: 'S', isDiscretionarySale: true, symbol: 'ACME', issuerName: 'Acme Inc', ownerName: 'Some Insider' }),
  trade({ accession: 'd', kind: 'AWARD', code: 'A', symbol: 'FOO', issuerName: 'Foo Inc', ownerName: 'Foo Insider' }),
  trade({ accession: 'e', kind: 'EXERCISE', code: 'M', symbol: 'BAR', issuerName: 'Bar Inc', ownerName: 'Bar Insider' }),
]

describe('filterTrades', () => {
  it('returns everything for "all"', () => {
    expect(filterTrades(trades, 'all', '')).toHaveLength(5)
  })
  it('filters to buys', () => {
    expect(filterTrades(trades, 'buys', '')).toHaveLength(1)
  })
  it('filters to sells', () => {
    expect(filterTrades(trades, 'sells', '')).toHaveLength(2)
  })
  it('filters to planned sales', () => {
    expect(filterTrades(trades, 'planned', '')).toHaveLength(1)
  })
  it('filters to discretionary sales', () => {
    expect(filterTrades(trades, 'discretionary', '')).toHaveLength(1)
  })
  it('filters to awards', () => {
    expect(filterTrades(trades, 'awards', '')).toHaveLength(1)
  })
  it('filters to exercises', () => {
    expect(filterTrades(trades, 'exercises', '')).toHaveLength(1)
  })
  it('matches a query against symbol, issuer name, or owner name, case-insensitively', () => {
    expect(filterTrades(trades, 'all', 'wdgt')).toHaveLength(1)
    expect(filterTrades(trades, 'all', 'gadget')).toHaveLength(1)
    expect(filterTrades(trades, 'all', 'JANE')).toHaveLength(1)
    expect(filterTrades(trades, 'all', 'nonexistent')).toHaveLength(0)
  })
})

describe('kindLabel', () => {
  const AWARD_LIKE: InsiderKind[] = ['AWARD', 'EXERCISE', 'CONVERSION']
  const SALE_LIKE: InsiderKind[] = ['TAX', 'GIFT']

  it('never returns "Bought" for an award, exercise, or conversion', () => {
    for (const kind of AWARD_LIKE) expect(kindLabel(kind)).not.toBe('Bought')
  })
  it('never returns "Sold" for a tax withholding or gift', () => {
    for (const kind of SALE_LIKE) expect(kindLabel(kind)).not.toBe('Sold')
  })
  it('labels a real purchase and sale plainly', () => {
    expect(kindLabel('BUY')).toBe('Bought')
    expect(kindLabel('SELL')).toBe('Sold')
  })
})

describe('roleLabel', () => {
  it('strips a parenthetical officer title', () => {
    expect(roleLabel('Officer (CEO)')).toBe('Officer')
  })
  it('leaves a role with no title alone', () => {
    expect(roleLabel('Director')).toBe('Director')
    expect(roleLabel('Officer, Director, 10% Owner')).toBe('Officer, Director, 10% Owner')
  })
})

describe('personHref', () => {
  it('links to the insider person page', () => {
    expect(personHref('9876543210')).toBe('/insider/9876543210')
  })
})

describe('tradeKeys', () => {
  it('is unique for the two legs of one exercise, which differ only by isDerivative', () => {
    // A real pair from the feed: the common stock acquired and the RSU disposed, same
    // accession, owner, code, shares and date.
    const legs = [
      trade({ accession: 'a1', code: 'M', shares: 1014, transactionDate: '2026-09-03', isDerivative: false }),
      trade({ accession: 'a1', code: 'M', shares: 1014, transactionDate: '2026-09-03', isDerivative: true }),
    ]
    expect(new Set(tradeKeys(legs)).size).toBe(2)
  })

  it('is unique even for rows identical in every field', () => {
    // 0.5% of rows on file are indistinguishable by every field combined; the occurrence
    // index is what keeps their keys apart. Duplicate keys are what broke the filtered table.
    const twins = [trade({ accession: 'a2' }), trade({ accession: 'a2' }), trade({ accession: 'a2' })]
    expect(new Set(tradeKeys(twins)).size).toBe(3)
  })

  it('gives one key per row, in order', () => {
    expect(tradeKeys(trades)).toHaveLength(trades.length)
  })

  it('is stable across calls, so a re-render does not re-key every row', () => {
    expect(tradeKeys(trades)).toEqual(tradeKeys(trades))
  })
})

describe('saleBasisLabel', () => {
  it('is null for a non-sale', () => {
    expect(saleBasisLabel(trade({ kind: 'BUY' }))).toBeNull()
  })
  it('labels a planned sale apart from a discretionary one', () => {
    expect(saleBasisLabel(trade({ kind: 'SELL', isPlanned: true, isDiscretionarySale: false }))).toBe('Planned (10b5-1)')
    expect(saleBasisLabel(trade({ kind: 'SELL', isPlanned: false, isDiscretionarySale: true }))).toBe('Discretionary')
  })
  it('labels an unstated 10b5-1 checkbox as not stated, never as discretionary', () => {
    expect(saleBasisLabel(trade({ kind: 'SELL', isPlanned: false, isDiscretionarySale: false }))).toBe('Not stated')
  })
})
