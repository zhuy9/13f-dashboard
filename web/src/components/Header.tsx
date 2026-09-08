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
      {/* Wraps and can shrink: the title plus three nav links need about 400 px in a row,
          more than the ~343 px a 375 px phone leaves after padding. Without this the group
          could not give way, and an unshrinkable element widens the whole document. Verified
          by rendering the deployed page inside a 375 px iframe: title, nav and search each
          take their own line and nothing is clipped. */}
      <div className="flex min-w-0 flex-wrap items-center gap-x-6 gap-y-1">
        <span className="text-lg font-semibold">Consensus Sheet</span>
        <nav className="flex flex-wrap gap-4">
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
