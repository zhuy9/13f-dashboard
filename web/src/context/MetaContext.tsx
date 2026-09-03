import { createContext, useContext, type ReactNode } from 'react'
import { getMeta } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'
import type { Meta } from '@/types'

interface MetaState {
  meta: Meta | null
  loading: boolean
  error: string | null
}

const MetaContext = createContext<MetaState | null>(null)

export function MetaProvider({ children }: { children: ReactNode }) {
  const { data, loading, error } = useAsyncData(getMeta, [])
  return <MetaContext.Provider value={{ meta: data, loading, error }}>{children}</MetaContext.Provider>
}

export function useMeta(): MetaState {
  const ctx = useContext(MetaContext)
  if (!ctx) throw new Error('useMeta must be used within a MetaProvider')
  return ctx
}
