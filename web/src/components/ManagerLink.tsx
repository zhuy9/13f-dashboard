import { Link } from 'react-router-dom'

export function ManagerLink({ cik, label, className }: { cik: string; label: string; className?: string }) {
  return (
    <Link to={`/manager/${cik}`} className={className ?? 'text-call hover:underline'}>
      {label}
    </Link>
  )
}
