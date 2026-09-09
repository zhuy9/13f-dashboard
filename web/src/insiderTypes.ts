import type { Timestamp } from 'firebase/firestore/lite'

// Section K's transaction code -> kind table. Exhaustive: every code maps to exactly one of
// these, and OTHER is the fallback for a code outside the ones with their own meaning.
export type InsiderKind = 'BUY' | 'SELL' | 'AWARD' | 'EXERCISE' | 'TAX' | 'GIFT' | 'CONVERSION' | 'DISPOSITION_TO_ISSUER' | 'OTHER'

export type InsiderPriority = 'HIGH' | 'MEDIUM' | 'LOW'

export type InsiderFilter = 'all' | 'buys' | 'sells' | 'planned' | 'discretionary' | 'awards' | 'exercises'

export interface InsiderTrade {
  accession: string
  form: string
  isAmendment: boolean
  filedAt: string
  transactionDate: string
  issuerCik: string | null
  issuerName: string
  symbol: string
  ownerCik: string
  ownerName: string
  role: string
  isDerivative: boolean
  security: string
  code: string
  kind: InsiderKind
  shares: number | null
  price: number | null
  value: number | null
  acquiredDisposed: string | null
  sharesAfter: number | null
  aff10b5One: boolean | null
  isPlanned: boolean
  isDiscretionarySale: boolean
  // True: this owner's first BUY on this issuer within the lookback window. Null: our log does
  // not reach back far enough to know -- absence of evidence is not evidence.
  firstBuyInWindow: boolean | null
  holders13f: number | null
  priority: InsiderPriority
  footnotes: string
  url: string
}

export interface InsiderCluster {
  symbol: string
  issuerCik: string
  issuerName: string
  buyerCount: number
  buyers: string[]
  windowDays: number
}

export interface InsiderVsThirteenF {
  symbol: string
  issuerCik: string
  issuerName: string
  buyers: number
  boughtValue: number
  holders13f: number
  hasCluster: boolean
}

// Over open-market (P/S) rows only. Planned and discretionary sales are counted separately here
// and must never be summed into one "insider selling" number.
export interface InsiderIssuerSummary {
  symbol: string
  issuerCik: string
  issuerName: string
  buyers: number
  sellers: number
  boughtShares: number
  soldShares: number
  boughtValue: number
  soldValue: number
  discretionarySellers: number
  plannedSellers: number
  lastTradeAt: string
}

// insider/feed
export interface InsiderFeed {
  updatedAt: Timestamp
  startDate: string
  lastFiledAt: string | null
  universe: { symbols: number; asOfPeriod: string | null }
  counts: { filings: number; trades: number; issuers: number; people: number }
  headline: {
    asOf: string
    windowDays: number
    windowSince: string
    startDate: string
    openMarketBuys: number
    discretionarySales: number
    clusterBuys: number
  }
  trades: InsiderTrade[]
  clusters: InsiderCluster[]
  vsThirteenF: InsiderVsThirteenF[]
}

export interface InsiderIssuerPerson {
  ownerCik: string
  ownerName: string
  role: string
  buys: number
  sells: number
  netShares: number
  lastTradeAt: string
}

// insider_issuers/{symbol}
export interface InsiderIssuer {
  symbol: string
  issuerCik: string
  issuerName: string
  sector: string
  summary: InsiderIssuerSummary | null
  people: InsiderIssuerPerson[]
  trades: InsiderTrade[]
}

export interface InsiderPersonIssuer {
  symbol: string
  issuerName: string
  role: string
  netShares: number
}

// insider_people/{cik}
export interface InsiderPerson {
  cik: string
  name: string
  roles: string[]
  issuers: InsiderPersonIssuer[]
  trades: InsiderTrade[]
}
