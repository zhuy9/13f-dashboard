# Methodology

What every number on the site means, and what it does not cover. This file is the stable
reference for definitions and limits.

- Using or self-hosting the site: [README.md](../README.md).
- How it was built, and what is still outstanding: [PLAN.md](PLAN.md).
- Diagrams of the system and the pipeline: [ARCHITECTURE.md](ARCHITECTURE.md).

Last reviewed: 2026-09-09. Methodology version: **2** (`methodology_version` in
`ingest/signals_config.json`, published as `meta/latest.methodologyVersion` and shown in the
site footer). Version 1 divided portfolio weights by the filing total including option rows.

## Sources

| Data | Form | Cadence | Lag |
|---|---|---|---|
| Holdings | 13F-HR | Quarterly | Up to 45 days after quarter end |
| Ownership stakes | Schedule 13D / 13G and their amendments | Event-driven | 2 to 5 business days for 13D; 13G varies by filer category |
| Insider transactions | Form 4 / 4-A | Event-driven | 2 business days |

Both come from SEC EDGAR. Nothing here is real time. A 13F tells you what a manager held on
the last day of a quarter, not what it holds today, and not when during the quarter it traded.

## The tracked universe

Signals cover the managers in `ingest/funds.json` and nobody else. "Consensus" means consensus
among that list. It is a hand-picked roster, not a market-wide measure, and adding or removing a
manager changes every count and average on the site.

13D filings are collected from every filer on EDGAR. 13G filings are collected only from the
tracked roster, because the universe-wide 13G stream is dominated by index funds.

Insider transactions are collected only for issuers held by at least one tracked manager at the
most recent 13F quarter. Universe-wide Form 4 is not fetchable on this budget (roughly 500
filings a day, against 30-50 for the whole 13D/13G family combined). This universe **moves** each
quarter: a stock every manager sold drops out of new fetching, but transactions already on file
for it are kept and still shown.

## Custom manager/style subsets

Patterns can restrict the research universe to selected managers. Counts, averages, rankings,
and score normalization are recomputed within that universe, using the published methodology
and thresholds. The minimum-manager control overrides both consensus and high-conviction count
thresholds; the qualifying portfolio-weight threshold stays unchanged. The selection and minimum
are encoded in the URL and CSV exports. Each manager's own equity weights remain unchanged.
Default views use Python's precomputed tables; custom subsets use browser aggregation verified
against the same Python fixtures. Stock and manager drill-downs show their full reported holdings.

## Portfolio weight

A 13F reports positions in equities, and also option positions, convertible notes, and warrants.
An option row is reported under the underlying stock's CUSIP, and its value is the value of the
underlying shares, not the premium paid. It is not invested capital and it is not
delta-adjusted exposure, so it is never treated as either.

`weight` is a position's reported value over the manager's **equity value**: the sum of its
common-equity rows only. Option rows, convertible notes, and warrants are excluded from that
denominator. So the eligible-equity weights of one manager-quarter sum to 100%.

Both figures are published. `totalValue` is the filing total over every row, which is what
reconciles against the filing itself. `equityValue` is the denominator above. The manager page
shows them as "Reported Total" and "Equity Value", and they differ for any manager reporting
options, notes, or warrants.

ETFs and funds count as equity and stay in the denominator. A manager holding half its book in
SPY really is half invested in equities. Convertible notes are debt and warrants are not the
share, so both stay out of it — but they remain in the holdings table, badged by kind, so they
are still inspectable.

A manager reporting no eligible equity at all has no weight, not a weight of zero. A zero
denominator is an unanswerable question, not zero conviction.

Weight is a share of the *reported equity* portfolio. It is not a share of the manager's assets.
Anything a 13F does not cover — cash, bonds, foreign listings, private holdings, short positions
— is invisible here. For an endowment, most of the real portfolio is invisible.

## Position status

