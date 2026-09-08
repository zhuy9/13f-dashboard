import type { ReactNode } from 'react'

// One card shell for every tile on the site. `detail` and `href` exist because the Patterns
// entry cards are the same card with a second line and a link -- they had grown their own copy
// of these classes, which is how two tiles start drifting apart.
export function StatTile({
  label,
  value,
  detail,
  href,
}: {
  label: string
  value: ReactNode
  detail?: string
  href?: string
}) {
  const body = (
    <>
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="truncate font-tabular text-xl font-semibold">{value}</div>
      {detail && <div className="truncate text-xs text-ink-muted">{detail}</div>}
    </>
  )
  const shell = 'min-w-0 rounded border border-line px-4 py-3'
  return href ? (
    <a href={href} className={`${shell} block hover:border-ink-muted`}>
      {body}
    </a>
  ) : (
    <div className={shell}>{body}</div>
  )
}
