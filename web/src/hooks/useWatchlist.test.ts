import { beforeEach, expect, it, vi } from 'vitest'
import type { Meta } from '@/types'

const mocks = vi.hoisted(() => ({
  getManagerQuarter: vi.fn(),
  getStockQuarter: vi.fn(),
}))
vi.mock('@/data', () => mocks)

const PERIOD = '2026-06-30'
const meta = { latestPeriod: PERIOD, methodologyVersion: 2 } as Meta
const quarter = {
  period: PERIOD,
  newCount: 1,
  addedCount: 2,
  trimmedCount: 3,
  soldOutCount: 4,
  holders: [{ cik: '1111111111', short: 'M1', weight: 0.1 }],
  filings: [{ accession: 'a-1', url: 'https://www.sec.gov/a-1' }],
}

beforeEach(() => {
  vi.resetAllMocks()
  mocks.getStockQuarter.mockResolvedValue(null)
})

it('reads a stock report from the stock-quarter document', async () => {
  const { readReport } = await import('@/hooks/useWatchlist')
  mocks.getStockQuarter.mockResolvedValue(quarter)

  const report = await readReport('stock', 'AMZN', 'AMZN', meta)

  expect(report.report.summary).toBe('1 new · 2 added · 3 trimmed · 4 sold out')
  expect(report.report.sources).toEqual(['https://www.sec.gov/a-1'])
})

it('reports nothing to watch when the quarter has no document', async () => {
  const { readReport } = await import('@/hooks/useWatchlist')

  await expect(readReport('stock', 'NONE', 'NONE', meta)).rejects.toThrow('No current report for NONE.')
})
