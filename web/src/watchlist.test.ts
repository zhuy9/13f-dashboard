import { expect, it } from 'vitest'
import { reconcile, type Watched, type WatchState } from './watchlist'

const item: Watched = { kind: 'stock', id: 'AAA', label: 'AAA', report: {
  period: '2026-03-31', methodologyVersion: 2, fingerprint: 'original', summary: '2 added', sources: ['https://example.test/filing'],
} }
const baseline: WatchState = { version: 1, items: [item], events: [] }
it('starts from a baseline, deduplicates reruns and keeps unavailable reports unchanged', () => {
  expect(reconcile(baseline, [item]).events).toEqual([])
  const next = { ...item, report: { ...item.report, period: '2026-06-30', fingerprint: 'new' } }
  const first = reconcile(baseline, [next])
  expect(first.events[0].change).toBe('New quarterly report')
  expect(reconcile(first, [next])).toEqual(first)
  expect(reconcile(first, [])).toEqual(first)
})
it('labels revisions and methodology recalculations separately from a new report', () => {
  const revision = { ...item, report: { ...item.report, fingerprint: 'corrected' } }
  expect(reconcile(baseline, [revision]).events[0].change).toBe('Revised quarterly report')
  const recalc = { ...revision, report: { ...revision.report, methodologyVersion: 3 } }
  expect(reconcile(baseline, [recalc]).events[0].change).toBe('Methodology recalculation')
})
