function GithubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 19 19" aria-hidden="true">
      <use href="/icons.svg#github-icon" />
    </svg>
  )
}

export function Footer() {
  return (
    <footer className="mt-12 border-t border-line bg-paper">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-ink-muted">
        <div className="flex flex-col gap-1">
          <span className="font-medium text-ink">Consensus Sheet</span>
          <span>Signals derived from public SEC 13F filings.</span>
          <span>Not investment advice. Positions are reported up to 45 days after quarter-end.</span>
        </div>
        <span
          className="flex cursor-not-allowed items-center gap-1.5 opacity-50"
          title="Repo is private for now"
        >
          <GithubIcon />
          GitHub
        </span>
      </div>
    </footer>
  )
}
