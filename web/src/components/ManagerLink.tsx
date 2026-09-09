import { Link, useSearchParams } from 'react-router-dom'

export function ManagerLink({ cik, label, className }: { cik: string; label: string; className?: string }) {
  const [params] = useSearchParams()
  const period = params.get('period')
  const search = period ? `?${new URLSearchParams({ period })}` : ''
  return (
    <Link to={`/manager/${cik}${search}`} className={className ?? 'text-call hover:underline'}>
      {label}
    </Link>
  )
}
