import { useEffect, useState } from 'react'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useAsyncData<T>(fetcher: () => Promise<T | null>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T> & { deps: unknown[] }>({ data: null, loading: true, error: null, deps })

  useEffect(() => {
    let cancelled = false
    setState({ data: null, loading: true, error: null, deps })
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null, deps })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Failed to load data.'
          setState({ data: null, loading: false, error: message, deps })
        }
      })
    return () => {
      cancelled = true
    }
    // deps drive refetch; fetcher is expected to be stable/recreated alongside deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  // Hide the previous scope immediately, before the new effect runs.
  return deps.length !== state.deps.length || deps.some((d, i) => !Object.is(d, state.deps[i]))
    ? { data: null, loading: true, error: null } : state
}
