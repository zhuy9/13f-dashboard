import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { TableHead } from '@/components/ui/table'
import type { SortDirection } from '@/hooks/useSortableRows'
import { cn } from '@/lib/utils'

interface SortableTableHeadProps<K extends string> {
  label: string
  sortKey: K
  activeKey: K
  direction: SortDirection
  onSort: (key: K) => void
  align?: 'left' | 'right'
}

export function SortableTableHead<K extends string>({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
  align = 'left',
}: SortableTableHeadProps<K>) {
  const isActive = sortKey === activeKey
  const Icon = isActive ? (direction === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown

  return (
    <TableHead className={align === 'right' ? 'text-right' : undefined}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          'inline-flex items-center gap-1 hover:text-ink',
          align === 'right' && 'flex-row-reverse',
          isActive ? 'font-semibold text-ink' : 'text-inherit',
        )}
      >
        {label}
        <Icon className={cn('size-3', !isActive && 'opacity-40')} />
      </button>
    </TableHead>
  )
}
