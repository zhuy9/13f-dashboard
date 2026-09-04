import { doc, getDoc } from 'firebase/firestore'
import { db } from './firebase'
import type { Manager, ManagerQuarter, Meta, Signals, Stock } from './types'
import type { OwnershipFeed, OwnershipInvestor, OwnershipIssuer } from './ownershipTypes'

// The Firestore SDK retries a bad project/network config indefinitely and never rejects
// getDoc() on its own, so a wrong VITE_FIREBASE_PROJECT_ID would otherwise hang forever
// on "Loading...". This bounds every read so a config error surfaces as a visible message.
const FETCH_TIMEOUT_MS = 10_000

function withTimeout<T>(promise: Promise<T>, path: string): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(
        () => reject(new Error(`Timed out loading ${path}. Check your Firebase configuration.`)),
        FETCH_TIMEOUT_MS,
      ),
    ),
  ])
}

async function fetchDoc<T>(path: string): Promise<T | null> {
  const snap = await withTimeout(getDoc(doc(db, path)), path)
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
