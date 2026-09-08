# Methodology

What every number on the site means, and what it does not cover. This file is the stable
reference. `docs/PLAN.md` is implementation history; read this one for definitions.

Last reviewed: 2026-09-08. Methodology version: **2** (`methodology_version` in
`ingest/signals_config.json`, published as `meta/latest.methodologyVersion` and shown in the
site footer). Version 1 divided portfolio weights by the filing total including option rows.

## Sources

| Data | Form | Cadence | Lag |
|---|---|---|---|
| Holdings | 13F-HR | Quarterly | Up to 45 days after quarter end |
| Ownership stakes | Schedule 13D / 13G and their amendments | Event-driven | 2 to 5 business days for 13D; 13G varies by filer category |

Both come from SEC EDGAR. Nothing here is real time. A 13F tells you what a manager held on
the last day of a quarter, not what it holds today, and not when during the quarter it traded.

## The tracked universe

Signals cover the managers in `ingest/funds.json` and nobody else. "Consensus" means consensus
among that list. It is a hand-picked roster, not a market-wide measure, and adding or removing a
manager changes every count and average on the site.

13D filings are collected from every filer on EDGAR. 13G filings are collected only from the
tracked roster, because the universe-wide 13G stream is dominated by index funds.

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
its full weight because it came from zero. The score is then rescaled per quarter.

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

**Open limitation (Milestone 12):** the "last 7 days" count on the Ownership page is measured
back from the newest filing in the feed, not from today, and the feed itself is capped at the
most recent 300 events.

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
- Ownership feed capped at 300 events; the 7-day count is anchored to the newest filing, not to
  now (Milestone 12).
- Sectors come from SEC SIC codes, not GICS.
- Pre-2024-12-18 13D/13G filings are text, not structured XML, and are skipped.
- 13G coverage is roster-only.
