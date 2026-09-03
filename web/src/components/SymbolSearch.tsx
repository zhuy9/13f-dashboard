import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import type { SymbolRef } from '@/types'

export function SymbolSearch({ symbols }: { symbols: SymbolRef[] }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

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
    navigate(`/stock/${symbol}`)
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
