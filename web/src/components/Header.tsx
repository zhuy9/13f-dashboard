import { NavLink } from 'react-router-dom'
import { SymbolSearch } from '@/components/SymbolSearch'

const NAV_LINKS = [
  { to: '/patterns', label: 'Patterns' },
  { to: '/managers', label: 'Managers' },
  { to: '/ownership', label: 'Ownership' },
]

export function Header() {
  return (
    <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-4 border-b border-line bg-paper px-4 py-3">
      <div className="flex items-center gap-6">
        <span className="text-lg font-semibold">Consensus Sheet</span>
        <nav className="flex gap-4">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                isActive ? 'font-medium text-ink' : 'text-ink-muted hover:text-ink'
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <SymbolSearch />
    </header>
  )
}
