import { useId, type ReactNode } from 'react'

// Native <details> for the block that sits above a table. It is keyboard accessible and
// screen-reader navigable for free, works without JavaScript, and needs no component we are
// not already allowed to use.
export function Explain({ summary = 'How to read this', children }: { summary?: string; children: ReactNode }) {
  return (
    <details className="mb-2 text-sm text-ink-muted">
      <summary className="cursor-pointer text-ink-muted underline decoration-dotted hover:text-ink">{summary}</summary>
      <div className="mt-1 flex flex-col gap-1 border-l-2 border-line pl-3">{children}</div>
    </details>
  )
}

// Inside a table cell, <details> was the wrong control: the panel it opens is laid out in the
// cell, so it overlapped the next column and was clipped by the table's own overflow-x-auto,
// which makes overflow-y auto as well. The native popover API puts the panel in the browser's
// top layer instead, where no ancestor's overflow or z-index can reach it.
//
// Chosen over a hover tooltip, which would be unreachable by keyboard and on touch. A popover
// gets Escape, light dismiss and focus handling from the platform, with no JavaScript here.
export function InfoPopover({ label, heading, children }: { label: ReactNode; heading: string; children: ReactNode }) {
  const id = useId()
  return (
    <>
      <button
        type="button"
        popoverTarget={id}
        aria-label={heading}
        className="cursor-pointer font-tabular underline decoration-dotted hover:text-ink"
      >
        {label}
      </button>
      <div
        id={id}
        popover="auto"
        // whitespace-normal and text-left are resets, not decoration: the panel renders in the
        // top layer but still inherits computed style from the cell it is declared in, and
        // TableCell sets whitespace-nowrap -- so without this a long manager list runs off the
        // panel in a single line, which is the bug this replaced.
        className="max-w-xs rounded border border-line bg-paper p-3 text-left text-sm font-normal whitespace-normal shadow-lg"
      >
        <div className="mb-1 font-medium text-ink">{heading}</div>
        <div className="text-ink-muted">{children}</div>
      </div>
    </>
  )
}

// The managers behind one ranked row. A consensus row that cannot show its own evidence is
// only an assertion, so the count doubles as the control that reveals them.
export function ManagerList({ names, label, heading }: { names?: string[]; label?: string; heading: string }) {
  // An absent list is not an empty one: documents published before this field existed carry no
  // names, and claiming "no managers" there would be a fact invented from a missing field.
  if (!names) return <span className="font-tabular">{label ?? '—'}</span>
  if (names.length === 0) return <span className="text-ink-muted">—</span>
  return (
    <InfoPopover label={label ?? names.length} heading={heading}>
      {names.join(', ')}
    </InfoPopover>
  )
}
