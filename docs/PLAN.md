# Consensus Sheet — Implementation Plan (MVP)

> Planning + documentation: the planning model. Development: a cheaper model, one milestone at a time.
> This file is the single source of truth for the dev model.
> Every milestone has numbered tasks and a checkbox list of acceptance criteria (AC). A milestone is done only when every AC box is checked.

## Context

Build a public web dashboard of SEC Form 13F holdings for a tracked list of well-known conviction managers (see `ingest/funds.json`).
Beyond raw holdings, derive **signals** by aggregating the base dataset `Manager × Security × Quarter` in every direction:
manager → stocks, stock → managers, manager → sectors, quarter → quarter, manager → manager.

13F facts that shape the design:
- Long-only, quarterly, filed up to 45 days after quarter end. No shorts, no cash.
- Options ARE in the filing: each row has `putCall` (PUT / CALL / blank = shares). Options are listed under the **underlying's CUSIP**. Puts are never shown as "short"; they are "Reported Put Exposure".
- Rows carry CUSIP + issuer name only. **No ticker, no sector.** We enrich: CUSIP → ticker (OpenFIGI) → CIK + SIC (SEC) → sector (static map). This cached lookup is the "tiny sec master".
- Values are in **dollars** since 2023 (older: thousands). We load the last 4 quarters, all post-2023.
- Citadel and Millennium were **removed** by the user: their 13F is a market-making book and would poison every consensus signal.

Data changes 4×/year. So: **all derived tables are computed once at ingest in Python** and written as read-optimized Firestore docs. The browser only renders. No backend API, no always-on server, no auth.

## Decisions (locked, confirmed by user)

| Topic | Decision |
|---|---|
| Repo | One **public** GitHub repo, monorepo: `ingest/` + `web/` + `docs/`. Commits go **directly to `main`**. |
| Hosting | **Firebase Hosting** + user's custom domain. Not Vercel. |
| Serving data | **Firestore**: derived, read-optimized docs only (one read per page). Public-read rules. |
| File data | **Google Cloud Storage**: raw 13F XML + Parquet of the base table and every derived table. Blaze plan (billing on, $0 within free tier). Gated by `GCS_BUCKET`. |
| SQL | **No Cloud SQL.** BigQuery external tables over the Parquet later, if wanted. |
| Ingest | Python (3.12 in CI, 3.10 locally — no 3.11+-only syntax), `edgartools` + `pandas`, run by **GitHub Actions** (cron + manual). |
| Signals | All 13 signals computed in `ingest/derive.py`. Formulas and thresholds live in `ingest/signals_config.json`. The browser never computes a signal. |
| Managers | Tracked list lives in `ingest/funds.json`, all in the signal set. Cluster labels are manual. See "Adding a manager" in `CLAUDE.md` for the (code-free) process. |
| 13D/13G | Milestone 8: a sibling event pipeline (`ingest/ownership*.py`, daily cron). All `SCHEDULE 13D`/`13D/A` on EDGAR; `SCHEDULE 13G`/`13G/A` only from roster managers (CIK or `aliases`). Structured-XML filings only (from 2024-12-18). Contract in section J. |
| History | Last **4 quarters** per manager. QoQ status on quarters that have a prior quarter in the window. |
| Frontend | Vite + React + TS + **react-router-dom** + **Tailwind v4 + shadcn/ui** (5 components) + Recharts + Firebase JS. Pages: `/patterns`, `/managers`, `/manager/:cik`, `/stock/:symbol`; Milestone 8 adds `/ownership`, `/investor/:cik`. No auth. No per-user manager selection in MVP. |
| Agent docs | `CLAUDE.md` = agent instructions. `AGENTS.md` = symlink to it, recorded in git (real on Linux/GitHub; pointer file on Windows without the symlink privilege). `docs/PLAN.md` = this plan. |

## Architecture

```
GitHub Actions (monthly cron + manual; commits data/last_ingest.json so GitHub keeps the schedule enabled)
  └─ ingest/ingest.py
       ├─ fetch.py   : EDGAR ──► last 4 13F-HR per manager (edgartools) ──► normalized rows
       ├─ enrich.py  : CUSIP→ticker (OpenFIGI), ticker→CIK→SIC (SEC), SIC→sector (sectors.py); cached in Firestore securities/
       ├─ derive.py  : base table ──► manager_quarter_summary, manager_sector_exposure, stock_quarter_summary,
       │                            stock_trend, consensus tables, sector_rotation, similarity, options_exposure
       └─ store.py   : GCS (raw XML + Parquet) and Firestore (meta/, managers/, manager_quarters/, stocks/, signals/)

GitHub Actions (daily cron; Milestone 8)
  └─ ingest/ownership.py
       ├─ ownership_fetch.py  : EDGAR full-index ──► SCHEDULE 13D/13G (structured XML) ──► one row per filing
       ├─ enrich.py           : same securities/ cache (issuer CIK ──► ticker hint, OpenFIGI fallback)
       ├─ ownership_derive.py : filings ──► events (NEW / INCREASED / … per investor × issuer) ──► stakes
       └─ ownership_store.py  : GCS state (parquet/ownership_filings.parquet) + Firestore (ownership/, ownership_issuers/, ownership_investors/)

GitHub Actions (on push to main, paths web/**) ──► npm run build ──► Firebase Hosting ──► custom domain

Browser: one Firestore read per page (signals/{period}, manager_quarters/{cik}_{period}, stocks/{symbol}) + meta/latest once.
```

## Repo layout

```
13f/
  README.md  CLAUDE.md  AGENTS.md -> CLAUDE.md  LICENSE  .gitignore
  docs/PLAN.md  docs/ARCHITECTURE.md
  data/last_ingest.json          # written and committed by the ingest workflow
  firebase.json  .firebaserc  firestore.rules
  .github/workflows/ingest.yml  .github/workflows/deploy.yml  .github/workflows/ownership.yml
  ingest/
    requirements.txt  pyproject.toml  funds.json  signals_config.json  .env.example
    ingest.py         # CLI + orchestration only (13F)
    fetch.py          # edgartools fetch + normalize + edgar_ticker_hints
    enrich.py         # OpenFIGI + SEC lookups + securities cache
    api_constants.py  # external API URLs
    sectors.py        # SIC → sector
    derive.py         # all 13F derived tables (pure pandas, no I/O)
    store.py          # GCS + Firestore writes (13F)
    ownership.py           # CLI + orchestration (13D/13G, Milestone 8)
    ownership_fetch.py     # EDGAR index listing + structured 13D/13G parsing → one row per filing
    ownership_derive.py    # 13D/13G events, stakes, recent (pure pandas, no I/O)
    ownership_store.py     # GCS state parquet + Firestore ownership docs
    test_fetch.py  test_derive.py  test_sectors.py  test_store.py
    test_ownership_fetch.py  test_ownership_derive.py  test_ownership_store.py
    fixtures/holdings_small.csv  fixtures/ownership_small.csv  fixtures/ownership_13d.xml  fixtures/ownership_13g.xml
  web/
    package.json  vite.config.ts  tsconfig.json  tsconfig.app.json  index.html  components.json  .env.example
    src/
      main.tsx  App.tsx  index.css  firebase.ts  types.ts  format.ts  format.test.ts
      ownershipTypes.ts  ownership.ts  ownership.test.ts   # 13D/13G doc types + pure filter/label helpers
      data.ts                       # Firestore reads (one function per doc type)
      lib/utils.ts                  # shadcn cn()
      hooks/                        # useAsyncData, useSortableRows, useActiveSection
      context/MetaContext.tsx       # meta/latest fetched once, shared across pages
      components/ui/*               # shadcn-generated only: table, tabs, badge, input, select
      components/*                  # Header, Footer, SymbolSearch, StatusBadge, SideBadge, SectorBars,
                                     # Heatmap, StatTile, StockLink, ManagerLink, SortableTableHead, ...
      components/manager/*  components/stock/*  components/ownership/*   # page-specific sub-components
      pages/PatternsPage.tsx  ManagersPage.tsx  ManagerPage.tsx  StockPage.tsx  OwnershipPage.tsx  InvestorPage.tsx
      pages/patterns/*.tsx          # one small component per signal table
    public/                         # favicon.svg, icons.svg (sprite; only github-icon is used)
```

## Base dataset and derived tables (the contract for `derive.py`)

### Base table `holdings` (one row per manager × quarter × symbol × side)
```
cik, short, period (YYYY-MM-DD quarter end), filed_at, cusip, symbol, ticker|null, name, sector, cls,
value (int $), shares (int), put_call ("PUT"|"CALL"|null)
```
- `symbol` = `ticker` when known, else `"_" + cusip`. Used as the stock key and as the Firestore doc id.
- Duplicate (cik, period, cusip, put_call) rows are summed (13F splits positions across sub-managers).
- `total_value(cik, period)` = sum of `value` over all rows of that filing (equity + options), matching the 13F cover total.
- `periods` = sorted distinct periods in the window. `prev_period(p)` = the previous element; a manager with no filing at `prev_period` gets `prev_weight = null` and `status = null` for that quarter.
- Equity signals use `put_call is null` rows only. Options rows feed only `options_exposure`.

### A. `manager_quarter_summary` — per (cik, period, symbol), equity only
```
value, shares, weight = value / total_value
prev_value, prev_shares, prev_weight
change = weight - prev_weight            (percentage points; null when prev unknown)
status: NEW        prev absent, current present
        ADDED      shares > prev_shares
        TRIMMED    shares < prev_shares
        UNCHANGED  shares == prev_shares
        SOLD_OUT   prev present, current absent  (emit a row: value 0, weight 0, change = -prev_weight)
        null       no prior quarter for this manager in the window
```
Status uses **shares** (price moves change weight without a trade). `# ponytail: stock splits look like ADDED; split-adjust if it matters.`

### B. `manager_sector_exposure` — per (cik, period, sector)
`weight = sum(value in sector) / total_value`, `prev_weight`, `change`.

### C. `stock_quarter_summary` — per (period, symbol), equity only
```
manager_count, managers_total (managers with a filing this period), pct_holding = manager_count / managers_total
avg_weight, median_weight, max_weight (over current holders), total_value
new_count, added_count, trimmed_count, unchanged_count, sold_out_count
holders:  [{cik, short, value, shares, weight, prev_weight, change, status}]  sorted by weight desc
sold_out: [{cik, short, prev_weight}]
```

### D. `stock_trend` — per symbol, one row per period
`manager_count, avg_weight, median_weight, max_weight, new_managers, exited_managers, net_change`.

### E. Consensus tables — per period, from C (thresholds from `signals_config.json`)
| Table | Filter | Columns | Sort |
|---|---|---|---|
| `consensus_buys` | `new_count + added_count >= consensus_min_managers` | symbol, name, new_buyers, added, avg_weight, avg_weight_increase (mean `change` over NEW+ADDED), score | score desc |
| `consensus_exits` | `sold_out_count + trimmed_count >= consensus_min_managers` | symbol, name, sold_out, trimmed, avg_reduction (mean `change` over SOLD_OUT+TRIMMED) | sold_out desc, trimmed desc |
| `high_conviction` | holders with `weight >= high_conviction_min_weight` count `>= high_conviction_min_managers` | symbol, name, managers (that count), avg_weight, max_weight, new, added | managers desc, avg_weight desc |
| `biggest_new` | status NEW | cik, short, symbol, name, weight, value | weight desc, top 25 |
| `biggest_adds` | status ADDED | cik, short, symbol, name, weight, change, value | change desc, top 25 |
| `biggest_trims` | status TRIMMED or SOLD_OUT | cik, short, symbol, name, weight, change, value | change asc, top 25 |
| `fastest_growing` | from D, latest period, `net_change > 0` | symbol, name, prev_count, count, new_managers, exited_managers, net_change | net_change desc, top 25 |
| `top_signals` | all symbols with `manager_count >= consensus_min_managers` | symbol, name, score, manager_count, avg_weight, new_count, added_count | score desc, top 25 |

