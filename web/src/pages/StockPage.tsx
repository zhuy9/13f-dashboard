import { useParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { HoldersTable } from '@/components/stock/HoldersTable'
import { OptionsGroups } from '@/components/stock/OptionsGroups'
import { TrendCharts } from '@/components/stock/TrendCharts'
import { StatTile } from '@/components/StatTile'
import { getStock } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'

export function StockPage() {
  const { symbol = '' } = useParams<{ symbol: string }>()
  const stockState = useAsyncData(() => getStock(symbol), [symbol])

  if (stockState.loading) return <LoadingState />
  if (stockState.error) return <ErrorState message={stockState.error} />
  if (!stockState.data) return <EmptyState message="Stock not found." />

  const stock = stockState.data
  const { latest } = stock

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold">
          {stock.symbol} <span className="font-normal text-ink-muted">{stock.name}</span>
        </h1>
        <p className="text-sm text-ink-muted">{stock.sector}</p>
      </header>

      {latest ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatTile
              label="Managers Own"
              value={`${latest.managerCount} / ${latest.managersTotal}`}
            />
            <StatTile label="New" value={latest.newCount} />
            <StatTile label="Added" value={latest.addedCount} />
            <StatTile label="Trimmed" value={latest.trimmedCount} />
            <StatTile label="Sold Out" value={latest.soldOutCount} />
          </div>

          <section>
            <h2 className="mb-2 text-lg font-medium">Holders</h2>
            <HoldersTable holders={latest.holders} />
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium">Positions by Type</h2>
            <OptionsGroups
              equityHolders={latest.holders}
              calls={latest.options.calls}
              puts={latest.options.puts}
            />
          </section>
        </>
      ) : (
        <EmptyState message="No holders this quarter." />
      )}

      <section>
        <h2 className="mb-2 text-lg font-medium">Trend</h2>
        <TrendCharts trend={stock.trend} />
      </section>
    </div>
  )
}
