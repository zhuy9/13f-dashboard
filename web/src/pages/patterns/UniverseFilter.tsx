import { useSearchParams } from 'react-router-dom'
import { RotateCcw, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useSetSearchParam } from '@/hooks/useSearchParam'
import type { ManagerRef } from '@/types'

export function UniverseFilter({ managers, selected, minimum }: { managers: ManagerRef[]; selected: string[]; minimum: number }) {
  const [params, setParams] = useSearchParams()
  const setParam = useSetSearchParam()
  const select = (ciks: string[]) => setParam('managers', [...new Set(ciks)].sort().join(','))
  const chosen = new Set(selected)
  const styles = [...new Set(managers.map((m) => m.cluster))].sort()
  const membersOf = (cluster: string) => managers.filter((m) => m.cluster === cluster)
  const ordered = [...managers].sort((a, b) => a.cluster.localeCompare(b.cluster) || a.short.localeCompare(b.short))
  // The style control used to reset to its placeholder after every pick, so it reflected nothing.
  // Naming the style whose members are exactly the current selection makes it read as state.
  const activeStyle = styles.find((c) => {
    const members = membersOf(c)
    return members.length === selected.length && members.every((m) => chosen.has(m.cik))
  })
  const isEveryManager = selected.length === managers.length

  return (
    <details className="rounded border border-line">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 p-3 font-medium hover:bg-muted">
        Research universe
        <Badge variant="secondary" className="font-tabular">
          {isEveryManager ? 'All' : selected.length} of {managers.length}
        </Badge>
        {activeStyle && <Badge variant="outline">{activeStyle}</Badge>}
        <Badge variant="outline" className="font-tabular">
          min {minimum}
        </Badge>
      </summary>

      <div className="border-t border-line p-3">
        <p className="mb-3 text-sm text-ink-muted">
          All tables below use this universe. Stock and manager links open their full reported holdings.
        </p>

        <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button
            variant="outline"
            size="sm"
            disabled={isEveryManager && !params.has('min')}
            onClick={() => {
              const next = new URLSearchParams(params)
              next.delete('managers')
              next.delete('min')
              setParams(next)
            }}
          >
            <RotateCcw />
            All managers
          </Button>
          <Button variant="ghost" size="sm" disabled={selected.length === 0} onClick={() => select([])}>
            <X />
            Clear selection
          </Button>

          <label className="flex items-center gap-2 text-sm">
            Style
            <Select value={activeStyle ?? ''} onValueChange={(style) => select(membersOf(style).map((m) => m.cik))}>
              <SelectTrigger size="sm" aria-label="Choose style">
                <SelectValue placeholder="Custom selection" />
              </SelectTrigger>
              <SelectContent>
                {styles.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c} ({membersOf(c).length})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>

          <label className="flex items-center gap-2 text-sm" htmlFor="universe-minimum">
            Minimum managers
            <Input
              id="universe-minimum"
              className="w-16 font-tabular"
              type="number"
              min="1"
              value={minimum}
              onChange={(e) => setParam('min', e.target.value)}
            />
          </label>
        </div>

        {/* Sorted by style, but listed flat with the style as a per-row label. Style headings
            packed badly: cluster sizes run from 1 to 8, so in a grid every row grew as tall as
            its tallest group and left holes. CSS columns flow top-to-bottom before wrapping, so
            a style's managers stay adjacent and the list packs with no gaps. */}
        <fieldset className="columns-1 gap-x-6 sm:columns-2 lg:columns-3">
          <legend className="sr-only">Managers in the research universe</legend>
          {ordered.map((m) => (
            <div key={m.cik} className="flex break-inside-avoid items-center gap-2 py-0.5">
              <Checkbox
                id={`universe-${m.cik}`}
                checked={chosen.has(m.cik)}
                onCheckedChange={(on) => select(on ? [...selected, m.cik] : selected.filter((c) => c !== m.cik))}
              />
              <label
                htmlFor={`universe-${m.cik}`}
                className="flex min-w-0 flex-1 cursor-pointer items-baseline justify-between gap-2 text-sm"
              >
                <span className="truncate">{m.short}</span>
                <span className="truncate text-xs text-ink-muted">{m.cluster}</span>
              </label>
            </div>
          ))}
        </fieldset>
      </div>
    </details>
  )
}