`NEW`, `ADDED`, `TRIMMED`, `UNCHANGED`, `SOLD_OUT` compare **share counts** between two
consecutive quarters. Weight change compares **portfolio weights**.

The two can point in opposite directions, and that is not an error. A manager can add 5% more
shares while the position's weight falls, because the rest of the book grew faster, or because
the stock fell while others rose. Read status as "did they trade it" and weight change as "did
it get more important".

A manager that did not file the previous quarter gets `status = null`, not `NEW`. Missing data
is never rendered as zero.

Share counts are compared on a consistent basis. Splits are recorded in
`ingest/corporate_actions.json`, one entry per action with the source it came from, and the
prior quarter's count is restated onto the current share basis before status is decided. Both
counts are published: `prevShares` as filed, `adjPrevShares` adjusted. Weight was never
affected, because it is relative.

Splits are never inferred. A share count that looks like a split is not evidence that one
happened, so a clean multiple with no recorded action is flagged (`UNADJUSTED?` in the UI) and
nothing is adjusted. The flag looks at value as well as shares: a split leaves a position's
value alone because the price divides by the same number, while a purchase moves both.

`13F-HR/A` amendments are processed by type. A `RESTATEMENT` re-files the whole report and
replaces the filing it corrects. A `NEW HOLDINGS` amendment adds only positions that were
previously confidential and is unioned with the original. An amendment whose cover page states
no type is skipped and reported in the run log, never guessed at.

A holding first disclosed by an amendment is labelled `AMENDED`. That says how it came to
light, not when it was bought — such a position was usually held all along under a
confidential-treatment request. Filing disclosure never establishes a trade date.

## Provenance

Every manager-quarter names the filings its numbers came from: accession, a link to the filing
on EDGAR, the date it was filed, and whether it was an original or an amendment. Each position
also carries the accession that reported it, so a holding can be traced to a specific filing
when a book was split across several.

A firm that files one book under more than one CIK has the filing CIK recorded separately from
the roster CIK, because that filing is otherwise not findable on EDGAR under the manager's own
number.

## Conviction Score

A 0-100 number per (quarter, stock). It combines how many tracked managers hold the stock, their
average weight in it, how many opened or added to it, and their average weight change. The
constants are in `ingest/signals_config.json` under `score`.

The exact factors, with a worked example, are in
`ingest/test_derive.py::test_conviction_score_components_are_reproducible_by_hand`:

```
raw = manager_count
      x (1 + avg_weight / weight_scale)
      x (1 + new_count * new_bonus)
      x (1 + added_count * added_bonus)
      x min(max(avg_change, 0) / accumulation_scale + 1, accumulation_cap)
```

`avg_change` is the mean weight change across current holders, where a NEW position counts as
its full weight because it came from zero. The score is then rescaled per quarter. Both `raw` and the quarter's `scorePeak` are published,
so a displayed score can be checked: `score = round(100 * raw / scorePeak)`.

Two things it is not:

1. **Not a probability, rating, or forecast.** It has no units.
2. **Not comparable across quarters.** The raw score is rescaled so that the highest-scoring
   stock in each quarter is 100. A stock scoring 80 in two quarters means "80% of that quarter's
   top score" twice, and those two top scores can be very different.

## Ownership events

Derived per (investor, company) pair by comparing each filing to that pair's previous filing in
our log. No previous filing means `event = null`, never `NEW`.

`EXITED` is stored, but the site shows it as **Below 5%**, because that is all it means: the
reported stake fell under the 5% threshold. The investor may still hold nearly 5%. Once under
the threshold they stop filing, so we cannot see whether they later sold the rest.

`total_percent` and `total_shares` are the maximum across the reporting persons on a filing,
never a sum. Nested entities in one filing all report the same aggregate stake.

The 13F holder count shown beside an ownership event comes from the most recent 13F quarter. It
is always older than the filing next to it. Zero means no tracked manager held it as of that
quarter. A dash means the 13F pipeline has not run yet.

