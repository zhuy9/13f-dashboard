import { useMemo, useState } from 'react'

export type SortDirection = 'asc' | 'desc'

export function useSortableRows<T>(rows: T[], defaultKey: keyof T, defaultDirection: SortDirection = 'desc') {
  const [sortKey, setSortKey] = useState<keyof T>(defaultKey)
  const [direction, setDirection] = useState<SortDirection>(defaultDirection)

  const sorted = useMemo(() => {
    const copy = [...rows]
    copy.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
      return direction === 'asc' ? cmp : -cmp
    })
    return copy
  }, [rows, sortKey, direction])

  function toggleSort(key: keyof T) {
    if (key === sortKey) {
      setDirection((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setDirection('desc')
    }
  }

  return { sorted, sortKey, direction, toggleSort }
}
