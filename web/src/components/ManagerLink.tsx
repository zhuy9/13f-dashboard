import { Link } from 'react-router-dom'
import { usePeriodSearch } from '@/hooks/useSearchParam'

export function ManagerLink({ cik, label, className }: { cik: string; label: string; className?: string }) {
  const search = usePeriodSearch()
  return (
    <Link to={`/manager/${cik}${search}`} className={className ?? 'text-call hover:underline'}>
      {label}
    </Link>
  )
}
