# Methodology

What every number on the site means, and what it does not cover. This file is the stable
reference. `docs/PLAN.md` is implementation history; read this one for definitions.

Last reviewed: 2026-09-08.

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

`weight` is a position's reported value over the manager's reported total. Both the total and
the equity-only subtotal are stored, so a weight can be reconciled against the filing.

**Open limitation (Milestone 10):** the denominator currently includes option rows. For a
manager with a large option book, equity weights therefore read lower than the equity-only
figure, and are not directly comparable to a manager who reports no options. Milestone 10
switches the denominator to equity only and stamps a methodology version on the published data.

Weight is a share of the *reported* portfolio. It is not a share of the manager's assets.
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

**Open limitation (Milestone 11):** share counts are compared as reported, with no adjustment
for stock splits. A 2-for-1 split doubles the share count with no trade behind it, and currently
reads as `ADDED`. A reverse split reads as `TRIMMED`. Weight is unaffected, because it is
relative.

**Open limitation (Milestone 11):** `13F-HR/A` amendments are ignored. A manager that corrects
or completes a filing by amendment is represented by its original filing only.

## Conviction Score

A 0-100 number per (quarter, stock). It combines how many tracked managers hold the stock, their
average weight in it, how many opened or added to it, and their average weight change. The
constants are in `ingest/signals_config.json` under `score`.

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

- Weight denominator includes option rows (Milestone 10).
- No stock-split adjustment (Milestone 11).
- No `13F-HR/A` amendment handling (Milestone 11).
- Conviction Score is relative within a quarter only.
- Ownership feed capped at 300 events; the 7-day count is anchored to the newest filing, not to
  now (Milestone 12).
- Sectors come from SEC SIC codes, not GICS.
- Pre-2024-12-18 13D/13G filings are text, not structured XML, and are skipped.
- 13G coverage is roster-only.
