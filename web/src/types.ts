import type { Timestamp } from 'firebase/firestore'

export type PositionStatus = 'NEW' | 'ADDED' | 'TRIMMED' | 'UNCHANGED' | 'SOLD_OUT'

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

export interface SymbolRef {
  symbol: string
  name: string
  sector: string
}

export interface Meta {
  latestPeriod: string
  periods: string[]
  managers: ManagerRef[]
  clusters: ClusterSummary[]
  symbols: SymbolRef[]
  updatedAt: Timestamp
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
  value: number
  shares: number
  weight: number
  prevValue: number | null
  prevShares: number | null
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

export interface ManagerQuarter {
  filedAt: string
  totalValue: number
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
  cik: string
  short: string
  value: number
  shares: number
  weight: number
  prevWeight: number | null
  change: number | null
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
  trend: StockTrendPoint[]
  latest: StockLatest | null
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
}

export interface ConsensusExitRow {
  symbol: string
  name: string
  soldOut: number
  trimmed: number
  avgReduction: number
}

export interface HighConvictionRow {
  symbol: string
  name: string
  managers: number
  avgWeight: number
  maxWeight: number
  new: number
  added: number
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

export interface Signals {
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
