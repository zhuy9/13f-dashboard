import { useEffect, useState } from 'react'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useAsyncData<T>(fetcher: () => Promise<T | null>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    setState({ data: null, loading: true, error: null })
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Failed to load data.'
          setState({ data: null, loading: false, error: message })
        }
      })
    return () => {
      cancelled = true
    }
    // deps drive refetch; fetcher is expected to be stable/recreated alongside deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}
