import { expect, it } from 'vitest'
import fixture from './fixtures/subset.json'
import { subsetSignals } from './subsetSignals'
import type { ManagerQuarter, Signals } from './types'

// Match floating-point arithmetic within tolerance; preserve table ordering.
const precise = (value: unknown): unknown => {
  if (typeof value === 'number') return Number(value.toFixed(10))
  if (Array.isArray(value)) return value.map(precise)
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, precise(v)]))
  return value
}
for (const test of fixture.cases) {
  it(`matches Python for ${test.ciks.length} selected managers: ${test.ciks}`, () => {
    const quarters = fixture.quarters as unknown as Record<string, ManagerQuarter>
    const rows = test.ciks.map(cik => ({ cik, quarter: quarters[`${cik}_${fixture.period}`] }))
    const result = subsetSignals(fixture.published as Signals, rows, true)
    expect(precise(result)).toEqual(precise(test.expected))
  })
}
it('shows no consensus for an empty or under-threshold universe', () => {
  expect(subsetSignals(fixture.published as Signals, [], true).consensusBuys).toEqual([])
  const quarter = Object.values(fixture.quarters).at(-1) as unknown as ManagerQuarter
  expect(subsetSignals(fixture.published as Signals, [{ cik: '3333333333', quarter }], true, 4).consensusBuys).toEqual([])
})
