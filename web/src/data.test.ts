import { expect, it, vi } from 'vitest'

const reads: string[] = []
vi.mock('./firebase', () => ({ db: {} }))
vi.mock('firebase/firestore/lite', () => ({
  doc: (_db: unknown, path: string) => path,
  getDoc: async (path: string) => {
    reads.push(path)
    return { exists: () => true, data: () => path === 'meta/latest' ? { datasetId: 'complete' } : {} }
  },
}))

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
