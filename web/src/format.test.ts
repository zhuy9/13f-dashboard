import { describe, expect, it } from 'vitest'
import { filedDate, money, pct, pp, quarterLabel, SECTOR_COLORS } from './format'

describe('money', () => {
  it('formats billions with one decimal', () => {
    expect(money(1_200_000_000)).toBe('$1.2B')
  })
  it('formats millions with no decimal', () => {
    expect(money(340_000_000)).toBe('$340M')
  })
  it('formats thousands with no decimal', () => {
    expect(money(12_000)).toBe('$12K')
  })
  it('formats small values as plain dollars', () => {
    expect(money(500)).toBe('$500')
  })
  it('formats negative values with a leading minus', () => {
    expect(money(-2_000_000)).toBe('-$2M')
  })
})

describe('pct', () => {
  it('formats a fraction as a percentage with one decimal', () => {
    expect(pct(0.123)).toBe('12.3%')
  })
})

describe('pp', () => {
  it('formats a positive change with a leading plus', () => {
    expect(pp(0.011)).toBe('+1.1 pp')
  })
  it('formats a negative change with a minus sign', () => {
    expect(pp(-0.005)).toBe('−0.5 pp')
  })
})

describe('quarterLabel', () => {
  it('maps a quarter-end date to a year/quarter label', () => {
    expect(quarterLabel('2026-06-30')).toBe('2026 Q2')
    expect(quarterLabel('2025-12-31')).toBe('2025 Q4')
  })
})

describe('filedDate', () => {
  it('formats an ISO date as a human-readable date, without a timezone off-by-one', () => {
    expect(filedDate('2026-08-14')).toBe('Aug 14, 2026')
  })
})

describe('SECTOR_COLORS', () => {
  it('has exactly 12 fixed sectors', () => {
    expect(Object.keys(SECTOR_COLORS)).toHaveLength(12)
  })
})
