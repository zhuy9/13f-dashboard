import type { PositionStatus, SecurityKind } from './types'

export function money(value: number): string {
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(0)}M`
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`
  return `${sign}$${abs.toFixed(0)}`
}

export function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

// A share-count change is a ratio, not a weight: +100% means the position doubled. Distinct
// from pp(), which reports a move in percentage points of the portfolio.
export function signedPct(value: number): string {
  const points = value * 100
  const sign = points < 0 ? '\u2212' : '+'
  return `${sign}${Math.abs(points).toFixed(1)}%`
}

export function pp(value: number): string {
  const points = value * 100
  const sign = points < 0 ? '−' : '+'
  return `${sign}${Math.abs(points).toFixed(1)} pp`
}

const QUARTER_BY_MONTH: Record<string, string> = {
  '03': 'Q1',
  '06': 'Q2',
  '09': 'Q3',
  '12': 'Q4',
}

export function quarterLabel(period: string): string {
  const [year, month] = period.split('-')
  return `${year} ${QUARTER_BY_MONTH[month] ?? month}`
}

export function filedDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return isoDate
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

// A 13F is not due until 45 days after the quarter it covers ends.
export function filingDue(period: string): string {
  const [year, month, day] = period.split('-').map(Number)
  return filedDate(new Date(Date.UTC(year, month - 1, day + 45)).toISOString().slice(0, 10))
}

// Every period is a quarter end, i.e. the last day of a month, and day 0 of month n is the last
// day of month n-1 -- so month + 4, day 0 is the next quarter end, rolling the year over itself.
export function nextPeriod(period: string): string {
  const [year, month] = period.split('-').map(Number)
  return new Date(Date.UTC(year, month + 3, 0)).toISOString().slice(0, 10)
}

export const SECTOR_COLORS: Record<string, string> = {
  Technology: '#4361ee',
  Financials: '#3a86ff',
  'Health Care': '#06d6a0',
  'Consumer Discretionary': '#f72585',
  'Consumer Staples': '#7209b7',
  Industrials: '#495057',
  'Energy & Mining': '#6f4518',
  Materials: '#4cc9f0',
  Communication: '#560bad',
  Utilities: '#023e8a',
  'Real Estate': '#b5838d',
  'ETF / Fund': '#adb5bd',
  Other: '#ced4da',
}

const DEFAULT_SECTOR_COLOR = '#9ca3af'

export function sectorColor(sector: string): string {
  return SECTOR_COLORS[sector] ?? DEFAULT_SECTOR_COLOR
}

export const STATUS_COLORS: Record<PositionStatus, string> = {
  NEW: '#1a7f37',
  ADDED: '#1a7f37',
  TRIMMED: '#9a6700',
  UNCHANGED: '#6b6759',
  SOLD_OUT: '#cf222e',
}

export const KIND_COLORS: Record<Exclude<SecurityKind, 'EQUITY'>, string> = {
  NOTE: '#7209b7',
  WARRANT: '#9a6700',
}

export const PUT_COLOR = '#cf222e'
export const CALL_COLOR = '#0969da'
