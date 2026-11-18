import { filedDate } from './format'
import type { DateRange, QuarterlyIssue } from './quarterlyTypes'

// The AI field wins only when it passed the ingest-side checks; anything it dropped is null.
export function issueText(issue: QuarterlyIssue): { headline: string; lede: string; isAi: boolean } {
  const ai = issue.ai
  return {
    headline: ai?.headline ?? issue.headline,
    lede: ai?.lede ?? issue.lede,
    isAi: Boolean(ai?.headline || ai?.lede),
  }
}

export function windowLabel({ start, end }: DateRange): string {
  const sameYear = start.slice(0, 4) === end.slice(0, 4)
  const from = sameYear
    ? new Date(`${start}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
    : filedDate(start)
  return `Filed ${from} – ${filedDate(end)}`
}
