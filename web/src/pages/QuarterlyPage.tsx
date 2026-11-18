import { Link, useNavigate, useParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { Explain } from '@/components/Explain'
import { QuarterSelect } from '@/components/QuarterSelect'
import { StatTile } from '@/components/StatTile'
import { getQuarterlyIndex, getQuarterlyIssue } from '@/data'
import { filedDate } from '@/format'
import { useAsyncData } from '@/hooks/useAsyncData'
import { issueText } from '@/quarterly'
import type { QuarterlyIssue } from '@/quarterlyTypes'
import { IssueSectionBlock } from './quarterly/IssueSectionBlock'

export function QuarterlyPage() {
  const { period } = useParams()
  const indexState = useAsyncData(getQuarterlyIndex, [])
  // A deep link reads its issue in parallel with the index; /quarterly waits for the newest period.
  const wanted = period ?? indexState.data?.issues[0]?.period ?? null
  const issueState = useAsyncData(() => (wanted ? getQuarterlyIssue(wanted) : Promise.resolve(null)), [wanted])

  if (indexState.loading || issueState.loading) return <LoadingState />
  if (indexState.error) return <ErrorState message={indexState.error} />
  if (issueState.error) return <ErrorState message={issueState.error} />
  const issues = indexState.data?.issues ?? []
  if (issues.length === 0) return <EmptyState message="No issue yet." />
  if (!issueState.data) {
    return (
      <div className="p-8 text-center text-ink-muted">
        <p>No issue for this quarter.</p>
        <Link to="/quarterly" className="text-call hover:underline">
          Read the latest issue
        </Link>
      </div>
    )
  }
  return <Issue issue={issueState.data} periods={issues.map((i) => i.period)} />
}

function Issue({ issue, periods }: { issue: QuarterlyIssue; periods: string[] }) {
  const navigate = useNavigate()
  const { headline, lede, isAi } = issueText(issue)
  const { coverage, totals } = issue

  return (
    <article className="mx-auto flex max-w-6xl flex-col gap-8 p-4">
      <header className="flex flex-col gap-3 border-b-2 border-ink pb-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ink-muted">The Quarterly</p>
            <h1 className="font-tabular text-5xl font-semibold tracking-tight sm:text-6xl">{issue.label}</h1>
          </div>
          <div className="w-36">
            <QuarterSelect periods={periods} value={issue.period} onChange={(p) => navigate(`/quarterly/${p}`)} />
          </div>
        </div>
        <p className="text-sm text-ink-muted">
          Quarter ended {filedDate(issue.period)} · {coverage.filed} of {coverage.total} managers filed · built{' '}
          {filedDate(issue.builtAt.slice(0, 10))}
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="max-w-4xl text-2xl font-semibold leading-tight sm:text-3xl">{headline}</h2>
        <p className="max-w-3xl text-base leading-relaxed">{lede}</p>
        {isAi && (
          <p className="text-xs text-ink-muted">AI-written summary · checked against the numbers below · not investment advice</p>
        )}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Positions opened" value={totals.opened.toLocaleString()} />
          <StatTile label="Positions closed" value={totals.closed.toLocaleString()} />
          <StatTile label="Added to" value={totals.added.toLocaleString()} />
          <StatTile label="Trimmed" value={totals.trimmed.toLocaleString()} />
        </div>
        <Explain>
          <p>
            <strong>Net buyers.</strong> For each stock, managers who opened or added a position, minus those who trimmed
            or sold out, by share count. A near-tie goes under "Where they disagree" instead. "Contested" means at least
            three managers were on the other side.
          </p>
          <p>
            <strong>Filing dates.</strong> 13D/13G and insider sections count what was filed during the quarter and what
            was filed since it ended. "No data" means our filing log does not reach back that far; it does not mean none.
          </p>
        </Explain>
      </section>

      <div className="grid grid-cols-1 gap-x-8 gap-y-10 lg:grid-cols-2">
        {issue.sections.map((s, i) => (
          <IssueSectionBlock key={s.id} section={s} number={i + 1} note={issue.ai?.notes[s.id] ?? null} windows={issue.windows} />
        ))}
      </div>
    </article>
  )
}
