import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useFeedFilter, useSetSearchParam } from '@/hooks/useSearchParam'

export function FeedFilters({ filters, placeholder }: { filters: { value: string; label: string }[]; placeholder: string }) {
  const { filter, query } = useFeedFilter()
  const setParam = useSetSearchParam()
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      {/* Wrap rather than scroll. overflow-x-auto forces overflow-y to auto too, so the
          horizontal scrollbar's own height produced a second, vertical one -- and a hidden
          scrollbar would leave the last filters unreachable without a shift-scroll. */}
      <Tabs value={filter} onValueChange={(value) => setParam('filter', value)} className="min-w-0">
        <TabsList className="flex-wrap group-data-horizontal/tabs:h-auto">
          {filters.map((f) => (
            <TabsTrigger key={f.value} value={f.value}>
              {f.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Input placeholder={placeholder} value={query} onChange={(e) => setParam('q', e.target.value || null)} className="sm:w-64" />
    </div>
  )
}
