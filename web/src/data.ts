// firestore/lite: one HTTP request per read, no realtime channel, no offline cache. The site
// only ever calls getDoc, and lite rejects a bad config instead of retrying it forever -- which
// is what the timeout race here used to exist to work around.
import { doc, getDoc } from 'firebase/firestore/lite'
import { db } from './firebase'
import type { Manager, ManagerQuarter, Meta, Signals, Stock, StockLatest, SymbolIndex } from './types'
import type { OwnershipFeed, OwnershipInvestor, OwnershipIssuer } from './ownershipTypes'

async function fetchDoc<T>(path: string): Promise<T | null> {
  const snap = await getDoc(doc(db, path))
  return snap.exists() ? (snap.data() as T) : null
}

// Pin one published snapshot for this browser session, including concurrent page reads.
let metaPromise: Promise<Meta | null> | undefined
export function getMeta(): Promise<Meta | null> {
  // Same rule as the dataset cache below: pin the snapshot, never a failure to read it. A cached
  // rejection here would leave the whole session unable to load anything short of a reload.
  return metaPromise ??= fetchDoc<Meta>('meta/latest').catch((e: unknown) => {
    metaPromise = undefined
    throw e
  })
}

// Everything under a dataset id is immutable: a rerun publishes a new id and flips the pointer,
// so a resolved path can be cached for the session. Deliberately not on fetchDoc -- ownership/*
// is rewritten in place by every ownership run, and meta/latest is the pointer itself.
// ponytail: unbounded, but the data bounds it (~34 managers x 12 quarters); add eviction only if
// a session is ever expected to touch materially more than it does now.
const cached = new Map<string, Promise<unknown>>()

async function fetchDatasetDoc<T>(path: string): Promise<T | null> {
  const meta = await getMeta()
  const full = meta?.datasetId ? `datasets/${meta.datasetId}/${path}` : path
  if (!cached.has(full)) {
    // A cached rejection would be permanent, where an uncached read retries on the next render.
    cached.set(full, fetchDoc<T>(full).catch((e: unknown) => { cached.delete(full); throw e }))
  }
  return cached.get(full) as Promise<T | null>
}

export function getSymbols(): Promise<SymbolIndex | null> {
  return fetchDatasetDoc<SymbolIndex>('meta/symbols')
}

export function getManager(cik: string): Promise<Manager | null> {
  return fetchDatasetDoc<Manager>(`managers/${cik}`)
}

export function getManagerQuarter(cik: string, period: string): Promise<ManagerQuarter | null> {
  return fetchDatasetDoc<ManagerQuarter>(`manager_quarters/${cik}_${period}`)
}

export function getStock(symbol: string): Promise<Stock | null> {
  // encodeURIComponent matches store.py's quote() so a ticker with a "/" (e.g. SPAC
  // units "ABC/U") resolves to one Firestore path segment instead of splitting in two.
  return fetchDatasetDoc<Stock>(`stocks/${encodeURIComponent(symbol)}`)
}

export function getSignals(period: string): Promise<Signals | null> {
  return fetchDatasetDoc<Signals>(`signals/${period}`)
}

export function getOwnershipFeed(): Promise<OwnershipFeed | null> {
  return fetchDoc<OwnershipFeed>('ownership/feed')
}

export function getOwnershipIssuer(symbol: string): Promise<OwnershipIssuer | null> {
  return fetchDoc<OwnershipIssuer>(`ownership_issuers/${encodeURIComponent(symbol)}`)
}

export function getOwnershipInvestor(cik: string): Promise<OwnershipInvestor | null> {
  return fetchDoc<OwnershipInvestor>(`ownership_investors/${cik}`)
}

export function getStockQuarter(symbol: string, period: string): Promise<StockLatest | null> {
  return fetchDatasetDoc<StockLatest>(`stock_quarters/${encodeURIComponent(symbol)}_${period}`)
}
