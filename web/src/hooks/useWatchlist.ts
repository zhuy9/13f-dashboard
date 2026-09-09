import { useSyncExternalStore } from 'react'
import { getManagerQuarter, getStock, getStockQuarter } from '@/data'
import { reconcile, type Watched, type WatchKind, type WatchState } from '@/watchlist'
import type { Meta } from '@/types'

const key = 'consensus-watchlist-v1'
let current: WatchState = { version: 1, items: [], events: [] }
try {
  const saved: WatchState | null = JSON.parse(localStorage.getItem(key) ?? 'null')
  if (saved) {
    if (saved.version !== 1 || !Array.isArray(saved.items) || !Array.isArray(saved.events) ||
      ![...saved.items, ...saved.events].every(i => ['stock', 'manager'].includes(i.kind) && typeof i.id === 'string' &&
        typeof i.label === 'string' && typeof i.report?.fingerprint === 'string' && typeof i.report.period === 'string' &&
        typeof i.report.summary === 'string' && Number.isInteger(i.report.methodologyVersion) &&
        Array.isArray(i.report.sources) && i.report.sources.every(s => typeof s === 'string' && s.startsWith('https://')))) {
      throw new Error('Invalid saved watchlist')
    }
    if (!saved.events.every(e => typeof e.eventId === 'string' && ['New quarterly report', 'Revised quarterly report', 'Methodology recalculation'].includes(e.change))) throw new Error('Invalid saved digest')
    current = { version: 1, items: saved.items, events: saved.events }
  }
} catch {
  current.error = 'Saved watchlist unavailable. Changes will be kept for this session if storage is blocked.'
}

function update(next: WatchState) {
  current = next
  try {
    localStorage.setItem(key, JSON.stringify(next))
  } catch {
    current = { ...next, error: 'Browser storage unavailable. This watchlist lasts only for this session.' }
  }
  window.dispatchEvent(new Event(key))
}

async function readReport(kind: WatchKind, id: string, label: string, meta: Meta): Promise<Watched> {
  const period = meta.latestPeriod
  const data = kind === 'manager' ? await getManagerQuarter(id, period)
    : await getStockQuarter(id, period) ?? (await getStock(id))?.latest
  if (!data || ('period' in data && data.period !== period)) throw new Error(`No current report for ${label}.`)
  const sources = [...new Set(data.filings?.map(f => f.url) ?? [])].sort()
  const rows = 'positions' in data ? data.positions : data.holders
  const counts = 'counts' in data ? data.counts : { new: data.newCount, added: data.addedCount, trimmed: data.trimmedCount, soldOut: data.soldOutCount }
  const summary = `${counts.new} new · ${counts.added} added · ${counts.trimmed} trimmed · ${counts.soldOut} sold out`
  const content = JSON.stringify({ period, version: meta.methodologyVersion, sources, summary,
    rows: rows.map(r => JSON.stringify(Object.fromEntries(Object.entries(r).sort(([a], [b]) => a.localeCompare(b))))).sort() })
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(content))
  const fingerprint = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('')
  return { kind, id, label, report: { period, methodologyVersion: meta.methodologyVersion, fingerprint, summary, sources } }
}

function subscribe(listener: () => void) {
  window.addEventListener(key, listener)
  return () => window.removeEventListener(key, listener)
}

export function useWatchlist() {
  const state = useSyncExternalStore(subscribe, () => current)
  return {
    state,
    async add(kind: WatchKind, id: string, label: string, meta: Meta) {
      const item = await readReport(kind, id, label, meta)
      if (!current.items.some(i => i.kind === kind && i.id === id)) update({ ...current, items: [...current.items, item] })
    },
    remove(kind: WatchKind, id: string) {
      update({ ...current, items: current.items.filter(i => i.kind !== kind || i.id !== id) })
    },
    async check(meta: Meta) {
      const results = await Promise.allSettled(current.items.map(i => readReport(i.kind, i.id, i.label, meta)))
      const reports = results.flatMap(r => r.status === 'fulfilled' ? [r.value] : [])
      update(reconcile(current, reports))
      if (results.some(r => r.status === 'rejected')) throw new Error('Some reports could not be checked. Their saved baselines are unchanged.')
    },
  }
}
