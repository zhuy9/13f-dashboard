// The quarterly issue docs (docs/PLAN.md section M): quarterly/index and quarterly/{period}.

export type IssueWindow = 'quarter' | 'since'

export interface DateRange {
  start: string
  end: string
}

export interface ManagerRef {
  cik: string
  short: string
}

export interface NetRow {
  symbol: string
  name: string | null
  buyers: number
  sellers: number
  net: number
  newCount: number
  addedCount: number
  trimmedCount: number
  soldOutCount: number
  managerCount: number
  avgWeight: number | null
  buyerManagers?: ManagerRef[]
  sellerManagers?: ManagerRef[]
  contested: boolean
}

export interface SplitRow {
  symbol: string
  name: string | null
  buyers: number
  sellers: number
  net: number
  buyerManagers: ManagerRef[]
  sellerManagers: ManagerRef[]
}

export interface NewPositionRow {
  cik: string
  short: string
  symbol: string
  name: string | null
  weight: number
  value: number
}

export interface ConvictionRow {
  symbol: string
  name: string | null
  managers: number
  avgWeight: number
  maxWeight: number
  change: 'ENTERED' | 'STAYED' | 'LEFT'
}

export interface SectorRow {
  sector: string
  avgWeight: number
  avgPrevWeight: number
  avgChange: number
  increasing: number
  decreasing: number
}

export interface StakeRow {
  window: IssueWindow
  filedAt: string
  form: '13D' | '13G'
  event: string
  priority: string
  investorCik: string
  investorName: string
  short: string | null
  isRoster: boolean
  isActivist: boolean
  symbol: string
  issuerName: string | null
  pct: number | null
  changePp: number | null
  holders13f: number
  url: string
}

export interface InsiderBuyRow {
  window: IssueWindow
  symbol: string
  issuerName: string | null
  buyers: number
  value: number
  holders13f: number
  isCluster: boolean
}

export interface InsiderSaleRow {
  window: IssueWindow
  symbol: string
  issuerName: string | null
  discretionarySellers: number
  discretionaryValue: number
  plannedSellers: number
  plannedValue: number
  holders13f: number
}

export type CrossSignal = '13F' | '13D' | 'INSIDER'

export interface CrossRow {
  symbol: string
  name: string | null
  signals: CrossSignal[]
  buyers: number | null
  net: number | null
  investor: string | null
  investorCik: string | null
  isRoster: boolean | null
  insiderBuyers: number
}

interface SectionBase<I extends string, R> {
  id: I
  title: string
  summary: string
  total: number
  noData: IssueWindow[]
  windowTotals?: Partial<Record<IssueWindow, number>>
  rows: R[]
}

export type IssueSection =
  | SectionBase<'bought' | 'sold', NetRow>
  | SectionBase<'split', SplitRow>
  | SectionBase<'new_positions', NewPositionRow>
  | SectionBase<'conviction', ConvictionRow>
  | SectionBase<'sectors', SectorRow>
  | SectionBase<'stakes', StakeRow>
  | SectionBase<'insider_buys', InsiderBuyRow>
  | SectionBase<'insider_sales', InsiderSaleRow>
  | SectionBase<'cross', CrossRow>

export type SectionId = IssueSection['id']

export interface QuarterlyAi {
  model: string
  generatedAt: string
  factsHash: string
  headline: string | null
  lede: string | null
  notes: Partial<Record<SectionId, string>>
}

export interface QuarterlyIssue {
  period: string
  prevPeriod: string
  label: string
  builtAt: string
  datasetId: string | null
  windows: Record<IssueWindow, DateRange>
  coverage: { filed: number; total: number; missing: string[] }
  totals: { opened: number; closed: number; added: number; trimmed: number; unchanged: number }
  headline: string
  lede: string
  sections: IssueSection[]
  ai: QuarterlyAi | null
}

export interface QuarterlyIndex {
  updatedAt: string
  issues: { period: string; label: string; headline: string; builtAt: string }[]
}
