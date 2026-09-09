import { STATUS_COLORS } from './format'
import type { InsiderFilter, InsiderKind, InsiderTrade } from './insiderTypes'

export function filterTrades(trades: InsiderTrade[], filter: InsiderFilter, query: string): InsiderTrade[] {
  let out = trades
  if (filter === 'buys') out = out.filter((t) => t.kind === 'BUY')
  else if (filter === 'sells') out = out.filter((t) => t.kind === 'SELL')
  else if (filter === 'planned') out = out.filter((t) => t.isPlanned)
  else if (filter === 'discretionary') out = out.filter((t) => t.isDiscretionarySale)
  else if (filter === 'awards') out = out.filter((t) => t.kind === 'AWARD')
  else if (filter === 'exercises') out = out.filter((t) => t.kind === 'EXERCISE')

  const q = query.trim().toLowerCase()
  if (!q) return out
  return out.filter(
    (t) =>
      t.symbol.toLowerCase().includes(q) ||
      t.issuerName.toLowerCase().includes(q) ||
      t.ownerName.toLowerCase().includes(q),
  )
}

// Never "Bought" for a grant/exercise, never "Sold" for a tax withholding/gift -- the whole
// point of classifying on `code` instead of edgartools' own mislabeled "Transaction Type".
const KIND_LABELS: Record<InsiderKind, string> = {
  BUY: 'Bought',
  SELL: 'Sold',
  AWARD: 'Awarded',
  EXERCISE: 'Exercised',
  TAX: 'Tax Withholding',
  GIFT: 'Gift',
  CONVERSION: 'Conversion',
  DISPOSITION_TO_ISSUER: 'Disposed to Issuer',
  OTHER: 'Other',
}

export function kindLabel(kind: InsiderKind): string {
  return KIND_LABELS[kind]
}

// The Python-side `role` already reads "Officer (CEO)"; a table cell wants the shorter form,
// with the title still available in the source field for anywhere that wants it in full.
export function roleLabel(role: string): string {
  return role.replace(/\s*\(.*\)$/, '')
}

const NEUTRAL = '#6b6759'

export const KIND_COLORS: Record<InsiderKind, string> = {
  BUY: STATUS_COLORS.NEW,
  SELL: STATUS_COLORS.SOLD_OUT,
  AWARD: NEUTRAL,
  EXERCISE: NEUTRAL,
  TAX: NEUTRAL,
  GIFT: NEUTRAL,
  CONVERSION: NEUTRAL,
  DISPOSITION_TO_ISSUER: NEUTRAL,
  OTHER: NEUTRAL,
}

export function personHref(cik: string): string {
  return `/insider/${cik}`
}

// One React key per row, unique by construction.
//
// The published data has no unique row id, and no combination of its fields is one: a single
// Form 4 routinely reports the same transaction line twice -- the two legs of an exercise (the
// stock acquired and the derivative disposed), or genuinely repeated tranches. Measured over the
// 242,029 rows on file, 13.5% collide on (accession, owner, code, shares, date), and 0.5% still
// collide with every other field thrown in. Duplicate keys are what made the trades table drop
// and reuse rows when the filter changed, so the row count above it moved while the rows below
// it did not. The occurrence index is the part that actually guarantees uniqueness.
//
// ponytail: identity derived in the browser. Publish a real row id from insider_fetch.py if
// anything ever needs to address a single trade row across a reload.
export function tradeKeys(trades: InsiderTrade[]): string[] {
  const seen = new Map<string, number>()
  return trades.map((t) => {
    const base = `${t.accession}-${t.ownerCik}-${t.code}-${t.shares}-${t.transactionDate}-${t.isDerivative}`
    const n = (seen.get(base) ?? 0) + 1
    seen.set(base, n)
    return `${base}#${n}`
  })
}

// A sale's basis is worth its own label next to the Sold badge: "not stated" is a real third
// state (the checkbox predates or was omitted from the filing), never folded into discretionary.
export function saleBasisLabel(trade: InsiderTrade): string | null {
  if (trade.kind !== 'SELL') return null
  if (trade.isPlanned) return 'Planned (10b5-1)'
  if (trade.isDiscretionarySale) return 'Discretionary'
  return 'Not stated'
}
