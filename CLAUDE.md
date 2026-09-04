# CLAUDE.md — instructions for the dev agent

## Project

A public dashboard of SEC 13F holdings for a tracked list of hedge fund managers (see `ingest/funds.json`), with signals derived across managers, stocks, sectors, and quarters.

**Read `docs/PLAN.md` first.** Work one milestone at a time, in order. Do not start the next milestone until every acceptance-criteria box of the current one is checked. `docs/ARCHITECTURE.md` has diagrams of the system and the data pipeline.

## Stack

- Ingest: Python 3.12, edgartools, pandas, firebase-admin, google-cloud-storage.
- Web: Vite, React, TypeScript, react-router-dom, Tailwind v4, shadcn/ui (table, tabs, badge, input, select — nothing else), Recharts, Firebase JS SDK.
- Data: Firestore (derived documents the site reads), Google Cloud Storage (raw XML + Parquet), Firebase Hosting.
- CI: GitHub Actions — monthly ingest cron (idempotent; catches late filers) and deploy on push to `main`.

## Commands

The dev machine is Windows / PowerShell. Local Python is 3.10; CI uses 3.12. Write code that runs on both (no 3.11+-only syntax). Local Node is 24; CI uses 22.

```powershell
# ingest
cd ingest
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
ruff format .
ruff check .
python ingest.py --dry-run
python ownership.py --dry-run

# web
cd web
npm install
npm run dev
npm run test
npm run build

# firebase (repo root, one-time, user runs it)
npx firebase-tools deploy --only firestore:rules
```

## Public repo rules

This repository is PUBLIC.

| Name | Kind | Where |
|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT` | secret | GitHub Actions secret only |
| `EDGAR_IDENTITY` | secret (it is the user's email) | GitHub secret + `ingest/.env` |
| `OPENFIGI_API_KEY` | secret | GitHub secret + `ingest/.env` |
| `GCS_BUCKET`, `FIREBASE_PROJECT_ID` | public variable | GitHub variable + `.env` |
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | public variable | GitHub variables + `web/.env` |

- Never commit `.env` or any key file. `.gitignore` covers them; do not weaken it.
- Never print, log, or echo a secret. Not in scripts, not in workflows.
- The service-account key file lives OUTSIDE the repo (for example `~/keys/13f-sa.json`). Point `GOOGLE_APPLICATION_CREDENTIALS` at it.
- The `VITE_FIREBASE_*` values are public identifiers, not secrets. Access is controlled by `firestore.rules`.
- Workflows use `push`, `schedule`, and `workflow_dispatch` only. Never `pull_request_target`. `permissions: contents: read`, except `ingest.yml` which needs `contents: write` for its keepalive commit (see `docs/PLAN.md`, Milestone 6).

## Where logic lives

- 13F signal math: `ingest/derive.py`. 13D/13G event math: `ingest/ownership_derive.py`. Thresholds and score constants for both: `ingest/signals_config.json`.
- The browser only formats and renders. It never computes a signal.
- The Firestore document shapes in `docs/PLAN.md` are the contract between Python and TypeScript. If a shape must change, change the plan first, then both sides.

## Conventions

- Files under ~300 lines. Split before they grow past that. Exception: `ingest/derive.py` — "Where logic lives" above requires all signal math in one file so it stays auditable as a single unit; it runs longer (11 focused functions, one per table) instead of being fragmented across a package.
- Python: typed functions. `derive.py` functions are pure (DataFrame in, DataFrame out). No network calls in tests.
- TypeScript: strict mode. No `any`.
- shadcn components are added only with `npx shadcn@latest add <name>`, and only the 5 listed. Never hand-copy component code.
- No new dependency without adding it to `docs/PLAN.md` first.
- No `console.log`, `print()` debugging, or commented-out code in commits. (`ingest.py` and `ownership.py` print their dry-run summaries on purpose; that is output, not debugging.)
- Match the naming in `docs/PLAN.md` exactly: function names, document ids, field names.
- Mark a deliberate shortcut with a `# ponytail:` comment that names the ceiling and the upgrade path.

