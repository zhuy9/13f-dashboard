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
          <span>Signals derived from public SEC 13F and Schedule 13D/13G filings.</span>
          <span>Not investment advice. 13F positions are reported up to 45 days after quarter-end.</span>
        </div>
        <a
          href="https://github.com/zhuy9/13f-dashboard"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 hover:text-ink"
        >
          <GithubIcon />
          GitHub
        </a>
      </div>
    </footer>
  )
}
