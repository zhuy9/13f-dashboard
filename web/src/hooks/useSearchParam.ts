import { useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

/** The `?period=...` suffix to carry the selected quarter across an in-app link, or '' when none. */
export function usePeriodSearch(): string {
  const [params] = useSearchParams()
  const period = params.get('period')
  return period ? `?${new URLSearchParams({ period })}` : ''
}

/** Set one search param, leaving the rest of the query string alone. */
export function useSetSearchParam() {
  const [, setParams] = useSearchParams()
  // Stable identity: callers list it in useEffect deps.
  return useCallback((key: string, value: string | null, replace = false) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value == null) next.delete(key)
      else next.set(key, value)
      return next
    }, { replace })
  }, [setParams])
}

/** The `?filter=` and `?q=` a feed page is narrowed by. */
export function useFeedFilter() {
  const [params] = useSearchParams()
  return { filter: params.get('filter') ?? 'all', query: params.get('q') ?? '' }
}

/** `?period=`, written into the URL (replacing history) as `fallback` once that is known, so
 * a reload or a shared link keeps the quarter. Returns the period and a setter for it. */
export function usePeriodParam(fallback: string | null | undefined): [string | null, (period: string) => void] {
  const [params] = useSearchParams()
  const setParam = useSetSearchParam()
  const urlPeriod = params.get('period')
  useEffect(() => {
    if (!urlPeriod && fallback) setParam('period', fallback, true)
  }, [urlPeriod, fallback, setParam])
  return [urlPeriod ?? fallback ?? null, useCallback((period: string) => setParam('period', period), [setParam])]
}