## Git

- Commit directly to `main`. No branches needed.
- Conventional messages: `feat:`, `fix:`, `docs:`, `ci:`, `test:`, `chore:`.
- Run the milestone's checks before every commit.
- When a milestone is done: check its boxes and set its `Status:` line in `docs/PLAN.md` to `done <short sha>` in a small follow-up `docs:` commit.

## 13F gotchas

- `putCall` marks an option row: `PUT` or `CALL`. Blank means shares.
- Options are reported under the underlying stock's CUSIP.
- Puts are "Reported Put Exposure". Never label them "short".
- Values are in dollars for filings since 2023. Older filings used thousands.
- Use form `13F-HR`. Ignore `13F-HR/A` (amendments) for now.
- Position status (NEW / ADDED / TRIMMED / UNCHANGED / SOLD_OUT) uses **shares**. Weight change uses **portfolio weight**.
- A manager with no filing in the previous quarter gets `status = null`, not `NEW`.
- edgartools column names vary between versions. Print `df.columns` once and map them explicitly.

## 13D/13G gotchas

- Only `SCHEDULE 13D` / `SCHEDULE 13D/A` / `SCHEDULE 13G` / `SCHEDULE 13G/A` — the structured-XML forms, mandatory since 2024-12-18. Never the legacy `SC 13D` / `SC 13G` text filings.
- EDGAR's index lists a filing once per associated CIK (subject company + every filer). Dedupe by accession, and never treat the index row's CIK as the filer.
- The filer CIK, amendment number, and previous accession come from the filing's XML `headerData`, not from anything `edgartools`' `Schedule13D`/`Schedule13G` objects expose.
- `total_percent` / `total_shares` are the **max** across reporting persons, never a sum — nested entities in one filing report the same aggregate.
- Amendments **are** the data here — the opposite of the 13F `13F-HR/A` rule. Every amendment changes the position.
- No prior filing in our log for that `(investor, cusip)` pair ⇒ event `null`, never `NEW` — same idea as `status = null` in the 13F table.
- `ownership.py --dry-run` must not advance state (no GCS or Firestore writes at all) — unlike `ingest.py`, which still archives to GCS on a dry run.
- `GCS_BUCKET` is required for the ownership pipeline; it has no "skip archive" fallback.
- Each run rewrites `ownership/feed` and only the issuer/investor docs touched by that run's new filings (Firestore's free tier is 20K writes/day) — use `--rebuild` to force every doc.

## Adding a manager

No code changes — it's data-driven end to end.

1. Find their 10-digit CIK on [EDGAR full-text search](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany).
2. Add one entry to `ingest/funds.json`: `{ "cik": "...", "name": "Exact EDGAR filer name", "short": "ShortName", "cluster": "Some Label" }`.
   `cluster` is freeform — reuse an existing label or start a new one; `clusters()` in `derive.py` just groups by whatever's there.
   Optional `"aliases": ["cik", ...]` lists other CIKs the same firm files 13D/13G under (Elliott and Icahn each use several). To find them, run `python ownership.py --dry-run` and read its "unmatched filers that look like roster names" print.
3. `python ingest.py --dry-run` first — check the new manager's top-10 holdings and PUT/CALL counts print sanely — then a real run.
4. Nothing else to touch: every signal in `derive.py` iterates `funds` from `funds.json`, so consensus, similarity, sector rotation, etc. pick the new manager up automatically on the next ingest.

## Stop and ask the user when

- A CIK's EDGAR name does not match the manager in `ingest/funds.json`.
- edgartools columns differ from what the plan expects.
- Any GCP or Firebase permission error.
- A new dependency seems needed.
- A step needs the Firebase or GCP console.
- A signal definition in the plan is ambiguous.
