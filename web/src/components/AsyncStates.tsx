export function LoadingState() {
  return <p className="p-8 text-center text-ink-muted">Loading…</p>
}

export function ErrorState({ message }: { message: string }) {
  return (
    <p role="alert" className="p-8 text-center text-status-soldout">
      {message}
    </p>
  )
}

export function EmptyState({ message }: { message: string }) {
  return <p className="p-8 text-center text-ink-muted">{message}</p>
}
