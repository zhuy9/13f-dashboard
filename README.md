# Consensus Sheet

## What this is

This site shows what big investors own. The data comes from SEC Form 13F filings. It also finds patterns across managers, like which stocks many of them are buying at the same time.

## Live site

[https://form-13f-dashboard.web.app](https://form-13f-dashboard.web.app)

A custom domain is not set up yet. This link will move there once it is (Manual setup step 8).

## What 13F data is (and is not)

A 13F is a report. Large US investment managers must file it with the SEC every quarter.

- It shows long positions in US stocks. A long position means the manager owns the stock.
- It does not show short positions. A short position is a bet that a stock will fall.
- It does not show cash, bonds, or most foreign stocks.
- It can be filed up to 45 days after the quarter ends. So the data is always a little old.
- It includes options. A put option is not the same as a short. We label puts as "Reported Puts".
- Values are in US dollars.
- This site is not investment advice.

## Managers tracked

| Manager | Person | Style label |
|---|---|---|
| Berkshire Hathaway | Warren Buffett | Value / Quality |
| Pershing Square | Bill Ackman | Activist / Quality |
| TCI Fund Management | Chris Hohn | Quality / Compounders |
| Baupost Group | Seth Klarman | Value / Event Driven |
| Appaloosa | David Tepper | Macro / Value |
| Duquesne Family Office | Stanley Druckenmiller | Macro |
| Coatue Management | Philippe Laffont | Tech / Growth |
| Tiger Global | Chase Coleman | Tech / Growth |
| Viking Global | Andreas Halvorsen | Tech / Growth |
| Lone Pine Capital | Steve Mandel | Tech / Growth |
| Third Point | Dan Loeb | Event Driven / Activist |

The style labels are set by hand. You can change them in `ingest/funds.json`.

## The signals

The site computes these signals once per quarter.

1. **Manager Conviction.** How big each stock is inside a manager's portfolio, and how that changed since last quarter.
2. **Stock Consensus.** How many managers own a stock, and how much of their portfolio it is.
3. **Consensus Buys.** Stocks that two or more managers bought or added in the same quarter.
4. **Consensus Exits.** Stocks that two or more managers sold or trimmed in the same quarter.
5. **High-Conviction Overlap.** Stocks that three or more managers hold at 3% or more of their portfolio.
6. **Conviction Score.** A score from 0 to 100. It rewards stocks that a few managers hold in big size and just bought.
7. **Sector Exposure.** How much of each manager's portfolio is in each sector, and how that changed.
8. **Sector Rotation.** Which sectors managers are moving into or out of, as a group.
9. **Manager Similarity.** How alike two managers' portfolios are, from 0 to 1.
10. **Manager Clusters.** Managers grouped by style, like "Tech / Growth".
11. **Ownership Change.** How the number of managers holding a stock changed over time.
12. **Position-Weight Trend.** How the average portfolio weight of a stock changed over time.
13. **Put / Call Exposure.** Which managers report puts or calls on a stock. This is kept separate from stock holdings.

## How it works

```
GitHub Actions (once a month, or by hand)
  └─ ingest/ingest.py (Python)
       ├─ fetch   : SEC EDGAR → last 4 quarters of 13F filings per manager
       ├─ enrich  : CUSIP → ticker (OpenFIGI) → sector (SEC industry code)
       ├─ derive  : all 13 signals
       └─ store   : Google Cloud Storage (files) + Firestore (documents the site reads)

GitHub Actions (on every push to main)
  └─ build the site → Firebase Hosting → your domain
```

A script runs once a month. It downloads the latest filings and computes every signal. It writes the results to Firestore. The website only reads and displays them. Nothing is computed live.

Each run also saves a small file, `data/last_ingest.json`, into the repo. It shows when the data was last updated. It also keeps the schedule alive. GitHub turns off schedules in repos with no activity for 60 days.

For diagrams of the full system and the data pipeline, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Set up your own copy

You need a Google account and a GitHub account. Some values are **secret**. Never put a secret in the code.

1. Go to the Firebase console. Create a project. Turn on **Firestore** (Native mode) and **Hosting**.
2. In Project settings, add a **Web app**. Copy the `API key`, `project ID`, and `app ID`. These three values are **public**. Put them in `web/.env` and in your GitHub repository **Variables**.
3. Upgrade the project to the **Blaze** plan. This turns on billing. Normal use stays inside the free tier. Set a budget alert at $5 to be safe. Create a Cloud Storage bucket. Put its name in the `GCS_BUCKET` variable.
4. In Google Cloud IAM, create a service account. Give it the **Firebase Admin** and **Storage Object Admin** roles. Create a JSON key. This key is **secret**. Paste the whole file into a GitHub secret named `FIREBASE_SERVICE_ACCOUNT`. Keep a copy outside the repo for local runs.
5. Get a free API key from openfigi.com. This is **secret**. Save it as the GitHub secret `OPENFIGI_API_KEY`.
6. The SEC asks for your name and email on every request. Save `Your Name your@email.com` as the GitHub secret `EDGAR_IDENTITY`. This is **secret** because it is your email.
7. Create a public GitHub repository. Push the code. Add the secrets and variables under Settings → Secrets and variables → Actions.
8. In the Firebase console, open Hosting. Add your custom domain. Add the DNS records it shows you at your domain registrar.
9. Run `npx firebase-tools login` once. Then run `npx firebase-tools deploy --only firestore:rules`. This makes the data readable by the site.

## Run locally

PowerShell:

```powershell
cd ingest
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# fill in .env, then:
python ingest.py --dry-run
```

```powershell
cd web
npm install
Copy-Item .env.example .env
# fill in .env, then:
npm run dev
```

bash:

```bash
cd ingest
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env, then:
python ingest.py --dry-run
```

```bash
cd web
npm install
cp .env.example .env
# fill in .env, then:
npm run dev
```

`--dry-run` downloads and computes everything but writes nothing. Drop the flag to write to Firestore.

## Add a manager

1. Find the manager's CIK number on the SEC EDGAR site. The CIK is the SEC's ID for a filer.
2. Add a line to `ingest/funds.json` with the CIK, name, short name, and style label.
3. Run the ingest workflow from the GitHub Actions tab.

## Tuning the signals

Edit `ingest/signals_config.json`. Then run the ingest workflow.

- `quarters` — how many quarters to load. Default 4.
- `consensus_min_managers` — how many managers make a "consensus". Default 2.
- `high_conviction_min_weight` — the portfolio weight that counts as high conviction. Default 0.03 (3%).
- `high_conviction_min_managers` — how many managers make a high-conviction overlap. Default 3.
- `sector_move_threshold` — the sector weight change that counts as a move. Default 0.005 (0.5 points).
- `top_n` — how many rows each ranked table keeps. Default 25.
- `score` — the constants inside the Conviction Score formula. See `docs/PLAN.md` for the formula.

## Sector data

13F filings do not include a sector. We look up each stock's SEC industry code (SIC). Then we map that code to a sector with a short table in `ingest/sectors.py`. This is rough. Some stocks will land in the wrong sector. To improve it, replace the table with a real sector data source.

## License

MIT. See `LICENSE`.
