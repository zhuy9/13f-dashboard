import type { Timestamp } from 'firebase/firestore/lite'

export type OwnershipForm = '13D' | '13G'

export type OwnershipEventKind =
  | 'NEW'
  | 'INCREASED'
  | 'DECREASED'
  | 'EXITED'
  | 'SWITCHED_TO_13D'
  | 'SWITCHED_TO_13G'
  | 'UPDATED'
  | null

export type OwnershipPriority = 'HIGH' | 'MEDIUM' | 'LOW'

export type OwnershipFilter = 'all' | '13d' | '13g' | 'new' | 'increased' | 'decreased' | 'activists'

export interface OwnershipEvent {
  accession: string
  form: OwnershipForm
  isAmendment: boolean
  amendmentNo: number | null
  filedAt: string
  eventDate: string | null
  investorCik: string
  investorName: string
  short: string | null
  isRoster: boolean
  isActivist: boolean
  issuerCik: string | null
  issuerName: string | null
  symbol: string
  sector: string
  shares: number | null
  pct: number | null
  prevPct: number | null
  changePp: number | null
  event: OwnershipEventKind
  priority: OwnershipPriority
  purpose: string | null
  url: string
  // Tracked managers holding this symbol at the last 13F quarter, from meta/holder_counts.
  // null when ingest has never run; 0 when it has and nobody holds it.
  holders13f: number | null
}

export interface OwnershipStake {
  investorCik: string
  investorName: string
  short: string | null
  isRoster: boolean
  isActivist: boolean
  issuerCik: string | null
  issuerName: string | null
  symbol: string
  sector: string
  form: OwnershipForm
  pct: number | null
  shares: number | null
  changePp: number | null
  event: OwnershipEventKind
  filedAt: string
  accession: string
  url: string
}

// ownership/feed
export interface OwnershipFeed {
  updatedAt: Timestamp
  startDate: string
  lastFiledAt: string | null
  counts: {
    filings: number
    investors: number
    issuers: number
  }
  events: OwnershipEvent[]
}

// ownership_issuers/{symbol}
export interface OwnershipIssuer {
  symbol: string
  issuerCik: string | null
  issuerName: string | null
  sector: string
  holders: OwnershipStake[]
  events: OwnershipEvent[]
}

// ownership_investors/{cik}
export interface OwnershipInvestor {
  cik: string
  name: string
  short: string | null
  cluster: string | null
  isRoster: boolean
  isActivist: boolean
  stakes: OwnershipStake[]
  events: OwnershipEvent[]
}