**Conviction score** (per period, symbol; constants from config, defaults shown):
```
raw = manager_count
    × (1 + avg_weight / weight_scale)                       # weight_scale = 0.05
    × (1 + new_count × new_bonus)                           # new_bonus = 0.5
    × (1 + added_count × added_bonus)                       # added_bonus = 0.25
    × min(1 + max(avg_change, 0) / accumulation_scale, accumulation_cap)   # 0.02, cap 3
score = round(100 × raw / max(raw over symbols this period))
```
`avg_change` = mean `change` over current holders (NEW counts as +weight). Sanity: 12 managers at 2.5% with no activity → raw 18; 4 managers at 9% with 3 new → raw ≈ 84. The concentrated, recent name ranks higher, as intended. `# ponytail: relative 0–100 within a quarter; not comparable across quarters.`

### F. `sector_rotation` — per (period, sector), from B
`avg_weight, avg_prev_weight, avg_change, increasing (managers with change > sector_move_threshold), decreasing (change < -threshold)`. Sort by avg_change desc.

### G. `manager_similarity` — per period
Vector per manager = equity weights by symbol. **Cosine similarity** matrix over managers with a filing that period. Also `most_similar[cik]` = top 5 others. `# ponytail: cosine only; Jaccard / sector similarity later.`

### H. `options_exposure` — per (period, symbol) with any option row
`equity_holders [cik], call_holders [cik], put_holders [cik]`.

### I. Clusters — per period, from `funds.json` labels
Per cluster: members, `common_holdings` (symbols held by ≥ half the members, top 10 by avg weight), `top_sector` (highest avg sector weight).

`ingest/signals_config.json`:
```json
{ "quarters": 4,
  "consensus_min_managers": 2,
  "high_conviction_min_weight": 0.03,
  "high_conviction_min_managers": 3,
  "sector_move_threshold": 0.005,
  "top_n": 25,
  "score": { "weight_scale": 0.05, "new_bonus": 0.5, "added_bonus": 0.25,
             "accumulation_scale": 0.02, "accumulation_cap": 3 },
  "ownership": { "start_date": "2024-12-18", "exit_below_pct": 5.0, "min_change_pp": 0.1,
                 "recent_events": 300, "purpose_max_chars": 400, "max_events_per_doc": 500,
                 "refetch_overlap_days": 3 } }
```

### J. Ownership (13D/13G) — the contract for `ownership_derive.py` (Milestone 8)

Schedule 13D/13G filings are event-driven, not quarterly: anyone crossing 5% of a company files within 5 business days (13D = intends to influence; 13G = passive) and amends on every material change. They are a second base table beside `holdings`, keyed by filing, not by quarter.

**Base table `ownership_filings`** — one row per accession; persisted as GCS `parquet/ownership_filings.parquet` (the pipeline state and the source of truth for every recompute).
```
accession (str "0001234567-26-001234"), form ("13D"|"13G"), is_amendment (bool), amendment_no (int|null),
filed_at (YYYY-MM-DD), event_date (YYYY-MM-DD|null),
filer_cik (10-digit str, from the XML header), reporting_ciks (list[str]; reporting persons that have a CIK),
investor_name (str), issuer_cik (10-digit str), issuer_name (str), cusip (str), ticker (str|null), symbol (str), sector (str),
shares (int|null), pct (float|null; percent of class, e.g. 7.4), purpose (str|null; 13D Item 4, truncated to purpose_max_chars),
prev_accession (str|null; from the XML header, display only), url (str)
```
- `symbol` = `ticker` when known, else `"_" + cusip` (same rule as `holdings`).
- `pct` / `shares` = edgartools `total_percent` / `total_shares` (max over reporting persons — nested entities each report the same aggregate, so a sum would double-count). `0.0` with zero reporting persons → `null`.
- A filing whose XML is not structured (`has_structured_data == False`, i.e. `xml()` returned nothing) is **not persisted**; it is retried while inside the `refetch_overlap_days` window. `# ponytail: after that it is lost; a --since rerun recovers it.`

**Derived `ownership_events`** — one row per filing row; pure function. Timeline key `(investor_cik, cusip)`, ordered by `(filed_at, amendment_no or 0, accession)`.
- `investor_cik` = the roster CIK when `filer_cik` or any of `reporting_ciks` is a roster CIK or alias (`funds.json` `aliases`), else `filer_cik`. For roster rows `investor_name`/`short`/`cluster` come from `funds.json`.
- Added columns: `event, prev_pct, change_pp, prev_accession_in_log, is_roster, is_activist, priority, short, cluster`.
- **Event rules, first match wins** (`prev` = the previous row on the same timeline, if any):
  1. no prev and not an amendment → `NEW`
  2. no prev and an amendment → `null` (the prior filing predates our log — unknown; same idea as `status = null` in A)
  3. `prev.pct` is null or `pct` is null → `null` (never infer an exit from missing data)
  4. `prev.pct < exit_below_pct` → `NEW` (re-entry after an exit)
  5. `pct < exit_below_pct` → `EXITED`
  6. `prev.form != form` → `SWITCHED_TO_13D` / `SWITCHED_TO_13G`
  7. `abs(pct − prev.pct) >= min_change_pp` → `INCREASED` / `DECREASED`
  8. otherwise → `UPDATED` (stake unchanged; the amendment changed Item 4 or an agreement — still shown)
- `change_pp = pct − prev.pct` (null if either is null). `is_activist = is_roster and "Activist" in cluster`.
- **Priority** (exactly this table): `HIGH` if (`form == "13D"` and event in {`NEW`, `SWITCHED_TO_13D`}) or (`is_activist` and event in {`NEW`, `INCREASED`, `SWITCHED_TO_13D`}); else `MEDIUM` if (`form == "13D"` and event in {`INCREASED`, `DECREASED`, `EXITED`}) or (`form == "13G"` and event == `NEW`) or (`form == "13D"` and event == `UPDATED` and `is_roster`); else `LOW`.
- Product signal names map onto these (the browser composes labels, Python stores the parts): NEW_MAJOR_HOLDER = `NEW`; NEW_13D = `NEW` and 13D; OWNERSHIP_INCREASE / DECREASE = `INCREASED` / `DECREASED`; MAJOR_HOLDER_EXIT = `EXITED`; KNOWN_ACTIVIST_ENTRY = `is_activist` and (`NEW` or `SWITCHED_TO_13D`).

**Derived `ownership_stakes`** — the latest event row per `(investor_cik, cusip)`; `is_current = pct is not null and pct >= exit_below_pct`.

**Derived `recent`** — the newest `recent_events` event rows by `(filed_at desc, accession desc)`.

Config keys (`signals_config.json` → `ownership`): `start_date` (first filing date ingested), `exit_below_pct`, `min_change_pp`, `recent_events`, `purpose_max_chars`, `max_events_per_doc`, `refetch_overlap_days`.

## Firestore documents (what the browser reads)

| Doc | Content | Read by |
|---|---|---|
| `meta/latest` | `latestPeriod, periods[], managers[{cik, short, name, cluster}], clusters[{label, members, commonHoldings, topSector}], symbols[{symbol, name, sector}], updatedAt` | every page, once |
| `managers/{cik}` | `cik, name, short, cluster, periods[]` | manager page |
| `manager_quarters/{cik}_{period}` | `filedAt, totalValue, count, counts{new,added,trimmed,unchanged,soldOut}, positions[A rows incl. SOLD_OUT], sectors[B rows], mostSimilar[{cik, short, score}]` | manager page |
| `stocks/{symbol}` | `symbol, name, sector, trend[D rows], latest{C summary + holders + soldOut + options{calls[], puts[]}}` | stock page |
| `signals/{period}` | all E tables, F, G (`ciks[]`, `matrix[][]`), H (symbols with options only) | patterns page |
| `securities/{cusip}` | enrichment cache (ingest only) | — |
| `ownership/feed` | `updatedAt, startDate, lastFiledAt, counts{filings, investors, issuers}, events[J event rows, newest first, ≤ recent_events]` | ownership page |
| `ownership_issuers/{symbol}` | `symbol, issuerCik, issuerName, sector, holders[J stake rows with is_current], events[newest first, ≤ max_events_per_doc]` | stock page (second read; absent ⇒ section hidden) |
| `ownership_investors/{cik}` | `cik, name, short\|null, cluster\|null, isRoster, isActivist, stakes[current], events[newest first, ≤ max_events_per_doc]` | investor page; manager page (second read) |

J event row (camelCase): `accession, form, isAmendment, amendmentNo, filedAt, eventDate, investorCik, investorName, short, isRoster, isActivist, issuerCik, issuerName, symbol, sector, shares, pct, prevPct, changePp, event, priority, purpose, url`. J stake row: `investorCik, investorName, short, isRoster, isActivist, issuerCik, issuerName, symbol, sector, form, pct, shares, changePp, event, filedAt, accession, url`. `ownership_issuers` ids use `quote(symbol, safe='')` / `encodeURIComponent`, like `stocks/`. Each run rewrites `ownership/feed` and **only** the issuer/investor docs touched by that run's new filings (Firestore free tier: 20K writes/day); `--rebuild` rewrites all.

Every doc stays far under 1 MB (largest: `ownership/feed` ≈ 200 KB, `signals` ≈ 100 KB, `meta` ≈ 100 KB). Rules: public read, no client write.

### GCS layout (when `GCS_BUCKET` is set; required for the ownership pipeline)
```
raw/<cik>/<period>/infotable.xml
parquet/holdings/<period>.parquet
parquet/<table>/<period>.parquet        # one per derived table A–H
raw_ownership/<accession>.xml           # Milestone 8
parquet/ownership_filings.parquet       # Milestone 8: single all-time file = the ownership pipeline's state
```

## Secrets and public-repo safety

The repo is PUBLIC. Follow exactly.

| Name | Kind | Where | Why |
|---|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT` | **secret** | GitHub Actions secret | Service-account JSON. Writes Firestore + GCS, deploys Hosting. |
| `EDGAR_IDENTITY` | **secret** | GitHub secret + `ingest/.env` | `"Your Name you@email"`. SEC requires it. Your email — never in the repo. |
| `OPENFIGI_API_KEY` | **secret** | GitHub secret + `ingest/.env` | Free key. Batch size 10 → 100. |
| `GCS_BUCKET` | variable | GitHub variable + `ingest/.env` | Bucket name. Unset = skip archive. |
| `FIREBASE_PROJECT_ID` | variable | GitHub variable | Used by deploy. |
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | variable | GitHub variables + `web/.env` | Firebase **web** config. Public by design (ships in the JS bundle). Access is controlled by `firestore.rules`. |

Rules: never print a secret; workflows use `push` / `schedule` / `workflow_dispatch` only, never `pull_request_target`; `permissions: contents: read` everywhere except `ingest.yml`, which needs `contents: write` for its keepalive commit; the service-account JSON goes to `$RUNNER_TEMP/sa.json` via an `env:` mapping; locally the key file lives **outside** the repo; `ingest.py` fails fast with a clear message when `EDGAR_IDENTITY` or credentials are missing.

Secret scan used by the AC below (the pattern is written so it does not match its own text):
```
git grep -i -E "@gma[i]l|AIza[0-9A-Za-z_-]{20}|-----BEG[I]N|private[_]key"
```

`.gitignore` (root):
```
.env
.env.*
!.env.example
*service-account*.json
*serviceAccount*.json
*-firebase-adminsdk-*.json
.firebase/
firebase-debug.log
firebase-debug.*.log
node_modules/
dist/
__pycache__/
*.pyc
.venv/
.pytest_cache/
.DS_Store
```

`firestore.rules`:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read: if true;
      allow write: if false;
    }
  }
}
```

