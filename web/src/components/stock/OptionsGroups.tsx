import { Link } from 'react-router-dom'
import { SideBadge } from '@/components/SideBadge'
import { CALL_COLOR, PUT_COLOR } from '@/format'
import type { Holder, OptionHolderRef } from '@/types'

function ManagerLinkList({ items }: { items: { cik: string; short: string }[] }) {
  if (items.length === 0) {
    return <p className="px-2 py-1 text-sm text-ink-muted">None.</p>
  }
  return (
    <ul className="flex flex-col gap-1 px-2 py-1 text-sm">
      {items.map((m) => (
        <li key={m.cik}>
          <Link to={`/manager/${m.cik}`} className="text-call hover:underline">
            {m.short}
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function OptionsGroups({
  equityHolders,
  calls,
  puts,
}: {
  equityHolders: Holder[]
  calls: OptionHolderRef[]
  puts: OptionHolderRef[]
}) {
  return (
    <div className="flex flex-col gap-2">
      <details className="rounded border border-line">
        <summary className="cursor-pointer px-2 py-1.5 text-sm font-medium">
          Equity Long ({equityHolders.length})
        </summary>
        <ManagerLinkList items={equityHolders} />
      </details>
      <details className="rounded border border-line">
        <summary className="cursor-pointer px-2 py-1.5 text-sm font-medium" style={{ color: CALL_COLOR }}>
          <SideBadge side="CALL" /> ({calls.length})
        </summary>
        <ManagerLinkList items={calls} />
      </details>
      <details className="rounded border border-line">
        <summary className="cursor-pointer px-2 py-1.5 text-sm font-medium" style={{ color: PUT_COLOR }}>
          <SideBadge side="PUT" /> ({puts.length})
        </summary>
        <ManagerLinkList items={puts} />
      </details>
    </div>
  )
}
