import { Link } from 'react-router-dom'

export function StockLink({ symbol, className }: { symbol: string; className?: string }) {
  return (
    <Link to={`/stock/${symbol}`} className={className ?? 'font-tabular text-call hover:underline'}>
      {symbol}
    </Link>
  )
}
