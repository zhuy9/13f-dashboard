import type { Timestamp } from 'firebase/firestore/lite'

export type PositionStatus = 'NEW' | 'ADDED' | 'TRIMMED' | 'UNCHANGED' | 'SOLD_OUT'

// What the filing's own Class field says the row is. A 13F carries convertible notes,
// warrants and units beside common stock; their reported value is not equity exposure.
export type SecurityKind = 'EQUITY' | 'NOTE' | 'WARRANT'

// meta/latest
export interface ManagerRef {
  cik: string
  short: string
  name: string
  cluster: string
}

export interface ClusterSummary {
  label: string
  members: string[]
  commonHoldings: string[]
  topSector: string | null
}

export interface QuarterCoverage {
  period: string
  filed: string[]
  missing: string[]
}

export interface Meta {
  datasetId?: string
  latestPeriod: string
  periods: string[]
  managers: ManagerRef[]
  clusters: ClusterSummary[]
  coverage?: QuarterCoverage[]
  methodologyVersion: number
  updatedAt: Timestamp
}

// meta/symbols -- its own doc so meta/latest stays small; only the search box reads it.
export interface SymbolIndex {
  symbols: { symbol: string; name: string; sector: string }[]
}

// managers/{cik}
export interface Manager {
  cik: string
  name: string
  short: string
  cluster: string
  periods: string[]
}

// manager_quarters/{cik}_{period}
export interface Position {
  symbol: string
  short: string
  name: string
  sector: string
  kind: SecurityKind
  // How the position came to light, not when it was bought.
  disclosedByAmendment: boolean
  // Comma-joined when an aliases13f book was reported under more than one filing. Null on a
  // SOLD_OUT row: no current filing mentions the position at all.
  accession?: string | null
  value: number
  shares: number
  weight: number
  prevValue: number | null
  prevShares: number | null
  // prevShares as filed; adjPrevShares restated onto the current share basis across a split.
  adjPrevShares?: number | null
  shareChange?: number | null
  splitUnverified?: boolean | null
  prevWeight: number | null
  change: number | null
  status: PositionStatus | null
}

export interface SectorExposure {
  sector: string
  weight: number
  prevWeight: number | null
  change: number | null
}

export interface SimilarManager {
  cik: string
  short: string
  score: number
}

export interface SourceFiling {
  accession: string
  url: string
  filedAt: string
  isAmendment: boolean
  amendmentType: string | null
  filerCik: string
}

export interface ManagerQuarter {
  priorPositions?: { symbol: string; period: string; held: boolean }[]
  filedAt: string
  totalValue: number
  equityValue: number
  filings?: SourceFiling[]
  count: number
  counts: {
    new: number
    added: number
    trimmed: number
    unchanged: number
    soldOut: number
  }
  positions: Position[]
  sectors: SectorExposure[]
  mostSimilar: SimilarManager[]
}

// stocks/{symbol}
export interface StockTrendPoint {
  period: string
  managerCount: number
  avgWeight: number
  medianWeight: number
  maxWeight: number
  newManagers: number
  exitedManagers: number
  netChange: number
}

export interface Holder {
  accession?: string | null
  cik: string
  short: string
  value: number
  shares: number
  weight: number
  prevWeight: number | null
  change: number | null
  // Optional: documents published before this field existed do not carry it.
  shareChange?: number | null
  status: PositionStatus | null
}

export interface SoldOutHolder {
  cik: string
  short: string
  prevWeight: number
}

export interface OptionHolderRef {
  cik: string
  short: string
}

export interface StockLatest {
  filings?: SourceFiling[]
  period: string
  managerCount: number
  managersTotal: number
  pctHolding: number
  avgWeight: number
  medianWeight: number
  maxWeight: number
  totalValue: number
  newCount: number
  addedCount: number
  trimmedCount: number
  unchangedCount: number
  soldOutCount: number
  holders: Holder[]
  soldOut: SoldOutHolder[]
  options: {
    calls: OptionHolderRef[]
    puts: OptionHolderRef[]
  }
}

export interface Stock {
  symbol: string
  name: string
  sector: string
  kind: SecurityKind
  trend: StockTrendPoint[]
  // Only in datasets published before Milestone 14 introduced stock_quarters/. Current ingests
  // omit it, and the readers below treat it as a fallback. Delete both once no legacy dataset
  // is reachable -- see "Legacy stock latest" in docs/PLAN.md.
  latest?: StockLatest | null
}

// signals/{period}
export interface ConsensusBuyRow {
  symbol: string
  name: string
  newBuyers: number
  added: number
  avgWeight: number
  avgWeightIncrease: number
  score: number
  // score = round(100 * raw / scorePeak); scorePeak is the quarter's highest raw score.
  // Optional because a document published before this field existed will not carry it, and
  // the web app deploys on push while the pipeline republishes on its own schedule.
  raw?: number
  scorePeak?: number
  managers?: string[]
}

export interface ConsensusExitRow {
  symbol: string
  name: string
  soldOut: number
  trimmed: number
  avgReduction: number
  managers?: string[]
}

export interface HighConvictionRow {
  symbol: string
  name: string
  managers: number
  avgWeight: number
  maxWeight: number
  new: number
  added: number
  managerNames?: string[]
}

export interface BiggestNewRow {
  cik: string
  short: string
  symbol: string
  name: string
  weight: number
  value: number
}

export interface BiggestChangeRow {
  cik: string
  short: string
  symbol: string
  name: string
  weight: number
  change: number
  value: number
}

export interface TopSignalRow {
  symbol: string
  name: string
  score: number
  managerCount: number
  avgWeight: number
  newCount: number
  addedCount: number
}

export interface FastestGrowingRow {
  symbol: string
  name: string
  prevCount: number
  count: number
  newManagers: number
  exitedManagers: number
  netChange: number
}

export interface SectorRotationRow {
  sector: string
  avgWeight: number
  avgPrevWeight: number
  avgChange: number
  increasing: number
  decreasing: number
}

export interface ManagerSimilarity {
  ciks: string[]
  matrix: { values: number[] }[]
}

export interface OptionsExposureRow {
  symbol: string
  equityHolders: string[]
  callHolders: string[]
  putHolders: string[]
}

export interface SignalConfig {
  consensusMinManagers: number
  highConvictionMinManagers: number
  highConvictionMinWeight: number
  sectorMoveThreshold: number
  topN: number
  score: { weightScale: number; newBonus: number; addedBonus: number; accumulationScale: number; accumulationCap: number }
}

export interface Signals {
  config?: SignalConfig
  filings?: SourceFiling[]
  consensusBuys: ConsensusBuyRow[]
  consensusExits: ConsensusExitRow[]
  highConviction: HighConvictionRow[]
  biggestNew: BiggestNewRow[]
  biggestAdds: BiggestChangeRow[]
  biggestTrims: BiggestChangeRow[]
  topSignals: TopSignalRow[]
  fastestGrowing: FastestGrowingRow[]
  sectorRotation: SectorRotationRow[]
  managerSimilarity: ManagerSimilarity
  optionsExposure: OptionsExposureRow[]
}