## Manual setup (the user does these; agents cannot)

1. Firebase console → create project. Enable **Firestore** (Native mode, `us-central1`). Enable **Hosting**.
2. Project settings → General → Your apps → add a **Web app** → copy the API key, project ID, and app ID into `web/.env` and GitHub **Variables**.
3. Upgrade to **Blaze**. Create bucket `<project>-13f`. Set a **budget alert at $5**. Put the name in `GCS_BUCKET`.
4. IAM → Service accounts → create `ci-13f`. Roles: **Firebase Admin** + **Storage Object Admin**. Create a **JSON key** → paste into GitHub secret `FIREBASE_SERVICE_ACCOUNT`; keep a copy outside the repo for local runs. If Hosting deploy fails on permissions, add **Service Usage Consumer**.
5. Free OpenFIGI API key (openfigi.com) → secret `OPENFIGI_API_KEY`.
6. Secret `EDGAR_IDENTITY` = `Your Name your@email.com`.
7. Create the public GitHub repo. Push `main`. Add the secrets/variables. **Before Milestone 6.**
8. Custom domain: Firebase console → Hosting → Add custom domain → TXT + A records at your registrar.
9. One-time: `npx firebase-tools login`, then `npx firebase-tools deploy --only firestore:rules` (after Milestone 1).

---

## Milestones

Work in order. Do not start a milestone until the previous one's AC are all checked. Each milestone has a `Status:` line the dev agent updates in this file (`not started` → `in progress` → `done <short sha>`, the sha of the milestone's main commit, set in a small follow-up `docs:` commit). Commit directly to `main` at the end of each task group with a conventional message (`docs:`, `feat:`, `fix:`, `ci:`, `test:`).

### Milestone 0 — Documentation and repo skeleton  (planning model)
Status: done 0d303cf

Tasks
1. `git init -b main`; `git config core.symlinks true`.
2. `.gitignore` (above), `LICENSE` (MIT).
3. `README.md` per the README spec. "Live site" stays `TBD` until Milestone 6.
4. `CLAUDE.md` per the CLAUDE.md spec.
5. `AGENTS.md` as a git symlink to `CLAUDE.md`. Try `cmd /c mklink AGENTS.md CLAUDE.md` first (needs the Windows symlink privilege). If Windows refuses, record it in git directly (Git Bash): `blob=$(printf 'CLAUDE.md' | git hash-object -w --stdin); git update-index --add --cacheinfo 120000,$blob,AGENTS.md; printf 'CLAUDE.md' > AGENTS.md; git config core.symlinks false`. GitHub and Linux checkouts get a real symlink; this Windows checkout shows a 1-line pointer file, which is expected. To upgrade later: enable Developer Mode, log out and in, then `git config core.symlinks true; rm AGENTS.md; git checkout -- AGENTS.md`.
6. `docs/PLAN.md` = this plan, in full.
7. Commit `docs: project plan, README, agent instructions`.

Acceptance criteria
- [x] `git ls-files` shows exactly `.gitignore LICENSE README.md CLAUDE.md AGENTS.md docs/PLAN.md`.
- [x] `git ls-files -s AGENTS.md` starts with `120000`, and `git cat-file -p <that blob>` prints `CLAUDE.md` (a real symlink on Linux/GitHub; a 1-line pointer file on a Windows checkout without the symlink privilege).
- [x] README: no sentence over ~20 words; a non-developer can follow "Set up your own copy".
- [x] CLAUDE.md has every section of its spec.
- [x] The secret scan (above) returns nothing.

### Milestone 1 — Project config, managers, signal config
Status: done 6b26006

Tasks
1. `firebase.json`:
   ```json
   { "hosting": { "public": "web/dist", "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
                  "rewrites": [{ "source": "**", "destination": "/index.html" }] },
     "firestore": { "rules": "firestore.rules" } }
   ```
2. `.firebaserc`: `{ "projects": { "default": "YOUR_PROJECT_ID" } }` (user fills in).
3. `firestore.rules` (above).
4. `ingest/funds.json` — 11 managers. Candidate CIKs are from memory: **verify every one**.
   ```json
   [
     { "cik": "1067983", "name": "Berkshire Hathaway Inc",             "short": "Berkshire",   "cluster": "Value / Quality" },
     { "cik": "1336528", "name": "Pershing Square Capital Management", "short": "Pershing",    "cluster": "Activist / Quality" },
     { "cik": "1647251", "name": "TCI Fund Management Ltd",            "short": "TCI",         "cluster": "Quality / Compounders" },
     { "cik": "1061768", "name": "Baupost Group LLC",                  "short": "Baupost",     "cluster": "Value / Event Driven" },
     { "cik": "1656456", "name": "Appaloosa LP",                       "short": "Appaloosa",   "cluster": "Macro / Value" },
     { "cik": "1536411", "name": "Duquesne Family Office LLC",         "short": "Duquesne",    "cluster": "Macro" },
     { "cik": "1135730", "name": "Coatue Management LLC",              "short": "Coatue",      "cluster": "Tech / Growth" },
     { "cik": "1167483", "name": "Tiger Global Management LLC",        "short": "Tiger Global","cluster": "Tech / Growth" },
     { "cik": "1103804", "name": "Viking Global Investors LP",         "short": "Viking",      "cluster": "Tech / Growth" },
     { "cik": "1061165", "name": "Lone Pine Capital LLC",              "short": "Lone Pine",   "cluster": "Tech / Growth" },
     { "cik": "1040273", "name": "Third Point LLC",                    "short": "Third Point", "cluster": "Event Driven / Activist" }
   ]
   ```
   Verify each: `python -c "from edgar import *; set_identity('$env:EDGAR_IDENTITY'); c=Company(CIK); print(c.name, len(c.get_filings(form='13F-HR')))"`. Name must match and count > 0. Otherwise look the manager up at `https://www.sec.gov/cgi-bin/browse-edgar?company=<name>&type=13F-HR` and use the entity that files 13F-HR. Write the verified EDGAR names into `funds.json`.
5. `ingest/signals_config.json` (above).
6. `ingest/.env.example` and `web/.env.example` with empty keys from the secrets table.
7. Commit `feat: firebase config, managers, signal config`.

Acceptance criteria
- [x] All 11 CIKs verified; names match EDGAR; each has ≥ 4 `13F-HR` filings.
- [x] `npx firebase-tools deploy --only firestore:rules` succeeds (user runs it).
- [x] `.env.example` files list every env var from the secrets table and nothing else. No `.env` committed.

### Milestone 2 — Fetch, normalize, enrich (base table)
Status: done b5e6d03

**Implementation note (deviation from spec):** edgartools 5.56.0's `holdings` DataFrame already
resolves a `Ticker` per row, and it covers foreign-domiciled-but-US-listed issuers (Chubb, ASML,
Eaton, Linde, ...) that OpenFIGI's free CUSIP mapping cannot match — OpenFIGI-only enrichment left
10.7% of rows unmapped, above the 5% AC. `fetch.edgar_ticker_hints(df)` extracts CUSIP→ticker from
the raw holdings frame; `enrich.ensure_securities(..., ticker_hints=...)` prefers that hint and
only calls OpenFIGI when a CUSIP has none. Result: 0.0% unmapped on a full 11-manager run.
`enrich.py`'s URL constants moved to `ingest/api_constants.py`.

Tasks
1. `ingest/requirements.txt`: `edgartools pandas pyarrow requests firebase-admin google-cloud-storage python-dotenv pytest`. Pin exact versions after install. Must install on Python 3.10 and 3.12.
2. `sectors.py` — `SIC_RANGES` (first match wins) and `sic_to_sector(sic, security_type)`: `"ETP"` → `"ETF / Fund"`, `None` → `"Unknown"`, range hit, else `"Other"`. Ranges:
   ```
   (100,999,"Other") (1000,1499,"Energy & Mining") (1500,1799,"Industrials")
   (2000,2199,"Consumer Staples") (2200,2599,"Consumer Discretionary") (2600,2699,"Materials")
   (2700,2799,"Communication") (2800,2829,"Materials") (2830,2836,"Health Care")
   (2840,2899,"Consumer Staples") (2900,2999,"Energy & Mining") (3000,3499,"Materials")
   (3500,3569,"Industrials") (3570,3579,"Technology") (3580,3669,"Industrials")
   (3670,3699,"Technology") (3700,3799,"Consumer Discretionary") (3800,3849,"Health Care")
   (3850,3999,"Consumer Discretionary") (4000,4799,"Industrials") (4800,4899,"Communication")
   (4900,4999,"Utilities") (5000,5999,"Consumer Discretionary") (6000,6799,"Financials")
   (7000,7369,"Consumer Discretionary") (7370,7379,"Technology") (7380,7999,"Consumer Discretionary")
   (8000,8099,"Health Care") (8100,8999,"Industrials")
   ```
   `# ponytail: SIC ranges are coarse; swap for a GICS source if sector accuracy matters.`
3. `fetch.py`
   - `fetch_filings(cik, quarters) -> list[Filing]`: `Company(cik).get_filings(form="13F-HR")` sorted by report period desc, take `quarters`. Ignore `13F-HR/A`.
   - `filing_rows(filing) -> tuple[period, filed_at, raw_xml: bytes | None, DataFrame]`: `.obj()` → info table. **Print `df.columns` once and map explicitly; names vary by edgartools version.**
   - `normalize(df, cik, short, period, filed_at) -> DataFrame` with base-table columns minus `symbol/ticker/sector`; `put_call` upper-cased to `PUT`/`CALL` else null; blank CUSIP dropped; duplicates summed on `(cusip, put_call)`; `value`, `shares` as int.
4. `enrich.py`
   - `openfigi_map(cusips, api_key)`: POST `https://api.openfigi.com/v3/mapping`, `[{"idType":"ID_CUSIP","idValue":c}]`, header `X-OPENFIGI-APIKEY` when set; batch 100 with key / 10 without; on 429 sleep 6 s and retry once; pick first item with `exchCode == "US"` else first; unmapped → `ticker None`.
   - `sec_ticker_to_cik(identity)`: GET `https://www.sec.gov/files/company_tickers.json`, `User-Agent: <identity>`; `TICKER → 10-digit CIK`.
   - `sec_sic(cik10, identity)`: GET `https://data.sec.gov/submissions/CIK{cik10}.json`; `(sic, sicDescription)`; `time.sleep(0.11)`.
   - `ensure_securities(db, cusips, identity, api_key, refresh_unknown=False) -> dict[cusip, dict]`: read cache, enrich missing (and unknown if flag), write in batches of 400, return full map.
   - `attach(df, securities) -> DataFrame`: adds `ticker`, `sector`, `symbol` (`ticker` or `"_"+cusip`).
5. `ingest.py` (CLI only for now): args `--quarters N` (default from config), `--fund CIK`, `--dry-run`, `--refresh-unknown`. Flow: funds → fetch → normalize → union CUSIPs → `ensure_securities` → `attach` → concatenate into the base table. Dry run prints per manager and period: row count, total value, top 10 by value with ticker/sector, PUT/CALL counts. Loads `ingest/.env` via `python-dotenv`. Exit non-zero if any manager failed, after processing the rest.
6. `test_sectors.py` (ETP / None / in-range / out-of-range) and `test_fetch.py` (`normalize` on a 6-row fixture: upper-cases put/call, merges duplicate CUSIP, drops blank CUSIP, ints).
7. Commit `feat: 13F fetch, normalize, and enrichment`.

Acceptance criteria
- [x] `cd ingest; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; pytest` → green.
- [x] `python ingest.py --fund 1067983 --dry-run` → Berkshire, 4 periods (latest 2026-06-30 as of Sept 2026), ~40 rows each, tickers like AAPL / BAC / AXP with non-Unknown sectors.
- [x] `python ingest.py --dry-run` → all 11 managers × 4 periods; unmapped CUSIPs < 5 % of rows. (0.0% with `--refresh-unknown` once, after the ticker-hints fix above.)
- [x] Second `--dry-run` writes 0 new `securities` docs (cache works) and finishes in < 2 min. (3.9s.)
- [x] No secret value appears in output.

