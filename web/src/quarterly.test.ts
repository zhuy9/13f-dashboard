import { describe, expect, it } from 'vitest'
import { issueText, windowLabel } from './quarterly'
import type { QuarterlyAi, QuarterlyIssue } from './quarterlyTypes'

function issue(ai: Partial<QuarterlyAi> | null): QuarterlyIssue {
  return {
    period: '2026-09-30',
    prevPeriod: '2026-06-30',
    label: '2026 Q3',
    builtAt: '2026-11-18T03:00:00+00:00',
    datasetId: 'ds1',
    windows: { quarter: { start: '2026-07-01', end: '2026-09-30' }, since: { start: '2026-10-01', end: '2026-11-18' } },
    coverage: { filed: 40, total: 40, missing: [] },
    totals: { opened: 1, closed: 1, added: 1, trimmed: 1, unchanged: 1 },
    headline: 'Template headline',
    lede: 'Template lede.',
    sections: [],
    ai: ai && { model: 'm', generatedAt: 'g', factsHash: 'h', headline: null, lede: null, notes: {}, ...ai },
  }
}

describe('issueText', () => {
  it('uses the template when there is no AI text', () => {
    expect(issueText(issue(null))).toEqual({ headline: 'Template headline', lede: 'Template lede.', isAi: false })
  })

  it('takes each AI field that passed, and falls back per field', () => {
    expect(issueText(issue({ headline: 'AI headline' }))).toEqual({ headline: 'AI headline', lede: 'Template lede.', isAi: true })
    expect(issueText(issue({ notes: { bought: 'n' } })).isAi).toBe(false)
  })
})

describe('windowLabel', () => {
  it('drops the repeated year', () => {
    expect(windowLabel({ start: '2026-07-01', end: '2026-09-30' })).toBe('Filed Jul 1 – Sep 30, 2026')
    expect(windowLabel({ start: '2026-10-01', end: '2027-01-05' })).toBe('Filed Oct 1, 2026 – Jan 5, 2027')
  })
})
