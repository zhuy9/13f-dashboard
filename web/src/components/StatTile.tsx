export function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-line px-4 py-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="font-tabular text-xl font-semibold">{value}</div>
    </div>
  )
}
