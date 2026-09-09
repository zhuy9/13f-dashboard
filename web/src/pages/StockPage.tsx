import { lazy, Suspense, useEffect } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState } from '@/components/AsyncStates'
import { WatchButton } from '@/components/WatchButton'
import { CsvExport } from '@/components/CsvExport'
import { Explain } from '@/components/Explain'
import { SourceFilings } from '@/components/manager/SourceFilings'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useMeta } from '@/context/MetaContext'
import { KindBadge } from '@/components/KindBadge'
import { ManagerLink } from '@/components/ManagerLink'
import { HoldersTable } from '@/components/stock/HoldersTable'
import { MajorShareholders } from '@/components/stock/MajorShareholders'
import { OptionsGroups } from '@/components/stock/OptionsGroups'
import { StatTile } from '@/components/StatTile'
import { getOwnershipIssuer, getStock, getStockQuarter } from '@/data'
import { pct, quarterLabel } from '@/format'
import { useAsyncData } from '@/hooks/useAsyncData'
import { isUnresolvedSymbol } from '@/ownership'

const TrendCharts = lazy(() => import('@/components/stock/TrendCharts').then((m) => ({ default: m.TrendCharts })))

export function StockPage() {
  const { symbol: rawSymbol = '' } = useParams<{ symbol: string }>()
  const symbol = decodeURIComponent(rawSymbol)
  const { meta } = useMeta()
  const [params, setParams] = useSearchParams()
  const period = params.get('period') ?? meta?.latestPeriod ?? null
  useEffect(() => {
    if (period && !params.has('period')) setParams({ period }, { replace: true })
  }, [period, params, setParams])
  const quarterState = useAsyncData(() => period ? getStockQuarter(symbol, period) : Promise.resolve(null), [symbol, period])
  const stockState = useAsyncData(() => getStock(symbol), [symbol])
  const issuerState = useAsyncData(() => getOwnershipIssuer(symbol), [symbol])

  if (stockState.loading || issuerState.loading || quarterState.loading) return <LoadingState />

  const stock = stockState.data
  const issuer = issuerState.data

  // Most 13D/13G issuers are not held by any tracked 13F manager, so the 13F doc is often
  // absent while the ownership doc is there. Only give up when neither exists.
  if (!stock && !issuer) {
    const message = stockState.error ?? issuerState.error
    return message ? <ErrorState message={message} /> : <EmptyState message="Stock not found." />
  }

  // A dataset published before stock_quarters/ existed carries the newest quarter on the stock
  // doc instead. Without this the whole page reads "unavailable" until the next full ingest.
  const latest = quarterState.data ?? (stock?.latest?.period === period ? stock.latest : null)
  const name = stock?.name ?? issuer?.issuerName ?? symbol
  const sector = stock?.sector ?? issuer?.sector ?? 'Unknown'
  const unresolved = !stock && isUnresolvedSymbol(symbol)

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold">
            {unresolved ? (
              name
            ) : (
              <>
                {symbol} <span className="font-normal text-ink-muted">{name}</span>{' '}
                <KindBadge kind={stock?.kind ?? null} />
              </>
            )}
          </h1>
          {sector !== 'Unknown' && <p className="text-sm text-ink-muted">{sector}</p>}
          {unresolved && (
            <p className="mt-1 text-sm text-ink-muted">
              No ticker matched this filing ({symbol}). The company is usually delisted or acquired.
            </p>
          )}
        </div>
        {/* Controls grouped in their own column, matching the manager page: the quarter picker
            and the watch control are the two things you act on here. */}
        <div className="flex flex-col items-end gap-1">
          {period && meta && (
            <Select value={period} onValueChange={p => setParams({ period: p })}>
              <SelectTrigger aria-label="Stock quarter"><SelectValue /></SelectTrigger>
              <SelectContent>{meta.periods.map(p => <SelectItem key={p} value={p}>{quarterLabel(p)}</SelectItem>)}</SelectContent>
            </Select>
          )}
          {/* The 13D/G section below carries its own filing dates; this says what the quarter scopes. */}
          {period && <span className="text-xs text-ink-muted">13F holdings as of {quarterLabel(period)}</span>}
          {stock && <WatchButton kind="stock" id={symbol} label={symbol} />}
        </div>
      </header>
      {quarterState.error && <ErrorState message={quarterState.error} />}
      {stockState.error && <ErrorState message={stockState.error} />}

      {!quarterState.error && stock ? (
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
              <CsvExport rows={latest.holders} name={`${symbol}-holders`} accessions={latest.filings?.map(f => f.accession)} />
              <HoldersTable holders={latest.holders} />
              {/* Collapsed: one accession per holder is provenance, not something to read past on
                  the way down the page. Same native <details> as the Explain above the table. */}
              {latest.filings && latest.filings.length > 0 && (
                <div className="mt-4">
                  <Explain summary={`Source filings (${latest.filings.length})`}>
                    <SourceFilings filings={latest.filings} cik="" />
                  </Explain>
                </div>
              )}
            </section>

            {latest.soldOut.length > 0 && (
              <section>
                <h2 className="mb-2 text-lg font-medium">
                  Sold Out <span className="text-sm font-normal text-ink-muted">— weight held the quarter before</span>
                </h2>
                <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
                  {[...latest.soldOut]
                    .sort((a, b) => b.prevWeight - a.prevWeight)
                    .map((h) => (
                      <li key={h.cik}>
                        <ManagerLink cik={h.cik} label={h.short} />{' '}
                        <span className="font-tabular text-ink-muted">{pct(h.prevWeight)}</span>
                      </li>
                    ))}
                </ul>
              </section>
            )}

            {/* Only when options were actually reported. 13F options are filed under the
                underlying equity's CUSIP, so a note or warrant page can never have any -- the
                section would just repeat the Holders table above under the wrong heading
                ("Equity Long" for a convertible note). Equity pages with no options got the
                same duplicate. */}
            {latest.options.calls.length + latest.options.puts.length > 0 && (
              <section>
                <h2 className="mb-2 text-lg font-medium">Positions by Type</h2>
                <OptionsGroups
                  equityHolders={latest.holders}
                  calls={latest.options.calls}
                  puts={latest.options.puts}
                />
              </section>
            )}
          </>
        ) : (
          <EmptyState message="Holdings unavailable for this quarter. Select another quarter." />
        )
      ) : !stockState.error && !quarterState.error && (
        <p className="text-sm text-ink-muted">No tracked manager reported this stock in a 13F filing.</p>
      )}

      {issuer && <MajorShareholders issuer={issuer} />}

      {stock && (
        <section>
          <h2 className="mb-2 text-lg font-medium">Trend</h2>
          <Suspense fallback={<LoadingState />}>
            <TrendCharts trend={stock.trend} />
          </Suspense>
        </section>
      )}
    </div>
  )
}
