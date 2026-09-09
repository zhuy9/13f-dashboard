import { useCallback } from 'react'
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
