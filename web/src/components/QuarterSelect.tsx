import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { quarterLabel } from '@/format'

export function QuarterSelect({ periods, value, onChange }: { periods: string[]; value: string | null; onChange: (period: string) => void }) {
  return (
    <Select value={value ?? undefined} onValueChange={onChange}>
      <SelectTrigger aria-label="Quarter">
        <SelectValue placeholder="Quarter" />
      </SelectTrigger>
      <SelectContent>
        {periods.map((p) => (
          <SelectItem key={p} value={p}>
            {quarterLabel(p)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
