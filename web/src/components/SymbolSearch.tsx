import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import { getSymbols } from '@/data'
import type { SymbolIndex } from '@/types'

export function SymbolSearch() {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  // ~2,300 symbols in their own doc. Nobody who never opens the search box pays for it.
  const [symbols, setSymbols] = useState<SymbolIndex['symbols']>([])
  const navigate = useNavigate()
  const [params] = useSearchParams()

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return symbols
      .filter((s) => s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
      .slice(0, 8)
  }, [query, symbols])

  function goToSymbol(symbol: string) {
    setQuery('')
    setOpen(false)
    navigate(`/stock/${encodeURIComponent(symbol)}${params.has('period') ? `?${new URLSearchParams({ period: params.get('period')! })}` : ''}`)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && matches.length > 0) {
      goToSymbol(matches[0].symbol)
    }
    if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative w-56">
      <Input
        type="text"
        placeholder="Search symbol or name…"
        value={query}
        onFocus={() => symbols.length === 0 && void getSymbols().then((d) => setSymbols(d?.symbols ?? []))}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onKeyDown={handleKeyDown}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        aria-label="Search stocks"
      />
      {open && matches.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full rounded border border-line bg-paper shadow-md">
          {matches.map((s) => (
            <li key={s.symbol}>
              <button
                type="button"
                className="w-full px-3 py-2 text-left text-sm hover:bg-line/30"
                onMouseDown={() => goToSymbol(s.symbol)}
              >
                <span className="font-tabular font-medium">{s.symbol}</span>{' '}
                <span className="text-ink-muted">{s.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
