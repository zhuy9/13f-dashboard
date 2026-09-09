import { useState } from 'react'
import { useMeta } from '@/context/MetaContext'
import { useWatchlist } from '@/hooks/useWatchlist'
import type { WatchKind } from '@/watchlist'

export function WatchButton({ kind, id, label }: { kind: WatchKind; id: string; label: string }) {
  const { meta } = useMeta()
  const { state, add, remove } = useWatchlist()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const saved = state.items.some(i => i.kind === kind && i.id === id)
  async function toggle() {
    if (!meta) return
    setBusy(true)
    setError('')
    try {
      if (saved) remove(kind, id)
      else await add(kind, id, label, meta)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save this name.') }
    finally { setBusy(false) }
  }
  return <div className="my-2 text-sm">
    <button className="text-call underline" disabled={busy || !meta} onClick={toggle}>{busy ? 'Saving…' : saved ? 'Remove from watchlist' : 'Watch this name'}</button>
    {(error || state.error) && <p role="status">{error || state.error}</p>}
  </div>
}
