import { getManager, getManagerQuarter, getMeta, getSignals } from './data'
import { subsetSignals, type SubsetQuarter } from './subsetSignals'

export async function getSubsetSignals(period: string, selected: string[] | null, minimum?: number) {
  const published = await getSignals(period)
  if (!published || (selected == null && minimum == null)) return published
  const meta = await getMeta()
  if (!meta || !published.config) throw new Error('Filtering is available after the next full data refresh.')
  if (minimum != null && (!Number.isInteger(minimum) || minimum < 1)) throw new Error('Minimum managers must be a positive integer.')
  const ciks = [...new Set(selected ?? meta.managers.map(m => m.cik))].sort()
  if (ciks.some(c => !meta.managers.some(m => m.cik === c))) throw new Error('The selected universe contains an unknown manager.')
  const inputs = await Promise.all(ciks.map(async (cik): Promise<SubsetQuarter | null> => {
    const quarter = await getManagerQuarter(cik, period)
    if (quarter) {
      if (!quarter.priorPositions) throw new Error('Filtering history is unavailable in this dataset.')
      return { cik, quarter }
    }
    // A missing current filing still contributes to the earlier holder count.
    const manager = await getManager(cik)
    const previousPeriod = manager?.periods.filter(p => p < period).sort().at(-1)
    if (!previousPeriod) return null
    const previous = await getManagerQuarter(cik, previousPeriod)
    if (!previous) return null
    if (!previous.priorPositions) throw new Error('Filtering history is unavailable in this dataset.')
    const equity = previous.positions.filter(p => p.kind === 'EQUITY')
    const symbols = new Set(equity.map(p => p.symbol))
    return { cik, quarter: { ...previous, positions: [], sectors: [], filings: [], priorPositions: [
      ...previous.priorPositions.filter(p => !symbols.has(p.symbol)),
      ...equity.map(p => ({ symbol: p.symbol, period: previousPeriod, held: p.value > 0 })),
    ] } }
  }))
  return subsetSignals(published, inputs.flatMap(i => i ? [i] : []), period === meta.latestPeriod, minimum)
}