Headline counts are computed in the pipeline over every event on file, not in the browser over
the visible feed, and each one carries the window and scope it was counted over. The feed below
them is still the newest 300 events; the counts are not limited to it.

## Insider transactions (Form 4)

Every transaction line on a Form 4 or 4/A carries an SEC transaction code. The code, not
edgartools' own "Transaction Type" label (which mislabels code `A` as a purchase), decides how a
line is classified:

| Code | Shown as | Notes |
|---|---|---|
| `P` | Bought | The only real open-market purchase. |
| `S` | Sold | Split into Planned and Discretionary below. |
| `A` | Awarded | A grant. **Never a purchase** — the insider paid nothing for it. |
| `M`, `X` | Exercised | An option exercise. **Never a purchase.** |
| `F` | Tax Withholding | Shares withheld to pay tax on a vesting event. **Never a sale.** |
| `G` | Gift | **Never a sale.** |
| `C` | Conversion | Converting one security into another. |
| `D` | Disposed to Issuer | An open-market-style disposition back to the issuer. |
| Anything else | Other | `J K L U V W Z I E H O` — none of these have their own meaning here. |

**A sale splits three ways, and the three are never summed into one "insider selling" number:**
- **Planned** — the filing's Rule 10b5-1 checkbox is checked. The trade was scheduled in advance,
  often months earlier, and says little about the insider's view today.
- **Discretionary** — the checkbox is explicitly unchecked.
- **Not stated** — the filing predates or omits the checkbox. This is not the same as
  discretionary; it means the filing simply does not say.

**First buy in window** flags an owner's first open-market purchase of an issuer within the
lookback period. It reads `null`, not `false`, when the data on file does not reach back far
enough to know for certain — the same rule as a `null` position status in the 13F table: absence
of evidence is not evidence.

**Cluster buying**: three or more distinct insiders buying the same stock within the same
window. A single insider buying is noise more often than not; this is the one insider signal
with real published support, which is why it is called out separately.

**Insiders buying a tracked name**: symbols with recent open-market buying that are also held by
at least one tracked 13F manager — a statement neither pipeline can make alone.

The 13F holder count shown beside an insider trade works exactly like the one beside an
ownership event: from the most recent 13F quarter, always older than the transaction next to it,
and a dash means the 13F pipeline has not run yet.

## Dollar values

Values are dollars for filings from 2023 onward. Older filings reported thousands, and a few
filers kept reporting thousands after the change. That distorts dollar figures for those
filers. It does not distort weights, which are relative.

## Freshness

The monthly 13F ingest is idempotent and re-runs the last quarters, which is how late filers get
picked up. The ownership pipeline runs daily. They are independent: one can be stale while the
other is current.

## Standing limitations, in one list

- Split adjustment covers only the actions recorded in `ingest/corporate_actions.json`; a
  split nobody has added there is flagged, not corrected.
- Conviction Score is relative within a quarter only.
- The ownership event feed shows the newest 300 events. Headline counts cover every event, but
  paging back through older ones is not built yet (Milestone 16B).
- Form 4 covers only Section 16 insiders (officers, directors, 10% owners) of issuers currently
  in the insider universe, not every employee and not every issuer. It is not a complete picture
  of who at a company is trading, and a stock that no tracked manager holds is never fetched.
- Sectors come from SEC SIC codes, not GICS. SIC 7389 ("Services-Business Services, NEC") is a
  catch-all mapped to Financials because the payment networks dominate it among S&P 500 names;
  that is wrong for other issuers in the same code, such as Uber, Alibaba, Etsy and Trip.com.
  See `ingest/sectors.py`, which names the trade-off.
- A holding whose issuer has deregistered — taken private or acquired — is sectored from the
  older `ticker.txt` list, which keeps such companies after `company_tickers.json` drops them.
  Anything that resolves to no SIC at all still reads Unknown.
- Pre-2024-12-18 13D/13G filings are text, not structured XML, and are skipped.
- 13G coverage is roster-only.
