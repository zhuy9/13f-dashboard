import { beforeEach, expect, it, vi } from 'vitest'
import fixture from './fixtures/subset.json'
import { getSubsetSignals } from './subsetData'

const mocks = vi.hoisted(() => ({ getSignals: vi.fn(), getMeta: vi.fn(), getManager: vi.fn(), getManagerQuarter: vi.fn() }))
vi.mock('./data', () => mocks)
beforeEach(() => {
  vi.resetAllMocks()
  mocks.getSignals.mockResolvedValue(fixture.published)
  mocks.getMeta.mockResolvedValue({ latestPeriod: fixture.period, managers: fixture.cases[0].ciks.map(cik => ({ cik })) })
  mocks.getManager.mockResolvedValue({ periods: ['2026-03-31'] })
  mocks.getManagerQuarter.mockImplementation(async (cik: string, period: string) => {
    if (cik === '1111111111' && period === fixture.period) return null
    return (fixture.quarters as Record<string, unknown>)[`${cik}_${period}`] ?? null
  })
})
it('keeps a missing current filer in the previous holder count', async () => {
  const result = await getSubsetSignals(fixture.period, fixture.cases[0].ciks)
  expect(result?.fastestGrowing.find(r => r.symbol === 'FFF')).toMatchObject({ prevCount: 1, count: 2, netChange: 1 })
  expect(mocks.getManagerQuarter).toHaveBeenCalledWith('1111111111', '2026-03-31')
})
it('fails visibly instead of treating a failed read as no holdings', async () => {
  mocks.getManagerQuarter.mockRejectedValue(new Error('Read failed'))
  await expect(getSubsetSignals(fixture.period, ['1111111111'])).rejects.toThrow('Read failed')
})
it('rejects invalid URL scopes and thresholds', async () => {
  await expect(getSubsetSignals(fixture.period, ['unknown'])).rejects.toThrow('unknown manager')
  await expect(getSubsetSignals(fixture.period, [], NaN)).rejects.toThrow('positive integer')
})
