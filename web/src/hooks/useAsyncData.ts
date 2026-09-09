import { useEffect, useState } from 'react'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useAsyncData<T>(fetcher: () => Promise<T | null>, deps: unknown[]): AsyncState<T> {
  // Deps are primitives; String keeps NaN, null and undefined distinct where JSON would not.
  const scope = deps.map(String).join('|')
  const [state, setState] = useState<AsyncState<T> & { scope: string }>({ data: null, loading: true, error: null, scope })

  useEffect(() => {
    let cancelled = false
    setState({ data: null, loading: true, error: null, scope })
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null, scope })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Failed to load data.'
          setState({ data: null, loading: false, error: message, scope })
        }
      })
    return () => {
      cancelled = true
    }
    // deps drive refetch; fetcher is expected to be stable/recreated alongside deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  // Hide the previous scope immediately, before the new effect runs.
  return scope === state.scope ? state : { data: null, loading: true, error: null }
}
