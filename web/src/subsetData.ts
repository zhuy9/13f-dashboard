import { getManager, getManagerQuarter, getMeta, getSignals } from './data'
import { subsetSignals, type SubsetQuarter } from './subsetSignals'

export async function getSubsetSignals(period: string, selected: string[] | null, minimum?: number) {
  const published = await getSignals(period)
  if (!published || (selected == null && minimum == null)) return published
  const meta = await getMeta()
  if (!meta) throw new Error('No published dataset to filter.')
  if (minimum != null && (!Number.isInteger(minimum) || minimum < 1)) throw new Error('Minimum managers must be a positive integer.')
  const ciks = [...new Set(selected ?? meta.managers.map(m => m.cik))].sort()
  if (ciks.some(c => !meta.managers.some(m => m.cik === c))) throw new Error('The selected universe contains an unknown manager.')
  // fastestGrowing is the only reader of priorPositions, and it only runs on the latest quarter.
  const latest = period === meta.latestPeriod
  const inputs = await Promise.all(ciks.map(async (cik): Promise<SubsetQuarter | null> => {
    const quarter = await getManagerQuarter(cik, period)
    if (quarter) return { cik, quarter }
    // A manager that skipped this quarter still counts toward the earlier holder count, the same
    // as stock_trend's prev_holder_ciks in Python. Its last filing becomes history, not holdings.
    const manager = await getManager(cik)
    const previousPeriod = manager?.periods.filter(p => p < period).sort().at(-1)
    const previous = previousPeriod ? await getManagerQuarter(cik, previousPeriod) : null
    if (!previous || !previousPeriod) return null
    const held = previous.positions.filter(p => p.kind === 'EQUITY')
      .map(p => ({ symbol: p.symbol, period: previousPeriod, held: p.value > 0 }))
    // Later period wins per symbol, so its own holdings override the history it carries.
    const priorPositions = [...new Map([...previous.priorPositions, ...held].map(p => [p.symbol, p])).values()]
    return { cik, quarter: { ...previous, positions: [], sectors: [], filings: [], priorPositions } }
  }))
  return subsetSignals(published, inputs.flatMap(i => i ? [i] : []), latest, minimum)
}
