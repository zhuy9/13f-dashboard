import { useSearchParams } from 'react-router-dom'
import type { ManagerRef } from '@/types'

export function UniverseFilter({ managers, selected, minimum }: { managers: ManagerRef[]; selected: string[]; minimum: number }) {
  const [params, setParams] = useSearchParams()
  function select(ciks: string[]) {
    const next = new URLSearchParams(params)
    next.set('managers', [...new Set(ciks)].sort().join(','))
    setParams(next)
  }
  return <details className="rounded border border-line p-3">
    <summary className="cursor-pointer font-medium">Research universe: {selected.length} managers · minimum {minimum}</summary>
    <p className="my-2 text-sm text-ink-muted">All tables below use this universe. Stock and manager links open their full reported holdings.</p>
    <div className="my-3 flex flex-wrap items-center gap-4">
      <button className="text-call underline" onClick={() => {
        const next = new URLSearchParams(params); next.delete('managers'); next.delete('min'); setParams(next)
      }}>All managers</button>
      <button className="text-call underline" onClick={() => select([])}>Clear selection</button>
      <label>Choose style <select aria-label="Choose style" className="border border-line p-1" value="" onChange={e => select(managers.filter(m => m.cluster === e.target.value).map(m => m.cik))}>
        <option value="" disabled>Select a style</option>
        {[...new Set(managers.map(m => m.cluster))].sort().map(c => <option key={c}>{c}</option>)}
      </select></label>
      <label>Minimum managers <input aria-label="Minimum managers" className="w-16 border border-line p-1" type="number" min="1" value={minimum} onChange={e => {
        const next = new URLSearchParams(params); next.set('min', e.target.value); setParams(next)
      }} /></label>
    </div>
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {managers.map(m => <label key={m.cik} className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={selected.includes(m.cik)} onChange={e => select(e.target.checked ? [...selected, m.cik] : selected.filter(c => c !== m.cik))} />
        {m.short}
      </label>)}
    </div>
  </details>
}
