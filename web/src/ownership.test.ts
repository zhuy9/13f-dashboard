import { describe, expect, it } from 'vitest'
import { changePpLabel, eventLabel, filterEvents, investorHref, isUnresolvedSymbol, pctLabel } from './ownership'
import type { OwnershipEvent } from './ownershipTypes'

function event(overrides: Partial<OwnershipEvent>): OwnershipEvent {
  return {
    accession: 'acc',
    form: '13D',
    isAmendment: false,
    amendmentNo: null,
    filedAt: '2026-08-14',
    eventDate: '2026-08-10',
    investorCik: '1791786',
    investorName: 'Elliott Investment Management L.P.',
    short: 'Elliott',
    isRoster: true,
    isActivist: true,
    issuerCik: '1234567890',
    issuerName: 'Widget Corp',
    symbol: 'WDGT',
    sector: 'Technology',
    shares: 1000,
    pct: 6.5,
    prevPct: null,
    changePp: null,
    event: 'NEW',
    priority: 'HIGH',
    purpose: null,
    url: 'https://www.sec.gov/example',
    ...overrides,
  }
}

const events: OwnershipEvent[] = [
  event({ accession: 'a', form: '13D', event: 'NEW', isActivist: true, symbol: 'WDGT', issuerName: 'Widget Corp', investorName: 'Elliott' }),
  event({ accession: 'b', form: '13G', event: 'NEW', isActivist: false, symbol: 'GDGT', issuerName: 'Gadget Corp', investorName: 'Passive Fund' }),
  event({ accession: 'c', form: '13D', event: 'INCREASED', isActivist: false, symbol: 'ACME', issuerName: 'Acme Inc', investorName: 'Some Filer' }),
  event({ accession: 'd', form: '13D', event: 'DECREASED', isActivist: false, symbol: 'FOO', issuerName: 'Foo Inc', investorName: 'Foo Filer' }),
]

describe('filterEvents', () => {
  it('returns everything for "all"', () => {
    expect(filterEvents(events, 'all', '')).toHaveLength(4)
  })
  it('filters to 13D', () => {
    expect(filterEvents(events, '13d', '').every((e) => e.form === '13D')).toBe(true)
    expect(filterEvents(events, '13d', '')).toHaveLength(3)
  })
  it('filters to 13G', () => {
    expect(filterEvents(events, '13g', '')).toHaveLength(1)
  })
  it('filters to new', () => {
    expect(filterEvents(events, 'new', '')).toHaveLength(2)
  })
  it('filters to increased', () => {
    expect(filterEvents(events, 'increased', '')).toHaveLength(1)
  })
  it('filters to decreased', () => {
    expect(filterEvents(events, 'decreased', '')).toHaveLength(1)
  })
  it('filters to activists', () => {
    expect(filterEvents(events, 'activists', '')).toHaveLength(1)
  })
  it('matches a query against symbol, issuer name, or investor name, case-insensitively', () => {
    expect(filterEvents(events, 'all', 'wdgt')).toHaveLength(1)
    expect(filterEvents(events, 'all', 'gadget')).toHaveLength(1)
    expect(filterEvents(events, 'all', 'ELLIOTT')).toHaveLength(1)
    expect(filterEvents(events, 'all', 'nonexistent')).toHaveLength(0)
  })
})

describe('eventLabel', () => {
  it('labels NEW with the form', () => {
    expect(eventLabel('NEW', '13D')).toBe('NEW 13D')
    expect(eventLabel('NEW', '13G')).toBe('NEW 13G')
  })
  it('labels a form switch', () => {
    expect(eventLabel('SWITCHED_TO_13D', '13D')).toBe('SWITCHED TO 13D')
    expect(eventLabel('SWITCHED_TO_13G', '13G')).toBe('SWITCHED TO 13G')
  })
  it('passes through the other kinds as-is', () => {
    expect(eventLabel('INCREASED', '13D')).toBe('INCREASED')
    expect(eventLabel('DECREASED', '13D')).toBe('DECREASED')
    expect(eventLabel('EXITED', '13D')).toBe('EXITED')
    expect(eventLabel('UPDATED', '13D')).toBe('UPDATED')
  })
  it('shows an em dash for null (unknown, no prior filing in the log)', () => {
    expect(eventLabel(null, '13D')).toBe('—')
  })
})

describe('pctLabel', () => {
  it('formats an already-percent value with one decimal', () => {
    expect(pctLabel(64.7)).toBe('64.7%')
  })
  it('shows an em dash for null', () => {
    expect(pctLabel(null)).toBe('—')
  })
})

describe('changePpLabel', () => {
  it('formats a positive change with a leading plus', () => {
    expect(changePpLabel(2.9)).toBe('+2.9 pp')
  })
  it('formats a negative change with a minus sign', () => {
    expect(changePpLabel(-0.8)).toBe('−0.8 pp')
  })
  it('shows an em dash for null', () => {
    expect(changePpLabel(null)).toBe('—')
  })
})

describe('investorHref', () => {
  it('links a roster investor to its manager page', () => {
    expect(investorHref({ investorCik: '1791786', isRoster: true })).toBe('/manager/1791786')
  })
  it('links a non-roster investor to the investor page', () => {
    expect(investorHref({ investorCik: '9999999999', isRoster: false })).toBe('/investor/9999999999')
  })
})

describe('isUnresolvedSymbol', () => {
  it('treats a plain letters-only ticker as resolved', () => {
    expect(isUnresolvedSymbol('AAPL')).toBe(false)
    expect(isUnresolvedSymbol('TFPM')).toBe(false)
    expect(isUnresolvedSymbol('AB')).toBe(false)
  })
  it('treats our own no-ticker fallback as unresolved', () => {
    expect(isUnresolvedSymbol('_037833100')).toBe(true)
    expect(isUnresolvedSymbol('_ISSUER0001234567')).toBe(true)
  })
  it('treats a foreign/secondary listing code as unresolved', () => {
    // Real examples from the backfill: Endeavor Group, EnLink, Kezar, a CUSIP-shaped code.
    expect(isUnresolvedSymbol('0C3')).toBe(true)
    expect(isUnresolvedSymbol('0E41')).toBe(true)
    expect(isUnresolvedSymbol('2KZ0')).toBe(true)
    expect(isUnresolvedSymbol('2662247D')).toBe(true)
  })
})
