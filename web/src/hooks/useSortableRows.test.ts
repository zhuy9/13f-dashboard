import { describe, expect, it } from 'vitest'
import { compare } from './useSortableRows'

describe('compare', () => {
  it('keeps a missing value last whichever way the column is sorted', () => {
    const rows = [{ v: 2 }, { v: null }, { v: 1 }]
    for (const dir of ['asc', 'desc'] as const) {
      expect([...rows].sort((a, b) => compare(a.v, b.v, dir)).at(-1)?.v).toBeNull()
    }
  })
})
