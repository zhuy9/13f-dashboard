# 13F Signals Dashboard — Implementation Plan (MVP)

> Planning + documentation: the planning model. Development: a cheaper model, one milestone at a time.
> This file is the single source of truth for the dev model.
> Every milestone has numbered tasks and a checkbox list of acceptance criteria (AC). A milestone is done only when every AC box is checked.

## Context

Build a public web dashboard of SEC Form 13F holdings for 11 well-known conviction managers.
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
| Managers | 11, all in the signal set: Berkshire, Pershing Square, TCI, Baupost, Appaloosa, Duquesne, Coatue, Tiger Global, Viking, Lone Pine, Third Point. Cluster labels are manual (in `funds.json`). |
| History | Last **4 quarters** per manager. QoQ status on quarters that have a prior quarter in the window. |
| Frontend | Vite + React + TS + **react-router-dom** + **Tailwind v4 + shadcn/ui** (5 components) + Recharts + Firebase JS. Pages: `/patterns`, `/managers`, `/manager/:cik`, `/stock/:symbol`. No auth. No per-user manager selection in MVP. |
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

GitHub Actions (on push to main, paths web/**) ──► npm run build ──► Firebase Hosting ──► custom domain

Browser: one Firestore read per page (signals/{period}, manager_quarters/{cik}_{period}, stocks/{symbol}) + meta/latest once.
```

## Repo layout

```
13f/
  README.md  CLAUDE.md  AGENTS.md -> CLAUDE.md  LICENSE  .gitignore
  docs/PLAN.md
  data/last_ingest.json          # written and committed by the ingest workflow
  firebase.json  .firebaserc  firestore.rules
  .github/workflows/ingest.yml  .github/workflows/deploy.yml
  ingest/
    requirements.txt  funds.json  signals_config.json  .env.example
    ingest.py      # CLI + orchestration only
    fetch.py       # edgartools fetch + normalize
    enrich.py      # OpenFIGI + SEC lookups + securities cache
    sectors.py     # SIC → sector
    derive.py      # all derived tables (pure pandas, no I/O)
    store.py       # GCS + Firestore writes
    test_fetch.py  test_derive.py  test_sectors.py
    fixtures/holdings_small.csv
  web/
    package.json  vite.config.ts  tsconfig.json  tsconfig.app.json  index.html  components.json  .env.example
    src/
      main.tsx  App.tsx  index.css  firebase.ts  types.ts  format.ts  format.test.ts
      data.ts                       # Firestore reads (one function per doc type)
      lib/utils.ts                  # shadcn cn()
      components/ui/*               # shadcn-generated only: table, tabs, badge, input, select
      components/Header.tsx  SymbolSearch.tsx  StatusBadge.tsx  SideBadge.tsx  SectorBars.tsx  Heatmap.tsx
      pages/PatternsPage.tsx  ManagersPage.tsx  ManagerPage.tsx  StockPage.tsx
      pages/patterns/*.tsx          # one small component per signal table
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
             "accumulation_scale": 0.02, "accumulation_cap": 3 } }
```

## Firestore documents (what the browser reads)

| Doc | Content | Read by |
|---|---|---|
| `meta/latest` | `latestPeriod, periods[], managers[{cik, short, name, cluster}], clusters[{label, members, commonHoldings, topSector}], symbols[{symbol, name}], updatedAt` | every page, once |
| `managers/{cik}` | `cik, name, short, cluster, periods[]` | manager page |
| `manager_quarters/{cik}_{period}` | `filedAt, totalValue, count, counts{new,added,trimmed,unchanged,soldOut}, positions[A rows incl. SOLD_OUT], sectors[B rows], mostSimilar[{cik, short, score}]` | manager page |
| `stocks/{symbol}` | `symbol, name, sector, trend[D rows], latest{C summary + holders + soldOut + options{calls[], puts[]}}` | stock page |
| `signals/{period}` | all E tables, F, G (`ciks[]`, `matrix[][]`), H (symbols with options only) | patterns page |
| `securities/{cusip}` | enrichment cache (ingest only) | — |

Every doc stays far under 1 MB (largest: `signals` ≈ 100 KB, `meta` ≈ 100 KB). Rules: public read, no client write.

### GCS layout (when `GCS_BUCKET` is set)
```
raw/<cik>/<period>/infotable.xml
parquet/holdings/<period>.parquet
parquet/<table>/<period>.parquet        # one per derived table A–H
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
GCS uploads fail gracefully (404, bucket `form-13f-dashboard` not created yet — Manual setup step 3,
pending) and don't block the Firestore write, per the try/except-per-object design.

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
- [ ] GCS has `raw/` and `parquet/` for every table and period. **Blocked**: bucket `form-13f-dashboard` doesn't exist yet (Manual setup step 3). Uploads fail gracefully and don't block the rest of the run; re-run `ingest.py` after the bucket is created to fill this in.
- [x] `signals/{latestPeriod}` and `meta/latest` each < 300 KB (check in console). (34.5 KB and 27.8 KB.)
- [x] Spot-check one manager in the console against a public 13F source: top holding and its weight agree within rounding. (Berkshire top holding AAPL at 22.0% weight, matches public 13F trackers.)

### Milestone 4 — Web app shell, manager page, stock page
Status: not started

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
- [ ] `src/components/ui/` contains exactly `table tabs badge input select` (+ `lib/utils.ts`).
- [ ] `npm run test` green; `npm run build` zero TS errors.
- [ ] `/manager/1067983` shows Berkshire: treemap, sector bars and QoQ table, positions with statuses, four lists, similar managers; period `Select` switches quarters.
- [ ] `/stock/AAPL` shows the summary tiles, holders with status, options groups (may be empty), and both trend charts with 4 points.
- [ ] Header search: typing `nvd` offers NVDA; Enter opens `/stock/NVDA`.
- [ ] Clicking a symbol on a manager page opens the stock page; clicking a manager on a stock page opens the manager page.
- [ ] At 375 px wide nothing scrolls horizontally except inside tables.
- [ ] Wrong `VITE_FIREBASE_PROJECT_ID` shows a visible error, not a blank page.

### Milestone 5 — Patterns page and managers page
Status: not started

Tasks
1. `PatternsPage.tsx`: loads `signals/{latestPeriod}` (period `Select` in the header of the page); sticky in-page nav with anchors to 10 sections; each section is one small component in `pages/patterns/`:
   `ConsensusBuys`, `ConsensusExits`, `HighConviction`, `BiggestNew`, `BiggestAdds`, `BiggestTrims`, `SectorRotation` (table + horizontal bar chart of avg change, positive/negative colored), `FastestGrowing`, `ManagerSimilarity` (`Heatmap.tsx`: CSS-grid matrix with color intensity, plus "most similar" lists), `PutCallExposure` (table: symbol, equity count, calls count, puts count; `<details>` to expand manager names).
   Every symbol links to `/stock/:symbol`; every manager links to `/manager/:cik`.
2. `ManagersPage.tsx`: clusters from `meta.clusters`: label, members (links), common holdings (links), top sector.
3. Commit `feat: patterns page and managers page`.

Acceptance criteria
- [ ] `/patterns` renders all 10 sections from one Firestore read (check the network tab: 1 `signals` doc + `meta`).
- [ ] Tables show the columns listed in "Consensus tables"; sort order matches.
- [ ] Sector rotation bar chart colors positive and negative moves differently.
- [ ] Heatmap: diagonal is 1.00; hovering a cell shows both manager names and the value.
- [ ] Put/Call section: expanding a row lists manager names per group; puts are labelled "Reported Puts", never "short".
- [ ] `/managers` groups all 11 managers by cluster with common holdings and top sector.
- [ ] `npm run build` zero TS errors; `npm run test` green.

### Milestone 6 — CI/CD and custom domain
Status: not started

Prerequisite: Manual setup 1–7 done (secrets and variables exist on GitHub).

Tasks
1. `.github/workflows/deploy.yml`: `on: push: branches: [main], paths: [web/**, firebase.json, .github/workflows/deploy.yml]` + `workflow_dispatch`; `permissions: contents: read`; checkout → `actions/setup-node@v4` (node 22, `cache: npm`, `cache-dependency-path: web/package-lock.json`) → `npm ci` + `npm run build` in `web/` with `env:` `VITE_FIREBASE_*` from `vars` → `FirebaseExtended/action-hosting-deploy@v0` (`firebaseServiceAccount: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}`, `channelId: live`, `projectId: ${{ vars.FIREBASE_PROJECT_ID }}`).
2. `.github/workflows/ingest.yml`: `on: schedule: - cron: "0 13 16 * *"` (monthly on the 16th — re-running a quarter is idempotent and catches late filers) + `workflow_dispatch` (inputs `fund`, `dry_run`); `permissions: contents: write` (needed only for task 3); `concurrency: ingest`; checkout → `actions/setup-python@v5` (3.12, `cache: pip`) → `pip install -r ingest/requirements.txt` → write secret to `$RUNNER_TEMP/sa.json` from an `env:` var → `python ingest/ingest.py` with `env:` `GOOGLE_APPLICATION_CREDENTIALS`, `EDGAR_IDENTITY`, `OPENFIGI_API_KEY`, `GCS_BUCKET` and the optional flags.
3. Keepalive: GitHub disables scheduled workflows in a public repo after 60 days without repository activity, so the workflow must create activity. On a real (non-dry) run, `ingest.py` writes `data/last_ingest.json` (`{period, ranAt, managers}`); a final workflow step commits it as `chore: ingest <period>` using the `github-actions[bot]` identity and pushes with `GITHUB_TOKEN`. Skip the commit when the file is unchanged. `deploy.yml`'s `paths` filter already ignores `data/**`, so this commit does not trigger a deploy.
4. Commit `ci: deploy on push and monthly ingest`. Push.
5. User adds the custom domain (Manual setup 8). Update README "Live site". Commit `docs: live site link`.

Acceptance criteria
- [ ] Push to `main` → deploy green → `https://<project>.web.app` shows live data.
- [ ] Ingest "Run workflow" with `dry_run=true` → green; log has 11 manager summaries and **no** secret values (search the log for `BEGIN PRIVATE KEY` and `@`).
- [ ] Ingest with `dry_run=false` → green; `meta/latest.updatedAt` changed; run time < 30 min.
- [ ] Custom domain serves the site over HTTPS.
- [ ] `deploy.yml` has `permissions: contents: read`; `ingest.yml` has `permissions: contents: write` and nothing more; no `pull_request_target` anywhere.
- [ ] After a real run, a `chore: ingest <period>` commit containing `data/last_ingest.json` appears on `main`, and it did not trigger a deploy.

### Milestone 7 — Docs sync and final check
Status: not started

Tasks
1. Re-read `README.md` and `CLAUDE.md` against what was built; fix any command or path that changed. Split any sentence over ~20 words.
2. Mark every milestone `done <sha>` in `docs/PLAN.md`.
3. Commit `docs: sync docs with implementation`.

Acceptance criteria
- [ ] A fresh clone + README alone gets a new user to a running local dashboard.
- [ ] `git log -p | Select-String -Pattern "@gma[i]l|AIza[0-9A-Za-z_-]{20}|-----BEG[I]N|private[_]key"` returns nothing.
- [ ] All milestone AC boxes in `docs/PLAN.md` are checked.

---

## Doc specs

### README.md (humans)
Style: simple English. Short sentences. One idea per sentence. No run-on sentences. Explain a term the first time it appears.
Tone sample: "This site shows what big investors own. The data comes from SEC Form 13F filings. Funds file them every quarter."

Sections, in order:
1. **What this is** — 3 sentences.
2. **Live site** — link (TBD until Milestone 6).
3. **What 13F data is (and is not)** — bullets: quarterly; up to 45 days late; long positions only; no shorts; no cash; options are reported but puts are not shorts; values in dollars; **not investment advice**.
4. **Managers tracked** — 11 names, one line each with the person behind it and the cluster label.
5. **The signals** — one plain sentence per signal (13), e.g. "Consensus Buys: stocks that two or more managers bought or added in the same quarter."
6. **How it works** — the architecture block, then 4 short sentences. Say signals are computed once per quarter, not live.
7. **Set up your own copy** — Manual setup 1–9 in plain words. Say which values are secret and which are public.
8. **Run locally** — exact commands for `ingest/` and `web/`. PowerShell first, then bash.
9. **Add a manager** — edit `ingest/funds.json`, verify the CIK, run the ingest workflow.
10. **Tuning the signals** — `ingest/signals_config.json`, one line per knob.
11. **Sector data** — coarse (SIC ranges); where to improve.
12. **License** — MIT.

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
