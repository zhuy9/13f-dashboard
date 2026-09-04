import { STATUS_COLORS } from './format'
import type { OwnershipEventKind, OwnershipEvent, OwnershipFilter, OwnershipForm } from './ownershipTypes'

export function filterEvents(events: OwnershipEvent[], filter: OwnershipFilter, query: string): OwnershipEvent[] {
  let out = events
  if (filter === '13d') out = out.filter((e) => e.form === '13D')
  else if (filter === '13g') out = out.filter((e) => e.form === '13G')
  else if (filter === 'new') out = out.filter((e) => e.event === 'NEW')
  else if (filter === 'increased') out = out.filter((e) => e.event === 'INCREASED')
  else if (filter === 'decreased') out = out.filter((e) => e.event === 'DECREASED')
  else if (filter === 'activists') out = out.filter((e) => e.isActivist)

  const q = query.trim().toLowerCase()
  if (!q) return out
  return out.filter(
    (e) =>
      e.symbol.toLowerCase().includes(q) ||
      (e.issuerName ?? '').toLowerCase().includes(q) ||
      e.investorName.toLowerCase().includes(q),
  )
}

export function eventLabel(event: OwnershipEventKind, form: OwnershipForm): string {
  if (!event) return '—'
  if (event === 'NEW') return `NEW ${form}`
  if (event === 'SWITCHED_TO_13D') return 'SWITCHED TO 13D'
  if (event === 'SWITCHED_TO_13G') return 'SWITCHED TO 13G'
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

const NEUTRAL = '#6b6759'

export const EVENT_COLORS: Record<Exclude<OwnershipEventKind, null>, string> = {
  NEW: STATUS_COLORS.NEW,
  INCREASED: STATUS_COLORS.NEW,
  DECREASED: STATUS_COLORS.TRIMMED,
  EXITED: STATUS_COLORS.SOLD_OUT,
  SWITCHED_TO_13D: '#0969da',
  SWITCHED_TO_13G: '#0969da',
  UPDATED: NEUTRAL,
}

export const FORM_COLORS: Record<OwnershipForm, string> = {
  '13D': '#cf222e',
  '13G': NEUTRAL,
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
