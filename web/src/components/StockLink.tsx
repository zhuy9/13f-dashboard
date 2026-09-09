import { Link, useSearchParams } from 'react-router-dom'

export function StockLink({ symbol, className }: { symbol: string; className?: string }) {
  const [params] = useSearchParams()
  const period = params.get('period')
  const search = period ? `?${new URLSearchParams({ period })}` : ''
  return (
    <Link to={`/stock/${encodeURIComponent(symbol)}${search}`} className={className ?? 'font-tabular text-call hover:underline'}>
      {symbol}
    </Link>
  )
}