### Milestone 3 — Derived tables and storage
Status: done e887713

**Implementation notes (deviations from spec):**
- `derive_all`'s output dict gained three entries not in the original table list, needed by
  `store.py` to keep `write_firestore(db, tables, funds, periods)`'s exact signature (no raw `h`
  parameter): `totals(h)` now also returns `filed_at`; `derive_all` adds `"holdings": h` (the base
  table itself, for `parquet/holdings/{period}.parquet`) and `"symbols"` (symbol→name/sector
  lookup, for the `stocks/{symbol}` doc's top-level fields).
- Firestore documents use **camelCase** field names throughout (`prevWeight`, `soldOut`,
  `mostSimilar`, ...), converted from the Python side's snake_case by `store._clean`. The plan's
  Firestore table only showed camelCase for top-level fields; this extends the convention to every
  nested object, matching normal JS/TS style for Milestone 4's `types.ts`.
- Firestore **forbids arrays nested directly inside arrays**. `signals/{period}.managerSimilarity`
  therefore stores `matrix` as `[{values: [...]}, ...]` (one row-object per manager), not `number[][]`.
- A manager's "last 4 quarters" can span more than 4 *calendar* quarters in the union across all
  11 managers, when one manager has an irregular filing gap (skips a quarter, so its own last-4
  reach further back). Real run: `meta/latest.periods` has 5 entries, not 4; `signals` has 5 docs,
  not 4. `manager_quarters` is still exactly 44 (11 × 4, each manager's own count). This is the
  intended behavior of "periods = sorted distinct periods in the window" (docs/PLAN.md line 95),
  not a bug.

Real Firestore run confirmed live: 11 `managers`, 44 `manager_quarters`, 514 `stocks`, 5 `signals`.
`meta/latest` ≈ 27.8 KB, `signals/{latestPeriod}` ≈ 34.5 KB — both far under the 300 KB target.

**Bucket naming (deviation from Manual setup step 3):** rather than a separately-created
`<project>-13f` Cloud Storage bucket, the user enabled **Firebase Storage** in the console, which
provisions its own default bucket named `<project-id>.firebasestorage.app`. The `google-cloud-storage`
library writes to it exactly the same way (Admin SDK bypasses Firebase Storage security rules,
uses IAM — the `ci-13f` service account already has the needed role). `GCS_BUCKET` is
`form-13f-dashboard.firebasestorage.app`, not `form-13f-dashboard`. Confirmed live: 44 `raw/`
objects (11 managers × 4 filings), 57 `parquet/` objects across 14 tables, ~2.2 MB total.

Tasks
1. `derive.py` — pure functions over the base table, no I/O, each returning a DataFrame or dict exactly as specified in "Base dataset and derived tables":
   `totals(h)`, `manager_quarter_summary(h, periods)`, `manager_sector_exposure(h, periods)`, `stock_quarter_summary(mqs, managers_per_period)`, `stock_trend(sqs)`, `conviction_score(sqs, cfg)`, `consensus_tables(sqs, mqs, trend, cfg)`, `sector_rotation(mse, cfg)`, `manager_similarity(mqs)`, `options_exposure(h)`, `clusters(mqs, mse, funds)`, and `derive_all(h, funds, cfg) -> dict[str, DataFrame|dict]`.
2. `fixtures/holdings_small.csv` — 3 managers × 2 periods × 6 symbols, hand-built so every status occurs (NEW, ADDED, TRIMMED, UNCHANGED, SOLD_OUT, null for a manager missing the first period), one PUT and one CALL row, two managers with identical weights (cosine = 1.0) and one orthogonal (cosine = 0.0), one sector that rises for two managers and falls for one.
3. `test_derive.py` — asserts hand-computed expected values from the fixture for: weights and totals; every status; `change` sign and null rules; SOLD_OUT row emitted with `change = -prev_weight`; C counts and `pct_holding`; D `net_change`; consensus buys / exits membership and order; high-conviction filter; score ordering (the concentrated recent name beats the widely-held low-weight name); sector rotation counts; similarity 1.0 / 0.0; options exposure lists; cluster common holdings.
4. `store.py`
   - `write_gcs(bucket, raw_by_filing, tables)`: raw XML + one Parquet per table per period. try/except per object; log and continue.
   - `write_firestore(db, tables, funds, periods)`: builds and writes `meta/latest`, `managers/{cik}`, `manager_quarters/{cik}_{period}`, `stocks/{symbol}`, `signals/{period}` exactly as the Firestore table above. Batched (400/batch). Deletes nothing (docs are overwritten by id).
5. `ingest.py`: after the base table, call `derive_all`, then `store.write_gcs` (if bucket) and `store.write_firestore` (unless `--dry-run`). `--dry-run` also prints the top 5 rows of `consensus_buys`, `high_conviction`, `top_signals`, `sector_rotation`, and the similarity matrix.
6. Commit `feat: derived signal tables and Firestore/GCS writer`.

Acceptance criteria
- [x] `pytest` green; `test_derive.py` covers every bullet in Task 3.
- [x] `python ingest.py --dry-run` prints sensible signals for the latest period (e.g. a known crowded name shows `manager_count >= 3`). (TSM: 6 managers, AMZN: 7 managers.)
- [x] Real run (local, `GOOGLE_APPLICATION_CREDENTIALS` outside the repo): Firestore has `meta/latest` (11 managers, 5 periods — see implementation note, clusters, symbols), 11 `managers`, 44 `manager_quarters`, `stocks` for every symbol (514), 5 `signals`.
- [x] GCS has `raw/` and `parquet/` for every table and period. Bucket is `form-13f-dashboard.firebasestorage.app` (Firebase Storage's default bucket, not a separately-created `<project>-13f` bucket — see note below). 44 `raw/` objects (11 managers × 4 filings), 57 `parquet/` objects across 14 tables.
- [x] `signals/{latestPeriod}` and `meta/latest` each < 300 KB (check in console). (34.5 KB and 27.8 KB.)
- [x] Spot-check one manager in the console against a public 13F source: top holding and its weight agree within rounding. (Berkshire top holding AAPL at 22.0% weight, matches public 13F trackers.)

**Tooling addendum (post-M3, dev-only dependency):** `ruff` added to `ingest/requirements.txt` for
formatting + linting (replaces manual style review). Config in `ingest/pyproject.toml`, target
Python 3.10 (matches the local/CI compat requirement). Not part of the runtime pipeline; `ruff
format` / `ruff check` are run manually before commits, not wired into CI in this MVP.

### Milestone 4 — Web app shell, manager page, stock page
Status: done 09c2b68

**Implementation notes (deviations from spec):**
- shadcn's CLI has been redesigned since the plan was written: `init` now asks for a component
  library (`base`, `radix`, `aria` — chose `radix`, matching the ecosystem the plan assumed) and a
  design "preset" (`nova`, `vega`, `maia`, ...; no more literal "neutral" choice, though
  `components.json`'s `baseColor` is still `"neutral"` under the hood). Ran
  `npx shadcn@latest init -t vite -b radix -p nova -y`. `init` also auto-creates a `button.tsx`
  component; deleted it immediately since it's not one of the 5 listed and nothing in `table`,
  `tabs`, `badge`, `input`, `select` depends on it — `src/components/ui/` holds exactly the 5.
- `meta/latest.symbols` gained a `sector` field (`{symbol, name, sector}`, was `{symbol, name}`).
  The Positions treemap needs to color 25 cells by sector, and neither `manager_quarters.positions`
  nor the old `meta.symbols` carried that — the only place sector lived was `stocks/{symbol}`,
  which would have meant up to 25 extra reads per page load. Added it to `derive_all`'s existing
  `symbols` table (already had sector) via `store.py`'s `_build_meta`; one extra field on an
  already-cached read, zero extra reads. `ingest/test_store.py` updated to assert it.
- Fixed a real bug found while building this: `signals/{period}`'s top-level keys were an
  accidental mix of snake_case (`consensus_buys`, `fastest_growing`, `sector_rotation`) and
  camelCase (`managerSimilarity`, `optionsExposure`) in `store.py`. Made fully camelCase before
  writing `types.ts` against it, so the TS contract wouldn't encode the inconsistency. Re-ran the
  real ingest to overwrite `signals/*` with corrected field names.
- Firestore's JS SDK retries a bad project/network config indefinitely and never rejects a
  `getDoc()` promise on its own — a wrong `VITE_FIREBASE_PROJECT_ID` would otherwise hang on
  "Loading…" forever instead of surfacing an error. `src/data.ts`'s `fetchDoc` now races every
  read against a 10s timeout. Found and fixed by actually testing the AC in a browser (Playwright,
  no `chromium-cli` available in this environment), not just by inspection.
- `main.tsx` uses a dynamic `import('./App')` instead of a static one specifically so the
  synchronous throw in `firebase.ts` (empty env vars) rejects an awaitable promise instead of
  crashing before React ever renders — a static import's error isn't catchable by a try/catch or
  error boundary, since ES module evaluation happens before the importing module's own code runs.
- Chart entrance animations (Recharts `Line`/`Bar`) are disabled (`isAnimationActive={false}`)
  after a Playwright screenshot briefly looked like a broken line chart — it was mid-animation,
  not a data bug, but a dense ledger-style UI shouldn't animate on every load regardless.
- `stocks/{symbol}` doc IDs and `/stock/:symbol` routes now percent-encode the symbol
  (`urllib.parse.quote(symbol, safe="")` in `store.py`, `encodeURIComponent` in `data.ts` /
  `StockLink.tsx` / `SymbolSearch.tsx`, `decodeURIComponent` in `StockPage.tsx`). A SPAC
  unit/warrant ticker with a `/` (`ABC/U`, `ABC/WS`) would otherwise split into extra Firestore
  path segments and extra route segments. Ordinary tickers are byte-for-byte unchanged, so no
  re-ingest is required for existing data.

Verified live (Playwright against the dev server, real Firestore data): treemap/sector
bars/QoQ table/positions/four lists/similar-managers all render on `/manager/1067983`; period
`Select` switching refetches and updates the total-value tile; `/stock/AAPL` shows tiles, holders,
options `<details>` groups (Reported Put Exposure correctly shows Third Point, matching the PUT
row seen in Milestone 2/3 dry runs), and both trend charts with all 4 points connected; header
search `nvd` → NVDA → Enter navigates; symbol/manager links cross-navigate both directions; 375px
viewport has zero horizontal overflow (`scrollWidth === clientWidth`); zero console errors on any
page. Both empty and non-empty-but-wrong `VITE_FIREBASE_PROJECT_ID` show a visible error message.

Tasks
1. Scaffold `npm create vite@latest web -- --template react-ts`; `npm i`.
2. Tailwind v4: `npm i tailwindcss @tailwindcss/vite`; plugin in `vite.config.ts`; `@import "tailwindcss";` at top of `src/index.css`.
3. Alias `@/*` → `./src/*` in `tsconfig.json`, `tsconfig.app.json`, and `vite.config.ts` (`resolve.alias`); `npm i -D @types/node`.
4. shadcn: `npx shadcn@latest init` (Vite, neutral, CSS variables). Then **only** `npx shadcn@latest add table tabs badge input select`.
5. `npm i firebase recharts react-router-dom`; `npm i -D vitest`; script `"test": "vitest run"`.
6. `src/firebase.ts` (init from `VITE_*`; readable error if empty). `src/types.ts` mirrors the Firestore docs. `src/data.ts`: `getMeta()`, `getManager(cik)`, `getManagerQuarter(cik, period)`, `getStock(symbol)`, `getSignals(period)` — one `getDoc` each, typed.
7. `src/format.ts` + `format.test.ts`: `money` (`$1.2B`, `$340M`, `$12K`), `pct` (`12.3%`), `pp` (`+1.1 pp`, `−0.5 pp`), `quarterLabel("2026-06-30") → "2026 Q2"`, `SECTOR_COLORS` (12 fixed), `STATUS_COLORS`.
8. Routes (`react-router-dom`): `/` → redirect `/patterns`; `/patterns`; `/managers`; `/manager/:cik?period=`; `/stock/:symbol`. `Header.tsx`: nav links + `SymbolSearch.tsx` (shadcn `Input`, filters `meta.symbols` by symbol/name substring, Enter or click → `/stock/:symbol`).
9. `ManagerPage.tsx`: header (name, cluster badge, `Select` for period); tiles: total value, positions, NEW / ADDED / TRIMMED / SOLD_OUT counts; Recharts `Treemap` of top 25 by weight colored by sector; `SectorBars.tsx` (current weight bars) + QoQ table (sector, prev, current, change); positions `Table`: symbol (link), name, weight, prev, change, `StatusBadge`; four short lists: Biggest Adds, Biggest Trims, New Positions, Sold Out; "Most similar managers" list.
10. `StockPage.tsx`: header (symbol, name, sector); summary tiles: "x / N managers own", added, trimmed, new, sold out; holders `Table` (manager link, weight, change, status); `<details>` groups for Equity Long / Reported Calls / Reported Puts with manager names; two Recharts charts from `trend`: manager count (bars) and avg weight (line).
11. Theme (`index.css` `:root` tokens): light "financial ledger" — off-white paper, near-black ink, numbers in `font-mono tabular-nums` right-aligned; semantic colors only: NEW/ADDED green, TRIMMED amber, SOLD_OUT red, PUT red, CALL blue; sectors from `SECTOR_COLORS`. Dense tables, sticky header, visible focus rings, tables inside `overflow-x-auto`. Loading / empty / error states on every page.
12. Commit `feat: app shell, manager page, stock page`.

Acceptance criteria
- [x] `src/components/ui/` contains exactly `table tabs badge input select` (+ `lib/utils.ts`).
- [x] `npm run test` green; `npm run build` zero TS errors.
- [x] `/manager/1067983` shows Berkshire: treemap, sector bars and QoQ table, positions with statuses, four lists, similar managers; period `Select` switches quarters.
- [x] `/stock/AAPL` shows the summary tiles, holders with status, options groups (may be empty), and both trend charts with 4 points.
- [x] Header search: typing `nvd` offers NVDA; Enter opens `/stock/NVDA`.
- [x] Clicking a symbol on a manager page opens the stock page; clicking a manager on a stock page opens the manager page.
- [x] At 375 px wide nothing scrolls horizontally except inside tables.
- [x] Wrong `VITE_FIREBASE_PROJECT_ID` shows a visible error, not a blank page.

### Milestone 5 — Patterns page and managers page
Status: done 175900a

**Implementation note:** `top_signals` (one of the 8 E-tables, part of `Signals`/`signals/{period}`)
is intentionally not rendered as an 11th patterns section — the task list names exactly 10
sections and `top_signals` isn't among them. The data is still computed and stored (used
elsewhere / available for later), just not given its own section here.

Verified live (Playwright against the dev server, real Firestore data): all 10 sections render on
`/patterns` under a working sticky nav + period `Select`; sector rotation bars are green for
positive / red for negative avg change, matching the table beneath; the similarity heatmap's
diagonal reads 1.00, cell hover title shows both manager names and the value, and the "most
similar" lists (computed client-side from the already-loaded matrix, no extra reads) agree with
the heatmap's own numbers; Put/Call rows expand via `<details>` into Equity Long / Reported Calls
/ Reported Puts name lists — "Reported Puts" appears, "short" does not, anywhere on the page;
`/managers` groups all 11 managers into their 8 clusters with common holdings and top sector,
including the edge cases of a single-member cluster and a manager absent from the given period.
Zero console errors on either page.

Tasks
1. `PatternsPage.tsx`: loads `signals/{latestPeriod}` (period `Select` in the header of the page); sticky in-page nav with anchors to 10 sections; each section is one small component in `pages/patterns/`:
   `ConsensusBuys`, `ConsensusExits`, `HighConviction`, `BiggestNew`, `BiggestAdds`, `BiggestTrims`, `SectorRotation` (table + horizontal bar chart of avg change, positive/negative colored), `FastestGrowing`, `ManagerSimilarity` (`Heatmap.tsx`: CSS-grid matrix with color intensity, plus "most similar" lists), `PutCallExposure` (table: symbol, equity count, calls count, puts count; `<details>` to expand manager names).
   Every symbol links to `/stock/:symbol`; every manager links to `/manager/:cik`.
2. `ManagersPage.tsx`: clusters from `meta.clusters`: label, members (links), common holdings (links), top sector.
3. Commit `feat: patterns page and managers page`.

Acceptance criteria
- [x] `/patterns` renders all 10 sections from one Firestore read (check the network tab: 1 `signals` doc + `meta`). (`meta` fetched once at app level via `MetaProvider`; `signals/{period}` fetched once per period in `PatternsPage`.)
- [x] Tables show the columns listed in "Consensus tables"; sort order matches. (Rendered in server-given order; `derive.py`/`store.py` already sort each table.)
- [x] Sector rotation bar chart colors positive and negative moves differently.
- [x] Heatmap: diagonal is 1.00; hovering a cell shows both manager names and the value.
- [x] Put/Call section: expanding a row lists manager names per group; puts are labelled "Reported Puts", never "short".
- [x] `/managers` groups all 11 managers by cluster with common holdings and top sector.
- [x] `npm run build` zero TS errors; `npm run test` green.

### Milestone 6 — CI/CD and custom domain
Status: done b47283f

**Implementation note:** local testing before the first push caught a real, latent bug:
`derive.options_exposure()` returned a columnless empty `DataFrame` when a fund/window had zero
PUT/CALL rows (`pd.DataFrame([])` has no columns at all), which crashed `store.py`'s
period/symbol indexing. This never surfaced in earlier full 11-manager runs because some manager
always had *some* options activity; it broke immediately on a single-fund real run
(`--fund 1067983`, Berkshire, zero options that quarter). Fixed by giving `options_exposure` an
explicit `columns=` list so the empty case still has the right shape; added a regression test
(`test_options_exposure_has_columns_with_zero_option_rows`).

Verified live against the real GitHub Actions runs (not just locally):
- Push of `ci: deploy...` (touches `.github/workflows/deploy.yml`, itself in the `paths` filter)
  → `Deploy` ran, green in 1m4s → `https://form-13f-dashboard.web.app/manager/1067983` confirmed
  live with real data via a Playwright screenshot, zero console errors.
- `gh workflow run ingest.yml -f dry_run=true` → green in 1m9s. Log has 44 "total value" lines
  (11 managers × up to 4 periods each). Scanned the full log for `BEGIN PRIVATE KEY` and any
  `user@domain`-shaped string: zero matches. Keepalive step correctly printed "No
  data/last_ingest.json written (dry run); skipping commit." and made no commit.
- `gh workflow run ingest.yml -f dry_run=false` → green in 1m10s (well under 30 min).
  `meta/latest.updatedAt` moved from `05:27:30` to `05:33:44`. A `chore: ingest 2026-06-30` commit
  landed on `main`, authored by `github-actions[bot]`, containing `data/last_ingest.json` with all
  11 manager short names. Confirmed via `gh run list --workflow=deploy.yml` that this commit (and
  a later docs-only push) did **not** create a new `Deploy` run — the `paths` filter holds.

**Custom domain:** the user added it (DNS records at their registrar) — not something an agent
can do. `https://13f.darren-zhu.com` is live, verified `HTTP 200`, and set as the GitHub repo's
"website" field. README no longer duplicates the URL in its own section.

Prerequisite: Manual setup 1–7 done (secrets and variables exist on GitHub).

Tasks
1. `.github/workflows/deploy.yml`: `on: push: branches: [main], paths: [web/**, firebase.json, .github/workflows/deploy.yml]` + `workflow_dispatch`; `permissions: contents: read`; checkout → `actions/setup-node@v4` (node 22, `cache: npm`, `cache-dependency-path: web/package-lock.json`) → `npm ci` + `npm run build` in `web/` with `env:` `VITE_FIREBASE_*` from `vars` → `FirebaseExtended/action-hosting-deploy@v0` (`firebaseServiceAccount: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}`, `channelId: live`, `projectId: ${{ vars.FIREBASE_PROJECT_ID }}`).
2. `.github/workflows/ingest.yml`: `on: schedule: - cron: "0 13 16 * *"` (monthly on the 16th — re-running a quarter is idempotent and catches late filers) + `workflow_dispatch` (inputs `fund`, `dry_run`); `permissions: contents: write` (needed only for task 3); `concurrency: ingest`; checkout → `actions/setup-python@v5` (3.12, `cache: pip`) → `pip install -r ingest/requirements.txt` → write secret to `$RUNNER_TEMP/sa.json` from an `env:` var → `python ingest/ingest.py` with `env:` `GOOGLE_APPLICATION_CREDENTIALS`, `EDGAR_IDENTITY`, `OPENFIGI_API_KEY`, `GCS_BUCKET` and the optional flags.
3. Keepalive: GitHub disables scheduled workflows in a public repo after 60 days without repository activity, so the workflow must create activity. On a real (non-dry) run, `ingest.py` writes `data/last_ingest.json` (`{period, ranAt, managers}`); a final workflow step commits it as `chore: ingest <period>` using the `github-actions[bot]` identity and pushes with `GITHUB_TOKEN`. Skip the commit when the file is unchanged. `deploy.yml`'s `paths` filter already ignores `data/**`, so this commit does not trigger a deploy.
4. Commit `ci: deploy on push and monthly ingest`. Push.
5. User adds the custom domain (Manual setup 8). Set it as the GitHub repo's "website" field. Commit `docs: live site link`.

Acceptance criteria
- [x] Push to `main` → deploy green → `https://<project>.web.app` shows live data.
- [x] Ingest "Run workflow" with `dry_run=true` → green; log has 11 manager summaries and **no** secret values (search the log for `BEGIN PRIVATE KEY` and `@`).
- [x] Ingest with `dry_run=false` → green; `meta/latest.updatedAt` changed; run time < 30 min.
- [x] Custom domain serves the site over HTTPS. `https://13f.darren-zhu.com` verified `HTTP 200`.
- [x] `deploy.yml` has `permissions: contents: read`; `ingest.yml` has `permissions: contents: write` and nothing more; no `pull_request_target` anywhere.
- [x] After a real run, a `chore: ingest <period>` commit containing `data/last_ingest.json` appears on `main`, and it did not trigger a deploy.

### Milestone 7 — Docs sync and final check
Status: done b2e018d

Tasks
1. Re-read `README.md` and `CLAUDE.md` against what was built; fix any command or path that changed. Split any sentence over ~20 words.
2. Mark every milestone `done <sha>` in `docs/PLAN.md`.
3. Commit `docs: sync docs with implementation`.
4. *(Added on request)* `docs/ARCHITECTURE.md` — two Mermaid diagrams (system design: GCP/GitHub Actions; data flow: fetch → enrich → derive → store → display), plain-language explanation under each. Linked from `README.md`'s "How it works" and `CLAUDE.md`'s intro.

**Findings from the re-read (fixed):**
- `CLAUDE.md` said "quarterly ingest cron" — the real cron (`0 13 16 * *`, Milestone 6) is monthly. Fixed.
- `CLAUDE.md`'s Commands block didn't mention `ruff format` / `ruff check` (added post-Milestone-3 tooling). Added.
- `ingest/derive.py` is 439 lines, over the "~300 lines, split before it grows past that" convention. Left as one file and documented as a deliberate exception in `CLAUDE.md`: "Where logic lives" already requires all signal math in one auditable file, and splitting it would fragment 11 tightly-related pure functions across a package for no real readability gain.
- README itself needed no fixes — already accurate (verified against real file paths/commands) and every sentence checked in under ~20 words.

**Verification (not just proofreading):**
- Fresh `git clone` into a scratch directory, then ran the exact README commands for both `ingest` (venv, `pip install -r requirements.txt`, `pytest` — 26 passed) and `web` (`npm install`, `npm run build`, `npm run test` — 10 passed) with **no `.env` file present**. Both succeed; `ingest.py --dry-run` and `npm run dev` additionally need real secrets, which the README already says to fill in first.
- `git log -p` piped through the secret-scan pattern: zero matches. Also ran a broader manual check (the user's real email domain isn't Gmail, so the prescribed pattern alone wouldn't have caught a leak of it) for the literal email and any `user@domain` shape across the whole history, excluding known-safe noise (`@pytest.fixture`, `noreply@`, font/package files): zero real matches, only the README's own placeholder text `your@email.com`.

Acceptance criteria
- [x] A fresh clone + README alone gets a new user to a running local dashboard. (Mechanically verified for every step that doesn't require live secrets; the remaining steps are gated on secrets the README already tells the user to fill in.)
- [x] `git log -p | Select-String -Pattern "@gma[i]l|AIza[0-9A-Za-z_-]{20}|-----BEG[I]N|private[_]key"` returns nothing.
- [x] All milestone AC boxes in `docs/PLAN.md` are checked. Milestone 6's custom-domain AC was the
  user's action (DNS at their registrar); done, checked in this follow-up commit.

### Milestone 8 — 13D/13G Ownership Monitor  (planned by the planning model; built by the dev model)

Sub-milestones 8.1 → 8.7 are sequential. Contract: section J, the Firestore table, and the GCS layout above. Decisions (locked by the user): all `SCHEDULE 13D`/`13D/A` universe-wide + `SCHEDULE 13G`/`13G/A` from roster managers only; structured-XML filings only (from `start_date` 2024-12-18); daily cron in a separate `ownership.yml`; known activist = roster `cluster` contains "Activist"; `funds.json` `aliases` for firms filing under several CIKs; GCS parquet is the state; priority kept (minimal, not configurable); no new dependency.

**Verified facts — do not re-derive, do not deviate without asking** (checked live against EDGAR and the installed edgartools source):
- `edgartools==5.56.0` parses these forms: `edgar/beneficial_ownership/schedule13.py` → `Schedule13D`, `Schedule13G` with `.issuer_info{cik, name, cusip}`, `.reporting_persons[]{cik, name, aggregate_amount, percent_of_class, type_of_reporting_person}`, `.items.item4_purpose_of_transaction` (13D only), `.event_date` (a `MM/DD/YYYY` string — normalise to ISO), `.is_amendment`, `.has_structured_data`, `.total_shares`, `.total_percent` (already max over persons, excluding "aggregate excludes certain shares" rows; `0.0` when no persons → `null`). It has a classmethod that builds the object from an XML string (`parse_xml`); if that name differs, use whichever exists — stop and ask if none does.
- `edgar.get_filings(form=[the four form names], filing_date="YYYY-MM-DD:YYYY-MM-DD", amendments=True)` → `Filings`; `.to_pandas()` has `form, company, cik (int), filing_date, accession_number`. The index lists each filing **once per associated CIK** (subject company + every filer): 54 rows ↔ 27 unique accessions in a live check. **Dedupe on accession.** The surviving row's `cik` may be the subject company, so **never use the index row / `filing.cik` as the filer.**
- `Schedule13D.parse_xml` does not read `headerData`. Parse `headerData/filerInfo/filer/filerCredentials/cik` (the filer), `headerData/previousAccessionNumber`, and `formData/coverPageHeader/amendmentNo` yourself from `filing.xml()` with `xml.etree.ElementTree` and the `{*}` namespace wildcard.
- `filing.xml()` is one HTTP request (the submission `.txt`); `filing.obj()` calls it internally. **Never call `filing.homepage_url` / `filing.homepage`** (extra request). URL = `https://www.sec.gov/Archives/edgar/data/{int(filer_cik)}/{accession without dashes}/{accession}-index.html`.
- `Filing(cik=int, company=str, form=str, filing_date=str, accession_no=str)` is a public constructor — rebuild filings from the deduped rows.
- Only the lead reporting person reliably has a CIK; the 13G cover has none — 13G filer identity is the header filer CIK.
- Volumes: ~2,600 13D-family index rows per quarter incl. duplicates → roughly 7-10K unique filings since 2024-12-18 → backfill 20-40 min at SEC's 10 req/s; daily ≈ 30-50 filings. Firestore free tier = 20K writes/day → write only touched docs.
- Reuse: `enrich.ensure_securities(db, cusips, identity, api_key, refresh_unknown, ticker_hints)` + `enrich.attach`; invert `enrich.sec_ticker_to_cik(identity)` (`{cik10: ticker}`, first ticker wins) to build `ticker_hints = {cusip: ticker}` from `issuer_cik` so the backfill barely touches OpenFIGI. `store._clean`, `store._records`, `store._commit_in_batches` are imported as-is (`test_store.py` already does). `ingest.py` exposes `load_funds`, `load_config`, `init_firestore` — import them; **no** `clients.py`. Web patterns: `useAsyncData`, `useSortableRows`, `SideBadge`/`StatusBadge`, `AsyncStates`, `format.ts`; `firestore.rules` needs no change (blanket public read).
- Mirror `derive.py`: no prior data ⇒ `null`, never `NEW`.

Refactors decided: (1) CLAUDE.md "Where logic lives" becomes two files (`derive.py` for 13F, `ownership_derive.py` for 13D/13G) — done in 8.7; (2) `funds.json` optional `aliases` — done in 8.1; (3) ownership TS types go in `web/src/ownershipTypes.ts` so `types.ts` stays under 300 lines. Rejected: extracting a `clients.py`; renaming `store.py` helpers; merging 13D/13G fields into `stocks/` docs (the monthly 13F `batch.set` would wipe them).

#### Milestone 8.1 — Contract, config, aliases
Status: done 7993e30

Tasks
1. This section, section J, the Firestore/GCS rows, the config block, the Reuse line, the Skipped lines, and the repo-layout tree in this file.
2. `ingest/signals_config.json`: the `"ownership"` block shown under J.
3. `ingest/funds.json`: `"aliases"` on Elliott (`1791786`; aliases `1048445` Elliott Management Corp, `904495` Elliott Associates L.P., `937611` Elliott International L.P.) and Icahn (`921669`; aliases `1412093` Icahn Capital LP, `1413902` Icahn Capital Management LP, `1164756` Icahn Institutional Services LLC, `1317365` Icahn Management LP). The field is optional everywhere else.
4. `CLAUDE.md` "Adding a manager": one sentence on `aliases` and how the dry run finds them.
5. Commit `docs: plan milestone 8 — 13D/13G ownership monitor`.

Acceptance criteria
- [x] This file contains "### J. Ownership (13D/13G)", three `ownership*` rows in the Firestore table, two `ownership` lines in the GCS layout, and Milestones 8.1–8.7.
- [x] `python -c "import json; print(sorted(json.load(open('ingest/signals_config.json'))['ownership']))"` prints the 7 keys.
- [x] `python -c "import json; print({f['short']: f['aliases'] for f in json.load(open('ingest/funds.json')) if f.get('aliases')})"` prints exactly Elliott and Icahn.
- [x] `pytest ingest` green (27 passed; nothing else changed).

#### Milestone 8.2 — Fetch and parse (`ownership_fetch.py`)
Status: not started

Tasks
1. `ingest/ownership_fetch.py` (≤ 160 lines):
   - `FORMS = ["SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A"]`; `FILING_COLUMNS` = the J base-table columns, in order.
   - `roster_ciks(funds) -> dict[str, str]`: every roster CIK and alias (unpadded string, e.g. `"921669"`) → roster CIK.
   - `list_filings(funds, since: str, until: str) -> pd.DataFrame`: one `get_filings(form=FORMS, filing_date=f"{since}:{until}", amendments=True)`; `.to_pandas()`; `drop_duplicates("accession_number")`; keep rows whose form starts with `SCHEDULE 13D`, or starts with `SCHEDULE 13G` and `str(cik)` is in `roster_ciks`. Output columns `accession, form_raw, filing_date, cik, company`.
   - `to_filing(row) -> edgar.Filing` via the public constructor.
   - `header_fields(xml: str) -> tuple[str | None, int | None, str | None]` = `(filer_cik 10-digit, amendment_no, previous_accession)`; missing → `None`.
   - `parse_filing(xml: str, form_raw: str, accession: str, filed_at: str, company: str, cfg: dict) -> dict | None`: choose `Schedule13D`/`Schedule13G` by `form_raw`; `None` when `not obj.has_structured_data`; map to `FILING_COLUMNS`: `form` = `"13D"`/`"13G"`, `is_amendment = form_raw.endswith("/A")`, ISO `event_date`, `filer_cik` from `header_fields` (fallback: first reporting person with a CIK; else `None` → the caller skips the row with a warning), `reporting_ciks` zero-padded to 10, `investor_name` = the reporting person whose CIK equals `filer_cik`, else the first person, else `company`; `pct`/`shares` from `total_percent`/`total_shares` with the `0.0`-and-no-persons → `None` rule; `purpose` = `items.item4_purpose_of_transaction[:purpose_max_chars]` for 13D else `None`; `url` from `filing_url`. `ticker`/`sector`/`symbol` are attached later by `enrich.attach`, not here.
   - `filing_url(filer_cik: str, accession: str) -> str`.
   - `fetch_rows(listed: pd.DataFrame, cfg) -> tuple[list[dict], dict[str, str], int]` = `(rows, raw_xml_by_accession, failed_count)`; per-filing `try/except` → print a warning and continue; `xml() is None` counts as failed.
2. Fixtures `ingest/fixtures/ownership_13d.xml` and `ownership_13g.xml`: real structured filings trimmed to essentials (keep `headerData`, `coverPageHeader`, all `reportingPersons`, `item4`; drop addresses/signatures; ≤ ~80 lines each). Source: EDGAR `primary_doc.xml` of Elliott's Triple Flag `SCHEDULE 13D/A` accession `0000919574-26-004169` (filer `0001791786`, `amendmentNo` 3, previous `0000902664-23-002314`, `percentOfClass` 64.7, `aggregateAmountOwned` 133241535, issuer `0001829726`, CUSIP `89679M104`, event 06/30/2026) and Elliott's Pinterest `SCHEDULE 13G` accession `0000919574-26-005513` (`classPercent` 5.8, 28,000,000 shares, issuer `0001506293`, CUSIP `72352L106`).
3. `ingest/test_ownership_fetch.py` (no network): `header_fields` on the 13D/A → `("0001791786", 3, "0000902664-23-002314")`; on the 13G → `("0001791786", None, None)`; `parse_filing` on the 13D/A → `form == "13D"`, `is_amendment`, `pct == 64.7`, `shares == 133241535`, `issuer_cik == "0001829726"`, `cusip == "89679M104"`, `event_date == "2026-06-30"`, `url.endswith("0000919574-26-004169-index.html")`; on the 13G → `form == "13G"`, `pct == 5.8`, `purpose is None`; the 13D fixture with its `reportingPersons` block removed → `pct is None`; `roster_ciks` maps an alias to its roster CIK. `list_filings` is untested (network) — say so in a one-line comment.
4. `ruff format .`, `ruff check .`, `pytest`.

Acceptance criteria
- [ ] `pytest ingest/test_ownership_fetch.py` green; the test file contains none of `get_filings`, `requests`, `http`.
- [ ] In `ingest/`: `python -c "from ownership_fetch import header_fields; print(header_fields(open('fixtures/ownership_13d.xml').read()))"` prints `('0001791786', 3, '0000902664-23-002314')`.
- [ ] `ownership_fetch.py` ≤ 160 lines; `ruff check` clean.
- [ ] Manual, network, once (`.env` present): `python -c "import json; from ownership_fetch import list_filings; df=list_filings(json.load(open('funds.json')),'2026-09-01','2026-09-02'); print(len(df), df.accession.is_unique, df.form_raw.value_counts().to_dict())"` prints ~25-30 rows and `True`.

#### Milestone 8.3 — Derive (`ownership_derive.py`)
Status: not started

Tasks
1. `ingest/ownership_derive.py` (≤ 170 lines; pure — DataFrame in, DataFrame out; imports only pandas/numpy/stdlib):
   - `investor_map(funds) -> dict[str, dict]`: roster CIK and alias → `{cik, name, short, cluster}`.
   - `events(filings, funds, cfg) -> pd.DataFrame`: canonicalise the investor (header filer CIK first, then any reporting CIK), sort by `(investor_cik, cusip, filed_at, amendment_no.fillna(0), accession)`, per-timeline `shift` for `prev_pct`, `prev_form`, `prev_accession_in_log`, apply the J rules 1-8 in order, then `change_pp`, `is_roster`, `is_activist`, `priority`. Output columns = `FILING_COLUMNS` + `event, prev_pct, change_pp, prev_accession_in_log, is_roster, is_activist, priority, short, cluster`.
   - `stakes(events, cfg) -> pd.DataFrame`: last row per timeline; `is_current`.
   - `recent(events, n) -> pd.DataFrame`.
   - `derive_all(filings, funds, cfg) -> dict` with keys `filings, events, stakes, recent`.
2. `ingest/fixtures/ownership_small.csv` (~16 rows, columns = `FILING_COLUMNS`; `reporting_ciks` as a `|`-joined string, split in `events`) covering: initial 13D → `NEW`; amendment with no prior → `null`; null `pct` → `null`; 13G then 13D on one issuer → `SWITCHED_TO_13D`; drop below 5 → `EXITED`; re-entry after an exit → `NEW`; +2.9 → `INCREASED`; −0.8 → `DECREASED`; Δ 0.05 → `UPDATED`; a row whose `reporting_ciks` contains `0001048445` (Elliott alias) → `is_roster`, `is_activist`, `investor_cik == "1791786"`, `short == "Elliott"`; a 13G `NEW` → `MEDIUM`; a 13D `NEW` → `HIGH`; a same-day initial + `/A` pair ordered by `amendment_no`.
3. `ingest/test_ownership_derive.py`: `test_every_event_occurs` (all six named events present and ≥ 2 nulls), one test per rule-order pair (2 vs 4, 4 vs 5, 6 vs 7), `test_alias_canonicalises_to_roster_cik`, `test_priority_table`, `test_stakes_is_current`, `test_recent_orders_newest_first`, `test_events_does_not_mutate_input`.
4. `ruff format .`, `ruff check .`, `pytest`.

Acceptance criteria
- [ ] `pytest ingest` green; `test_ownership_derive.py` has ≥ 8 tests.
- [ ] `ownership_derive.py` ≤ 170 lines; every function typed; no `print`; no `firebase`, `edgar`, or `google` imports.
- [ ] In `ingest/`: `python -c "import json, pandas as pd; from ownership_derive import derive_all; t=derive_all(pd.read_csv('fixtures/ownership_small.csv'), json.load(open('funds.json')), json.load(open('signals_config.json'))['ownership']); print(t['events']['event'].value_counts(dropna=False).to_dict())"` shows `NEW, INCREASED, DECREASED, EXITED, SWITCHED_TO_13D, UPDATED` and a null count ≥ 2.

#### Milestone 8.4 — Store, CLI, dry run (`ownership_store.py`, `ownership.py`)
Status: not started

Tasks
1. `ingest/ownership_store.py` (≤ 170 lines): `STATE_BLOB = "parquet/ownership_filings.parquet"`, `RAW_PREFIX = "raw_ownership/"`; `read_state(bucket) -> pd.DataFrame | None`; `write_state(bucket, filings, raw_by_accession)` (raw XML per new accession, then the whole parquet; per-object `try/except` + `logger.exception` like `store.write_gcs`); `build_feed(tables, cfg) -> dict`; `build_issuer_docs(tables, cfg, only_symbols: set | None) -> dict[str, dict]`; `build_investor_docs(tables, funds, cfg, only_ciks: set | None) -> dict[str, dict]` (shapes exactly as the Firestore table; `events` = newest `max_events_per_doc`; `None` filter = all); `write_firestore(db, feed, issuer_docs, investor_docs) -> int` (write count; paths `ownership/feed`, `ownership_issuers/{quote(symbol, safe='')}`, `ownership_investors/{cik}`; `store._commit_in_batches`).
2. `ingest/ownership.py` (≤ 170 lines), CLI `--dry-run`, `--since`, `--until`, `--rebuild`:
   1. `load_dotenv`; `cfg = load_config()["ownership"]`; `EDGAR_IDENTITY` guard in `ingest.py`'s style; `edgar.set_identity`; `funds = load_funds()`; `db = init_firestore()`; `GCS_BUCKET` **required** — `ERROR: GCS_BUCKET is required for the ownership pipeline`, return 1.
   2. `state = read_state(bucket)`; `since = args.since or (max(state.filed_at) − refetch_overlap_days days) or cfg["start_date"]`; `until = args.until or today (UTC)`.
   3. `listed = list_filings(funds, since, until)` minus accessions already in `state`.
   4. `rows, raw, failed = fetch_rows(listed, cfg)`; print `fetched N new filings (M failed)`.
   5. `ticker_hints` from the inverted `sec_ticker_to_cik`; `securities = ensure_securities(db, new cusips, identity, api_key, False, ticker_hints)`; `attach` (runs in dry-run too — it is a cache, as in `ingest.py`).
   6. `filings = concat(state, new)`; `tables = derive_all(filings, funds, cfg)`.
   7. Dry run prints: the window; new-row counts by `event` and by `priority`; top-15 filers by filing count; **unmatched filers whose `investor_name` contains a roster `short` (case-insensitive)** with their `filer_cik`; the 20 newest events as a table. **Writes nothing** — no GCS, no Firestore (unlike `ingest.py`; the parquet is state and must not advance on a dry run).
   8. Real run: `write_state`, then `write_firestore(feed, issuer docs for touched symbols, investor docs for touched CIKs)`; `--rebuild` passes `None` filters. Print the write count. Exit 1 if `failed > 0`, else 0.
3. `ingest/test_ownership_store.py`: builders on `derive_all` of the CSV fixture — feed events newest first and ≤ `recent_events`; issuer doc keyed `quote("_" + cusip, safe="")` for an unresolved symbol; `only_symbols` filters; the Elliott-alias investor doc has `isRoster`, `isActivist`, `short == "Elliott"`; every doc survives `json.dumps` after `_clean` (no NaN).
4. `ruff format .`, `ruff check .`, `pytest`; then `python ownership.py --dry-run --since 2026-08-25` (network, no writes).
5. Commit 8.2-8.4 together: `feat: 13D/13G ownership pipeline`.

Acceptance criteria
- [ ] `pytest ingest` green; the 13F tests are untouched.
- [ ] The four new Python files are each ≤ 170 lines; `ruff format --check .` and `ruff check .` clean; `print` only in `ownership.py`.
- [ ] `python ownership.py --dry-run --since 2026-08-25` prints ≥ 100 new filings, an event table with at least `NEW` and `UPDATED`, the unmatched-filer list, and writes nothing (`parquet/ownership_filings.parquet` absent or its `updated` time unchanged; no `ownership/feed` in Firestore).
- [ ] `python ownership.py --since 2026-08-25 --until 2026-09-03` (real) creates `ownership/feed`; one `HIGH` event's `pct`, `shares`, `eventDate`, `issuerName` match its `url` on sec.gov; its `ownership_issuers/{symbol}` and `ownership_investors/{cik}` docs exist.
- [ ] Running that real command again prints `0 new filings` and `counts.filings` is unchanged.

#### Milestone 8.5 — Workflow and backfill
Status: not started

Tasks
1. `.github/workflows/ownership.yml`: copy `ingest.yml`; name `Ownership`; `schedule: - cron: "0 11 * * *"` (after EDGAR's nightly index rebuild); `workflow_dispatch` inputs `dry_run` (boolean, default false), `since`, `until` (strings), `rebuild` (boolean, default false); `permissions: contents: read`; `concurrency: ownership`; `timeout-minutes: 120`; run `python ingest/ownership.py` with the flags built the same bash way; **no keepalive/commit step** (the 13F job's monthly commit keeps the repo's schedules alive); same secrets and `GCS_BUCKET` var.
2. Commit `ci: daily 13D/13G ownership ingest`; push.
3. `gh workflow run ownership.yml -f dry_run=true -f since=2026-08-25` → green; read the log.
4. Backfill explicitly (8.4's local real run already wrote state from 2026-08-25): `gh workflow run ownership.yml -f since=2024-12-18 -f until=2026-08-24`; expect 20-40 min. If it times out, split by quarter with `since`/`until` — merges are idempotent.
5. `gh workflow run ownership.yml -f rebuild=true` once, so every issuer/investor doc reflects full history.

Acceptance criteria
- [ ] `ownership.yml` has `permissions: contents: read`, `concurrency: ownership`, no commit step, no `pull_request_target`; `ingest.yml` is unchanged.
- [ ] Dry-run workflow green; its log has the dry-run summary and no `BEGIN PRIVATE KEY` or `user@domain` strings.
- [ ] Backfill green; `ownership/feed.counts.filings` ≥ 5,000 and `counts.issuers` ≥ 1,500; the earliest `filed_at` in the parquet is within a week of 2024-12-18.
- [ ] Rebuild green with a printed write count < 15,000.
- [ ] The next daily run (scheduled, or a default manual run the next day) is green in < 5 min with a write count < 300.

#### Milestone 8.6 — Web
Status: not started

Tasks
1. `web/src/ownershipTypes.ts` (new; `types.ts` stays untouched and under 300 lines): `OwnershipEventKind = 'NEW' | 'INCREASED' | 'DECREASED' | 'EXITED' | 'SWITCHED_TO_13D' | 'SWITCHED_TO_13G' | 'UPDATED' | null`, `OwnershipForm = '13D' | '13G'`, `OwnershipPriority = 'HIGH' | 'MEDIUM' | 'LOW'`, `OwnershipEvent`, `OwnershipStake`, `OwnershipFeed`, `OwnershipIssuer`, `OwnershipInvestor`, `OwnershipFilter = 'all' | '13d' | '13g' | 'new' | 'increased' | 'decreased' | 'activists'` — fields exactly as the Firestore table.
2. `web/src/data.ts`: `getOwnershipFeed()`, `getOwnershipIssuer(symbol)` (`encodeURIComponent`), `getOwnershipInvestor(cik)`.
3. `web/src/ownership.ts` (pure): `filterEvents(events, filter, query)` (query matches `symbol`, `issuerName`, `investorName`, case-insensitive), `eventLabel(e)` (`"NEW 13D"`, `"INCREASED"`, `"SWITCHED TO 13D"`, `"—"` for null), `EVENT_COLORS`, `FORM_COLORS`, `investorHref(e)` (`/manager/{cik}` when `isRoster`, else `/investor/{cik}`). `web/src/ownership.test.ts` in the `format.test.ts` style: every tab, a query match, a label per kind, both hrefs.
4. `web/src/components/ownership/`: `FormBadge.tsx`, `EventBadge.tsx` (the `SideBadge` pattern), `EventsTable.tsx` (props `events`, `hideInvestor?`, `hideIssuer?`; `useSortableRows` keyed on `filedAt`; columns Filed · Investor (link) · Ticker (link to `/stock/:symbol`) · Form · Event · Own % · Change (pp) · SEC (external, `rel="noopener noreferrer"`); `HIGH` rows get a left accent border; `purpose` in a native `<details>` like `OptionsGroups`), `StakesTable.tsx`.
5. `web/src/pages/OwnershipPage.tsx`: `useAsyncData(getOwnershipFeed)`; three `StatTile`s from the rows (filings in the 7 days up to `lastFiledAt`, `NEW` 13Ds, activist entries); `Tabs` with the seven filters; `Input` search; `EventsTable`; `?filter=` and `?q=` in the URL via `useSearchParams` (the `?period=` pattern).
6. `web/src/pages/InvestorPage.tsx`: `useAsyncData(getOwnershipInvestor(cik))`; header (name, cluster `Badge`, "13F profile" link to `/manager/:cik` when `isRoster`); "Current stakes" (`StakesTable`); "Filings" (`EventsTable hideInvestor`).
7. `web/src/components/stock/MajorShareholders.tsx`: `StockPage` adds a second `useAsyncData(getOwnershipIssuer(symbol))` and renders a "Major Shareholders (13D/G)" `<section>` after "Holders" (`StakesTable` + `EventsTable hideIssuer`); nothing when the doc is null.
8. `web/src/components/manager/OwnershipFilings.tsx`: `ManagerPage` adds a second `useAsyncData(getOwnershipInvestor(cik))` **outside** the `mqState.data` block; a callout "{n} ownership filings since the {quarterLabel(latest)} 13F" (`n` = events with `filedAt > manager.periods.at(-1)`), then `StakesTable` + `EventsTable hideInvestor`; nothing when null.
9. `App.tsx`: routes `/ownership`, `/investor/:cik`; `Header.tsx` `NAV_LINKS` + `{ to: '/ownership', label: 'Ownership' }`.
10. `npm run lint`, `npm run test`, `npm run build`, `npm run dev` click-through. Commit `feat: ownership feed, investor page, 13D/G sections`; push (deploy runs).

Acceptance criteria
- [ ] `npm run test` green incl. `ownership.test.ts` (≥ 6 tests); `npm run build` and `npm run lint` clean; no `any`, no `console.log`; every new file ≤ 300 lines; `types.ts` unchanged.
- [ ] `/ownership` renders from one Firestore read beyond `meta/latest`; tabs and search filter without re-fetching; `?filter=13d&q=elliott` restores the state on load.
- [ ] From a `HIGH` row: the ticker link opens `/stock/:symbol` with "Major Shareholders (13D/G)" showing the same investor and %; a roster investor link opens `/manager/:cik` with "Ownership Filings" and the "since the … 13F" callout; a non-roster investor link opens `/investor/:cik`.
- [ ] `/manager/1791786` lists Elliott's Triple Flag stake (64.7 % at planning time); `/stock/PINS` lists Elliott at 5.8 % under Major Shareholders (re-verify against the SEC link on the row if the numbers moved).
- [ ] A 13F-only stock with no ownership doc shows no Major Shareholders section and no error.
- [ ] At 375 px, `/ownership` and `/investor/:cik` have no page-level horizontal scroll.
- [ ] Deploy green; the live site shows the "Ownership" nav entry.

#### Milestone 8.7 — Docs sync
Status: not started

Tasks
1. `CLAUDE.md`: "Where logic lives" → 13F signal math in `ingest/derive.py`, 13D/13G event math in `ingest/ownership_derive.py`, thresholds for both in `signals_config.json`; Commands + `python ownership.py --dry-run`; the `print()` exception covers `ingest.py` and `ownership.py`; new "13D/13G gotchas": only `SCHEDULE 13D/G` (structured, from 2024-12-18), never `SC 13D/G`; the index lists a filing once per associated CIK — dedupe by accession and never treat the index CIK as the filer; filer CIK, amendment number and previous accession come from the XML `headerData`; `total_percent` is a max, not a sum; amendments **are** the data (the opposite of the 13F `13F-HR/A` rule); no prior filing in our log ⇒ event `null`, never `NEW`; a dry run must not write state; `GCS_BUCKET` is required; write only touched docs (20K writes/day).
2. `README.md`: new section after "Managers tracked" — **Ownership filings (13D and 13G)** in the house style: what a 13D is, what a 13G is, the 5% rule, why a 13D matters more, events start on 2024-12-18, only tracked managers' 13G are shown, one line per event kind. Add `/ownership` and `/investor/:cik` to "How it works".
3. `docs/ARCHITECTURE.md`: add the ownership chain to both diagrams.
4. This file: set 8.1-8.7 `Status: done <sha>`, check every box, extend "Verification (end to end)" with the ownership dry run, the feed page, and the daily workflow.
5. Commit `docs: milestone 8 — 13D/13G ownership monitor`.

Acceptance criteria
- [ ] Every sentence in the new README section is ≤ ~20 words and a non-developer can tell 13D from 13G after reading it.
- [ ] `CLAUDE.md` no longer says all signal math lives in `derive.py`.
- [ ] Fresh clone: `pytest ingest` and `npm run test` green with no `.env`.
- [ ] `git log -p | Select-String -Pattern "@gma[i]l|AIza[0-9A-Za-z_-]{20}|-----BEG[I]N|private[_]key"` returns nothing.
- [ ] All 8.x boxes in this file are checked.

**Stop and ask the user when (Milestone 8):** the installed edgartools cannot build `Schedule13D`/`Schedule13G` from an XML string; `get_filings` returns zero rows for a window that should have filings, or the form names differ from `FORMS`; the dry run's unmatched-filer print shows a roster manager under a CIK not in `aliases` (report, do not guess); any Firestore/GCS permission error, or a run's write count above 15,000; the backfill exceeds 120 minutes even split by quarter; a parsed value contradicts the SEC page during a spot-check (ask before "fixing"); anything seems to need a new dependency.

---

## Doc specs

### README.md (humans)
Style: simple English. Short sentences. One idea per sentence. No run-on sentences. Explain a term the first time it appears.
Tone sample: "This site shows what big investors own. The data comes from SEC Form 13F filings. Funds file them every quarter."

Sections, in order:
1. **What this is** — 3 sentences.
2. **What 13F data is (and is not)** — bullets: quarterly; up to 45 days late; long positions only; no shorts; no cash; options are reported but puts are not shorts; values in dollars; **not investment advice**.
3. **Managers tracked** — 11 names, one line each with the person behind it and the cluster label.
4. **The signals** — one plain sentence per signal (13), e.g. "Consensus Buys: stocks that two or more managers bought or added in the same quarter."
5. **How it works** — the architecture block, then 4 short sentences. Say signals are computed once per quarter, not live.
6. **Set up your own copy** — Manual setup 1–9 in plain words. Say which values are secret and which are public.
7. **Run locally** — exact commands for `ingest/` and `web/`. PowerShell first, then bash.
8. **Add a manager** — edit `ingest/funds.json`, verify the CIK, run the ingest workflow.
9. **Tuning the signals** — `ingest/signals_config.json`, one line per knob.
10. **Sector data** — coarse (SIC ranges); where to improve.
11. **License** — MIT.

The live site URL lives in the GitHub repo's own "website" field (repo Settings → homepage), not duplicated in the README.

### CLAUDE.md (dev agent; AGENTS.md is a symlink to it)
1. **Project** — 2 lines. "Read `docs/PLAN.md` first. Work one milestone at a time, in order. Do not start the next milestone until every AC box is checked."
2. **Stack** — Python 3.12 + edgartools + pandas + firebase-admin; Vite + React + TS + react-router + Tailwind v4 + shadcn/ui (5 components) + Recharts + Firebase JS; Firestore + GCS + Firebase Hosting; GitHub Actions.
3. **Commands** — ingest: venv, `pip install -r requirements.txt`, `pytest`, `python ingest.py --dry-run`; web: `npm i`, `npm run dev`, `npm run test`, `npm run build`; firebase: `npx firebase-tools deploy --only firestore:rules`. Dev machine is Windows / PowerShell.
4. **Public repo rules** — the secrets table; never commit `.env` or key files; never print secrets; key file lives outside the repo.
5. **Where logic lives** — all signal math in `ingest/derive.py`, thresholds in `ingest/signals_config.json`; the browser only formats and renders; the Firestore doc shapes in `docs/PLAN.md` are the contract between the two.
6. **Conventions** — files under ~300 lines; Python: typed pure functions in `derive.py`, no network in tests; TS strict; shadcn components only via `npx shadcn add` and only the 5 listed; no new dependency without adding it to `docs/PLAN.md` first; no `console.log` / debug prints in committed code.
7. **Git** — commit directly to `main`; conventional messages; run the milestone checks before committing; update the milestone `Status:` line in `docs/PLAN.md`.
8. **13F gotchas** — `putCall` is the option side; options use the underlying's CUSIP; puts are "Reported Put Exposure", never "short"; values are dollars since 2023; use `13F-HR` not `13F-HR/A`; status uses shares, change uses weight; edgartools column names vary — print and map.
9. **Stop and ask the user when** — a CIK name does not match; edgartools columns differ from the plan; any GCP permission error; a new dependency seems needed; any step needs the Firebase/GCP console; a signal definition in the plan is ambiguous.

## Reuse (do not re-implement)
- 13F fetching/parsing: `edgartools`. Aggregation: `pandas`. Cosine: `numpy` (comes with pandas).
- 13D/13G listing and parsing: `edgartools` (`get_filings`, `edgar.beneficial_ownership.Schedule13D` / `Schedule13G`). XML header fields: stdlib `xml.etree`. No new dependency.
- Firestore + GCS: `firebase-admin` (Python), `firebase` (JS). Hosting deploy: `FirebaseExtended/action-hosting-deploy`.
- UI: shadcn/ui (table, tabs, badge, input, select). Charts: `recharts`. Heatmap: CSS grid, no library.

## Verification (end to end)
1. `pytest ingest` and `npm run test` green.
2. `python ingest/ingest.py --dry-run` → 11 managers × 4 quarters with tickers, sectors, and printed signal previews.
3. Full local run → Firestore docs and GCS objects as listed in Milestone 3 AC.
4. `npm run dev` → `/patterns`, `/managers`, `/manager/:cik`, `/stock/:symbol` all render from one read each; links cross-navigate; search works; 375 px has no page-level horizontal scroll.
5. Push to `main` → deploy green → site live → custom domain over HTTPS.
6. Manual ingest run → green; logs contain no secret values.
7. `git log -p` passes the secret scan.

## Skipped on purpose (add when…)
- **Per-user manager selection / re-filtering** — signals are precomputed over all 11 managers; add a client-side re-aggregation when someone actually asks to exclude a manager.
- **Citadel / Millennium** — removed by the user; re-add only as manager pages with an `excludeFromSignals` flag.
- **Auto-clustering, Jaccard / sector similarity** — cosine + manual labels first.
- **Auth, Cloud SQL, BigQuery** — public data; BigQuery is one command over the Parquet when SQL is wanted.
- **More than 4 quarters** — `--quarters 8` already works; UI trend charts just get more points.
- **13F-HR/A amendments, split adjustment, GICS sectors** — when the inaccuracy actually bites.
- **More shadcn components** — only when a listed view cannot be built with the 5.
- **Legacy `SC 13D` / `SC 13G` text filings (pre 2024-12-18)** — need an HTML/text parser; structured XML only for now.
- **Universe-wide 13G** — drop the roster filter in `ownership_fetch.list_filings` and add a passive-giant exclusion list (Vanguard, BlackRock, State Street, …) when wanted.
- **Item 4 purpose classification, feed pagination** — the purpose text is shown verbatim (truncated); the feed is one doc of `recent_events` rows.
