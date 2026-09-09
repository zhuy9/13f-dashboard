import { Link } from 'react-router-dom'
import { usePeriodSearch } from '@/hooks/useSearchParam'

export function StockLink({ symbol, className }: { symbol: string; className?: string }) {
  const search = usePeriodSearch()
  return (
    <Link to={`/stock/${encodeURIComponent(symbol)}${search}`} className={className ?? 'font-tabular text-call hover:underline'}>
      {symbol}
    </Link>
  )
}
