import { doc, getDoc } from 'firebase/firestore'
import { db } from './firebase'
import type { Manager, ManagerQuarter, Meta, Signals, Stock } from './types'

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
  return fetchDoc<Stock>(`stocks/${symbol}`)
}

export function getSignals(period: string): Promise<Signals | null> {
  return fetchDoc<Signals>(`signals/${period}`)
}
