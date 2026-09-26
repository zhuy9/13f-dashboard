import { NEUTRAL_COLOR, STATUS_COLORS } from './format'
import type { OwnershipEventKind, OwnershipEvent, OwnershipFilter, OwnershipForm } from './ownershipTypes'

export const EVENT_FILTERS: { value: OwnershipFilter; label: string; test: (e: OwnershipEvent) => boolean }[] = [
  { value: 'all', label: 'All', test: () => true },
  { value: '13d', label: '13D', test: (e) => e.form === '13D' },
  { value: '13g', label: '13G', test: (e) => e.form === '13G' },
  { value: 'new', label: 'New', test: (e) => e.event === 'NEW' },
  { value: 'increased', label: 'Increased', test: (e) => e.event === 'INCREASED' },
  { value: 'decreased', label: 'Decreased', test: (e) => e.event === 'DECREASED' },
  { value: 'activists', label: 'Activists', test: (e) => e.isActivist },
]

export function filterEvents(events: OwnershipEvent[], filter: string, query: string): OwnershipEvent[] {
  const test = EVENT_FILTERS.find((f) => f.value === filter)?.test ?? (() => true)
  const q = query.trim().toLowerCase()
  return events.filter((e) => test(e) && (!q || [e.symbol, e.issuerName ?? '', e.investorName].some((s) => s.toLowerCase().includes(q))))
}

export function eventLabel(event: OwnershipEventKind, form: OwnershipForm): string {
  if (!event) return '—'
  if (event === 'NEW') return `NEW ${form}`
  if (event === 'SWITCHED_TO_13D') return 'SWITCHED TO 13D'
  if (event === 'SWITCHED_TO_13G') return 'SWITCHED TO 13G'
  // The stored `EXITED` only means the stake fell under the 5% reporting threshold. The
  // investor may still hold 4.9%, so "exited" is the one label here that reads as a claim
  // about the position rather than about the filing. The identifier stays; the wording goes.
  if (event === 'EXITED') return 'BELOW 5%'
  return event
}

// `pct`/`changePp` from Firestore are already whole-number percent (64.7, not 0.647), unlike
// the 13F pipeline's `weight` fraction -- format.ts's pct()/pp() would multiply by 100 again.
export function pctLabel(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

export function changePpLabel(value: number | null): string {
  if (value === null) return '—'
  const sign = value < 0 ? '−' : '+'
  return `${sign}${Math.abs(value).toFixed(1)} pp`
}

export const EVENT_COLORS: Record<Exclude<OwnershipEventKind, null>, string> = {
  NEW: STATUS_COLORS.NEW,
  INCREASED: STATUS_COLORS.NEW,
  DECREASED: STATUS_COLORS.TRIMMED,
  EXITED: STATUS_COLORS.SOLD_OUT,
  SWITCHED_TO_13D: '#0969da',
  SWITCHED_TO_13G: '#0969da',
  UPDATED: NEUTRAL_COLOR,
}

export const FORM_COLORS: Record<OwnershipForm, string> = {
  '13D': '#cf222e',
  '13G': NEUTRAL_COLOR,
}

export function investorHref(e: { investorCik: string; isRoster: boolean }): string {
  return e.isRoster ? `/manager/${e.investorCik}` : `/investor/${e.investorCik}`
}

// A real US ticker is letters only. A digit means OpenFIGI fell back to a foreign/secondary
// listing code (usually because the company was delisted or acquired, so the SEC dropped it
// from company_tickers.json), and "_" is our own no-ticker fallback. Either way we could not
// match a ticker to the filing, so the issuer's own name is the honest thing to show.
export function isUnresolvedSymbol(symbol: string): boolean {
  return symbol.startsWith('_') || /\d/.test(symbol)
}
