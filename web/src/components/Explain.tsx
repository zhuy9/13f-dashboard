import type { ReactNode } from 'react'

// Native <details>, not a tooltip: it is keyboard accessible and screen-reader navigable for
// free, survives with JavaScript disabled, and needs no component we are not already allowed
// to use. A hover tooltip would also be unreachable on touch, which is where the narrow
// layout matters most.
export function Explain({ summary = 'How to read this', children }: { summary?: string; children: ReactNode }) {
  return (
    <details className="mb-2 text-sm text-ink-muted">
      <summary className="cursor-pointer text-ink-muted underline decoration-dotted hover:text-ink">{summary}</summary>
      <div className="mt-1 flex flex-col gap-1 border-l-2 border-line pl-3">{children}</div>
    </details>
  )
}

// The managers behind one ranked row. A consensus row that cannot show its own evidence is
// only an assertion, so the count doubles as the disclosure control.
export function ManagerList({ names, label }: { names?: string[]; label?: string }) {
  // An absent list is not an empty one: documents published before the field existed carry no
  // names, and claiming "no managers" there would be a fact invented from a missing field.
  if (!names) return <span className="font-tabular">{label ?? '—'}</span>
  if (names.length === 0) return <span className="text-ink-muted">—</span>
  return (
    <details className="inline-block">
      <summary className="cursor-pointer font-tabular underline decoration-dotted">{label ?? names.length}</summary>
      <div className="mt-1 max-w-xs text-xs font-normal text-ink-muted">{names.join(', ')}</div>
    </details>
  )
}
