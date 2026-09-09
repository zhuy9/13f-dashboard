import { useState } from 'react'
import { Loader2, Star } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useMeta } from '@/context/MetaContext'
import { useWatchlist } from '@/hooks/useWatchlist'
import type { WatchKind } from '@/watchlist'

export function WatchButton({ kind, id, label }: { kind: WatchKind; id: string; label: string }) {
  const { meta } = useMeta()
  const { state, add, remove } = useWatchlist()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const saved = state.items.some((i) => i.kind === kind && i.id === id)
  const message = error || state.error

  async function toggle() {
    if (!meta) return
    setBusy(true)
    setError('')
    try {
      if (saved) remove(kind, id)
      else await add(kind, id, label, meta)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save this name.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <Button
        variant={saved ? 'secondary' : 'outline'}
        size="sm"
        // The label below changes on hover, so the accessible name has to state the action
        // outright rather than leaving a screen reader to read "Watching" and guess.
        aria-label={saved ? `Remove ${label} from your watchlist` : `Add ${label} to your watchlist`}
        aria-busy={busy}
        disabled={busy || !meta}
        onClick={toggle}
        className="group"
      >
        {busy ? <Loader2 className="animate-spin" /> : <Star className={saved ? 'fill-current text-call' : ''} />}
        <span aria-hidden>
          {busy ? (
            'Saving…'
          ) : saved ? (
            // A saved control that still reads "Watching" on hover does not say what clicking does.
            <>
              <span className="group-hover:hidden">Watching</span>
              <span className="hidden group-hover:inline">Remove</span>
            </>
          ) : (
            'Watch this name'
          )}
        </span>
      </Button>
      {message && (
        <p role="status" className="text-sm text-put">
          {message}
        </p>
      )}
    </div>
  )
}
