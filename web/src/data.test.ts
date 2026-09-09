import { beforeEach, expect, it, vi } from 'vitest'

const reads: string[] = []
let fail = false
vi.mock('./firebase', () => ({ db: {} }))
vi.mock('firebase/firestore/lite', () => ({
  doc: (_db: unknown, path: string) => path,
  getDoc: async (path: string) => {
    reads.push(path)
    if (fail) throw new Error('Read failed')
    return { exists: () => true, data: () => path === 'meta/latest' ? { datasetId: 'complete' } : {} }
  },
}))

// resetModules gives each test a fresh module, so the session caches start empty.
beforeEach(() => {
  vi.resetModules()
  reads.length = 0
  fail = false
})

it('pins concurrent and subsequent 13F reads to one published dataset', async () => {
  const { getMeta, getStock, getManager, getSignals, getSymbols } = await import('./data')
  await Promise.all([getMeta(), getStock('ABC/U'), getManager('123')])
  await getSignals('2026-06-30')
  await getSymbols()
  expect(reads).toEqual([
    'meta/latest', 'datasets/complete/stocks/ABC%2FU', 'datasets/complete/managers/123',
    'datasets/complete/signals/2026-06-30', 'datasets/complete/meta/symbols',
  ])
})

it('reads each dataset document once, however often a filter re-reads it', async () => {
  const { getManagerQuarter } = await import('./data')
  await Promise.all([getManagerQuarter('123', '2026-06-30'), getManagerQuarter('123', '2026-06-30')])
  await getManagerQuarter('123', '2026-06-30')
  await getManagerQuarter('123', '2026-03-31')

  expect(reads).toEqual([
    'meta/latest',
    'datasets/complete/manager_quarters/123_2026-06-30',
    'datasets/complete/manager_quarters/123_2026-03-31',
  ])
})

// Documents are immutable within a dataset, but a failure is not a document: caching the
// rejection would make one network blip permanent for the rest of the session.
it('retries after a failed read instead of replaying the failure', async () => {
  const { getManagerQuarter, getMeta } = await import('./data')
  await getMeta()

  fail = true
  await expect(getManagerQuarter('123', '2026-06-30')).rejects.toThrow('Read failed')

  fail = false
  await expect(getManagerQuarter('123', '2026-06-30')).resolves.toEqual({})
  expect(reads.filter((p) => p.endsWith('manager_quarters/123_2026-06-30'))).toHaveLength(2)
})

// The pinned snapshot must not pin a failure to read it: that would strand the whole session.
it('retries meta/latest after a failed read', async () => {
  const { getMeta } = await import('./data')
  fail = true
  await expect(getMeta()).rejects.toThrow('Read failed')

  fail = false
  await expect(getMeta()).resolves.toEqual({ datasetId: 'complete' })
  expect(reads).toEqual(['meta/latest', 'meta/latest'])
})

// ownership_* is rewritten in place by every ownership run, so it must not be cached.
it('does not cache the ownership documents that each run overwrites', async () => {
  const { getOwnershipFeed } = await import('./data')
  await getOwnershipFeed()
  await getOwnershipFeed()

  expect(reads).toEqual(['ownership/feed', 'ownership/feed'])
})
