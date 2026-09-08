// firestore/lite: one HTTP request per read, no realtime channel, no offline cache. The site
// only ever calls getDoc, and lite rejects a bad config instead of retrying it forever -- which
// is what the timeout race here used to exist to work around.
import { doc, getDoc } from 'firebase/firestore/lite'
import { db } from './firebase'
import type { Manager, ManagerQuarter, Meta, Signals, Stock } from './types'
import type { OwnershipFeed, OwnershipInvestor, OwnershipIssuer } from './ownershipTypes'

async function fetchDoc<T>(path: string): Promise<T | null> {
  const snap = await getDoc(doc(db, path))
  return snap.exists() ? (snap.data() as T) : null
}

export function getMeta(): Promise<Meta | null> {
  return fetchDoc<Meta>('meta/latest')
}

export function getManager(cik: string): Promise<Manager | null> {
  return fetchDoc<Manager>(`managers/${cik}`)
}

export function getManagerQuarter(cik: string, period: string): Promise<ManagerQuarter | null> {
  return fetchDoc<ManagerQuarter>(`manager_quarters/${cik}_${period}`)
}

export function getStock(symbol: string): Promise<Stock | null> {
  // encodeURIComponent matches store.py's quote() so a ticker with a "/" (e.g. SPAC
  // units "ABC/U") resolves to one Firestore path segment instead of splitting in two.
  return fetchDoc<Stock>(`stocks/${encodeURIComponent(symbol)}`)
}

export function getSignals(period: string): Promise<Signals | null> {
  return fetchDoc<Signals>(`signals/${period}`)
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
