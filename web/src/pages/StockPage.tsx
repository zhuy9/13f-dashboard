import { useParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { HoldersTable } from '@/components/stock/HoldersTable'
import { MajorShareholders } from '@/components/stock/MajorShareholders'
import { OptionsGroups } from '@/components/stock/OptionsGroups'
import { TrendCharts } from '@/components/stock/TrendCharts'
import { StatTile } from '@/components/StatTile'
import { getOwnershipIssuer, getStock } from '@/data'
import { useAsyncData } from '@/hooks/useAsyncData'
import { isUnresolvedSymbol } from '@/ownership'

export function StockPage() {
  const { symbol: rawSymbol = '' } = useParams<{ symbol: string }>()
  const symbol = decodeURIComponent(rawSymbol)
  const stockState = useAsyncData(() => getStock(symbol), [symbol])
  const issuerState = useAsyncData(() => getOwnershipIssuer(symbol), [symbol])

  if (stockState.loading || issuerState.loading) return <LoadingState />

  const stock = stockState.data
  const issuer = issuerState.data

  // Most 13D/13G issuers are not held by any tracked 13F manager, so the 13F doc is often
  // absent while the ownership doc is there. Only give up when neither exists.
  if (!stock && !issuer) {
    const message = stockState.error ?? issuerState.error
    return message ? <ErrorState message={message} /> : <EmptyState message="Stock not found." />
  }

  const latest = stock?.latest ?? null
  const name = stock?.name ?? issuer?.issuerName ?? symbol
  const sector = stock?.sector ?? issuer?.sector ?? 'Unknown'
  const unresolved = !stock && isUnresolvedSymbol(symbol)

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold">
          {unresolved ? (
            name
          ) : (
            <>
              {symbol} <span className="font-normal text-ink-muted">{name}</span>
            </>
          )}
        </h1>
        {sector !== 'Unknown' && <p className="text-sm text-ink-muted">{sector}</p>}
        {unresolved && (
          <p className="mt-1 text-sm text-ink-muted">
            No ticker matched this filing ({symbol}). The company is usually delisted or acquired.
          </p>
        )}
      </header>

      {stock ? (
        latest ? (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <StatTile label="Managers Own" value={`${latest.managerCount} / ${latest.managersTotal}`} />
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
        )
      ) : (
        <p className="text-sm text-ink-muted">No tracked manager reported this stock in a 13F filing.</p>
      )}

      {issuer && <MajorShareholders issuer={issuer} />}

      {stock && (
        <section>
          <h2 className="mb-2 text-lg font-medium">Trend</h2>
          <TrendCharts trend={stock.trend} />
        </section>
      )}
    </div>
  )
}
