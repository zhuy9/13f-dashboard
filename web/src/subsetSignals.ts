import type { ManagerQuarter, Position, Signals } from './types'

export interface SubsetQuarter { cik: string; quarter: ManagerQuarter }
type Row = Position & { cik: string }
const mean = (values: number[]) => values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
const names = (rows: Row[]) => [...new Set(rows.map(r => r.short))].sort()
const changes = (rows: Row[]) => rows.flatMap(r => r.status === 'NEW' ? [r.weight] : r.change == null ? [] : [r.change])
// Python/pandas round exact halves to even.
const round = (n: number) => n % 1 === 0.5 ? Math.floor(n) + Math.floor(n) % 2 : Math.round(n)

export function subsetSignals(published: Signals, inputs: SubsetQuarter[], latest: boolean, minimum?: number): Signals {
  if (!published.config) throw new Error('Filtering is available after the next full data refresh.')
  const cfg = { ...published.config, ...(minimum == null ? {} : { consensusMinManagers: minimum, highConvictionMinManagers: minimum }) }
  const rows: Row[] = inputs.flatMap(({ cik, quarter }) => quarter.positions.filter(p => p.kind === 'EQUITY').map(p => ({ ...p, cik })))
    .sort((a, b) => a.cik.localeCompare(b.cik) || a.symbol.localeCompare(b.symbol))
  const grouped = new Map<string, Row[]>()
  for (const row of rows) grouped.set(row.symbol, [...(grouped.get(row.symbol) ?? []), row])
  const stocks = [...grouped].sort(([a], [b]) => a.localeCompare(b)).map(([symbol, positions]) => {
    const holders = positions.filter(r => r.value > 0)
    const buys = holders.filter(r => r.status === 'NEW' || r.status === 'ADDED')
    const exits = positions.filter(r => r.status === 'TRIMMED' || r.status === 'SOLD_OUT')
    const qualifying = holders.filter(r => r.weight >= cfg.highConvictionMinWeight)
    const newCount = holders.filter(r => r.status === 'NEW').length
    const addedCount = holders.filter(r => r.status === 'ADDED').length
    const avgWeight = mean(holders.map(r => r.weight))
    const avgChange = mean(changes(holders))
    const c = cfg.score
    const raw = holders.length * (1 + avgWeight / c.weightScale) * (1 + newCount * c.newBonus) *
      (1 + addedCount * c.addedBonus) * Math.min(1 + Math.max(avgChange, 0) / c.accumulationScale, c.accumulationCap)
    return { symbol, name: positions[0].name, holders, buys, exits, qualifying, newCount, addedCount, avgWeight, avgChange, raw }
  })
  const scorePeak = Math.max(0, ...stocks.map(s => s.raw))
  const score = (raw: number) => scorePeak ? round(100 * raw / scorePeak) : 0
  const consensusBuys = stocks.filter(s => s.buys.length >= cfg.consensusMinManagers).map(s => ({
    symbol: s.symbol, name: s.name, newBuyers: s.newCount, added: s.addedCount, avgWeight: s.avgWeight,
    avgWeightIncrease: mean(changes(s.buys)), score: score(s.raw), raw: s.raw, scorePeak, managers: names(s.buys),
  })).sort((a, b) => b.score - a.score)
  const consensusExits = stocks.filter(s => s.exits.length >= cfg.consensusMinManagers).map(s => ({
    symbol: s.symbol, name: s.name, soldOut: s.exits.filter(r => r.status === 'SOLD_OUT').length,
    trimmed: s.exits.filter(r => r.status === 'TRIMMED').length, avgReduction: mean(changes(s.exits)), managers: names(s.exits),
  })).sort((a, b) => b.soldOut - a.soldOut || b.trimmed - a.trimmed)
  const highConviction = stocks.filter(s => s.qualifying.length >= cfg.highConvictionMinManagers).map(s => ({
    symbol: s.symbol, name: s.name, managers: s.qualifying.length, avgWeight: mean(s.qualifying.map(r => r.weight)),
    maxWeight: Math.max(...s.qualifying.map(r => r.weight)), new: s.newCount, added: s.addedCount, managerNames: names(s.qualifying),
  })).sort((a, b) => b.managers - a.managers || b.avgWeight - a.avgWeight)
  const position = (r: Row) => ({ cik: r.cik, short: r.short, symbol: r.symbol, name: r.name, weight: r.weight, value: r.value })
  const biggestNew = rows.filter(r => r.status === 'NEW').map(position).sort((a, b) => b.weight - a.weight).slice(0, cfg.topN)
  const biggestAdds = rows.filter(r => r.status === 'ADDED').map(r => ({ ...position(r), change: r.change! }))
    .sort((a, b) => b.change - a.change).slice(0, cfg.topN)
  const biggestTrims = rows.filter(r => r.status === 'TRIMMED' || r.status === 'SOLD_OUT').map(r => ({ ...position(r), change: r.change! }))
    .sort((a, b) => a.change - b.change).slice(0, cfg.topN)
  const topSignals = stocks.filter(s => s.holders.length >= cfg.consensusMinManagers).map(s => ({
    symbol: s.symbol, name: s.name, score: score(s.raw), raw: s.raw, scorePeak, managerCount: s.holders.length,
    avgWeight: s.avgWeight, avgChange: s.avgChange, newCount: s.newCount, addedCount: s.addedCount, managers: names(s.holders),
  })).sort((a, b) => b.score - a.score).slice(0, cfg.topN)

  const prior = inputs.flatMap(({ cik, quarter }) => (quarter.priorPositions ?? []).map(p => ({ ...p, cik })))
  const fastestGrowing = latest ? stocks.map(s => {
    const history = prior.filter(p => p.symbol === s.symbol)
    const period = history.map(p => p.period).sort().at(-1)
    const previous = new Set(history.filter(p => p.period === period && p.held).map(p => p.cik))
    const current = new Set(s.holders.map(h => h.cik))
    const newManagers = period ? [...current].filter(c => !previous.has(c)).length : 0
    const exitedManagers = period ? [...previous].filter(c => !current.has(c)).length : 0
    return { symbol: s.symbol, name: s.name, prevCount: previous.size, count: current.size, newManagers, exitedManagers, netChange: newManagers - exitedManagers }
  }).filter(r => r.netChange > 0).sort((a, b) => b.netChange - a.netChange).slice(0, cfg.topN) : []

  const sectors = inputs.flatMap(i => i.quarter.sectors).filter(s => s.change != null)
  const sectorRotation = [...new Set(sectors.map(s => s.sector))].sort().map(sector => {
    const selected = sectors.filter(s => s.sector === sector)
    return { sector, avgWeight: mean(selected.map(s => s.weight)), avgPrevWeight: mean(selected.map(s => s.prevWeight!)),
      avgChange: mean(selected.map(s => s.change!)), increasing: selected.filter(s => s.change! > cfg.sectorMoveThreshold).length,
      decreasing: selected.filter(s => s.change! < -cfg.sectorMoveThreshold).length }
  }).sort((a, b) => b.avgChange - a.avgChange)

  // Pairwise cosine similarity is unchanged by removing other managers.
  const selected = new Set(inputs.map(i => i.cik))
  const indexes = published.managerSimilarity.ciks.flatMap((c, i) => selected.has(c) ? [i] : [])
  const managerSimilarity = { ciks: indexes.map(i => published.managerSimilarity.ciks[i]),
    matrix: indexes.map(i => ({ values: indexes.map(j => published.managerSimilarity.matrix[i].values[j]) })) }
  const optionsExposure = published.optionsExposure.map(r => ({ symbol: r.symbol,
    equityHolders: r.equityHolders.filter(c => selected.has(c)), callHolders: r.callHolders.filter(c => selected.has(c)),
    putHolders: r.putHolders.filter(c => selected.has(c)),
  })).filter(r => r.callHolders.length || r.putHolders.length)
  return { config: cfg, filings: inputs.flatMap(i => i.quarter.filings ?? []), consensusBuys, consensusExits, highConviction,
    biggestNew, biggestAdds, biggestTrims, topSignals, fastestGrowing, sectorRotation, managerSimilarity, optionsExposure }
}
