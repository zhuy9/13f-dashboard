export type WatchKind = 'stock' | 'manager'
export interface ReportSnapshot {
  period: string
  methodologyVersion: number
  fingerprint: string
  summary: string
  sources: string[]
}
export interface Watched {
  kind: WatchKind
  id: string
  label: string
  report: ReportSnapshot
}
export interface WatchEvent extends Watched {
  change: 'New quarterly report' | 'Revised quarterly report' | 'Methodology recalculation'
}

export interface WatchState {
  version: 1
  items: Watched[]
  events: WatchEvent[]
  error?: string
}

/** Identifies one reported change, for dedupe and as a render key. */
export const eventId = (e: Watched) => `${e.kind}:${e.id}:${e.report.fingerprint}`

export function reconcile(state: WatchState, reports: Watched[]): WatchState {
  const events = [...state.events]
  const items = state.items.map(item => {
    const next = reports.find(r => r.kind === item.kind && r.id === item.id)
    if (!next || next.report.period < item.report.period || next.report.methodologyVersion < item.report.methodologyVersion) return item
    if (next.report.fingerprint === item.report.fingerprint) return item
    const change = next.report.methodologyVersion !== item.report.methodologyVersion ? 'Methodology recalculation'
      : next.report.period !== item.report.period ? 'New quarterly report' : 'Revised quarterly report'
    if (!events.some(e => eventId(e) === eventId(next))) events.unshift({ ...next, change })
    return next
  })
  return { ...state, items, events }
}
