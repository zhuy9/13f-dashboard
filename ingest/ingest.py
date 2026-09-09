"""CLI: fetch, normalize, and enrich 13F holdings for the tracked managers."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import NamedTuple

import edgar
import firebase_admin
import pandas as pd
from dotenv import load_dotenv
from firebase_admin import firestore

from derive import derive_all
from enrich import attach, ensure_securities
from fetch import (
    BASE_COLUMNS,
    collapse,
    edgar_ticker_hints,
    fetch_filings,
    filed_notice,
    filing_rows,
    normalize,
    resolve_amendments,
)
from store import write_firestore, write_gcs

HERE = Path(__file__).parent


def load_funds() -> list[dict]:
    return json.loads((HERE / "funds.json").read_text())


def load_config() -> dict:
    return json.loads((HERE / "signals_config.json").read_text())


def load_corporate_actions() -> list[dict]:
    """Stock splits, from data, never inferred. A large share change is not evidence of a split,
    so nothing is adjusted without an entry here carrying a source."""
    return json.loads((HERE / "corporate_actions.json").read_text())


class ManagerFetch(NamedTuple):
    """What one manager's fetch produced. A NamedTuple rather than a 5-tuple: the callers index
    these by name, and provenance is the fifth thing a positional tuple would have hidden."""

    base: pd.DataFrame
    ticker_hints: dict[str, str]
    raw_by_filing: dict[tuple, bytes]
    filings: pd.DataFrame
    notes: list[str]


FILING_COLUMNS = ["cik", "period", "accession", "url", "filed_at", "is_amendment", "amendment_type", "filer_cik"]


def fetch_manager(fund: dict, quarters: int) -> ManagerFetch:
    """One manager's filings over the last `quarters` report periods, across every CIK the firm
    files them under.

    Rows from every `aliases13f` CIK carry the roster cik/short, so `collapse` sums a book split
    across filers into one. Amendments are resolved per (filer, period) by `resolve_amendments`
    before any of that: a restatement replaces its original, an additive amendment unions with
    it, and one accession contributes once however many times it is seen."""
    frames = []
    ticker_hints: dict[str, str] = {}
    raw_by_filing: dict[tuple, bytes] = {}
    provenance: list[dict] = []
    notes: list[str] = []
    for cik in [fund["cik"], *fund.get("aliases13f", [])]:
        parsed = [filing_rows(f) for f in fetch_filings(cik, quarters)]
        for period, group in groupby(sorted(parsed, key=lambda f: f.period), key=lambda f: f.period):
            kept, period_notes = resolve_amendments(list(group))
            notes += [f"{fund['short']} {note}" for note in period_notes]
            for filing, rows in kept:
                frames.append(normalize(rows, fund["cik"], fund["short"], filing))
                ticker_hints.update(edgar_ticker_hints(rows))
                # `filer_cik` is the CIK that actually filed, which for an aliases13f manager is
                # not the roster CIK the rows carry. Keeping it is what makes an alias's filing
                # findable rather than looking like it went missing.
                provenance.append(
                    {
                        "cik": fund["cik"],
                        "period": period,
                        "accession": filing.accession,
                        "url": filing.url,
                        "filed_at": filing.filed_at,
                        "is_amendment": filing.is_amendment,
                        "amendment_type": filing.amendment_type,
                        "filer_cik": cik,
                    }
                )
                if filing.raw_xml:
                    # Keyed by accession: an amended quarter archives every filing it had.
                    raw_by_filing[(cik, period, filing.accession)] = filing.raw_xml
    base = collapse(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame(columns=BASE_COLUMNS)
    return ManagerFetch(base, ticker_hints, raw_by_filing, pd.DataFrame(provenance, columns=FILING_COLUMNS), notes)


def print_dry_run_summary(short: str, enriched: pd.DataFrame) -> None:
    for period, group in enriched.groupby("period"):
        total_value = int(group["value"].sum())
        put_count = int((group["put_call"] == "PUT").sum())
        call_count = int((group["put_call"] == "CALL").sum())
        print(f"{short} {period}: {len(group)} rows, ${total_value:,} total value, PUT={put_count} CALL={call_count}")
        top10 = group.sort_values("value", ascending=False).head(10)
        for _, row in top10.iterrows():
            ticker = row["ticker"] or "?"
            sector = row["sector"] or "?"
            print(f"  {row['name']:<30} {ticker:<6} {sector:<24} ${row['value']:,}")


def print_dry_run_signals(tables: dict) -> None:
    latest = tables["periods"][-1]
    print(f"\n--- Signals for {latest} (top 5) ---")
    for name in ["consensus_buys", "high_conviction", "top_signals"]:
        df = tables[name]
        print(f"\n{name}:")
        print(df[df["period"] == latest].head(5).to_string(index=False))

    rotation = tables["sector_rotation"]
    print("\nsector_rotation:")
    print(rotation[rotation["period"] == latest].head(5).to_string(index=False))

    sim = tables["manager_similarity"].get(latest, {"ciks": [], "matrix": []})
    print("\nmanager_similarity ciks:", sim["ciks"])
    for row in sim["matrix"][:5]:
        print(["%.2f" % v for v in row])


def write_last_ingest(tables: dict, base_by_fund: list[tuple[dict, pd.DataFrame]]) -> None:
    """Keepalive marker for the ingest workflow: a real run commits this file so GitHub
    doesn't disable the scheduled workflow after 60 days of no repo activity."""
    path = HERE.parent / "data" / "last_ingest.json"
    path.parent.mkdir(exist_ok=True)
    payload = {
        "period": tables["periods"][-1],
        "ranAt": datetime.now(timezone.utc).isoformat(),
        "managers": [fund["short"] for fund, _ in base_by_fund],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def stale_manager_lines(base_by_fund: list[tuple[dict, pd.DataFrame]], latest: str) -> list[str]:
    """One line per manager missing the newest quarter, saying which kind of missing it is.

    A 13F-NT means the manager did not stop filing -- another one reported its holdings -- and is
    the only case that is fixable, by adding that manager's CIK to `aliases13f`.
    """
    lines = []
    for fund, base in base_by_fund:
        if latest in set(base["period"]):
            continue
        try:
            reason = (
                "filed a 13F-NT: another manager reported it, add that CIK to aliases13f"
                if filed_notice(fund["cik"], latest)
                else "no 13F-HR and no 13F-NT -- may have dropped below the $100M threshold"
            )
        except Exception as e:  # EDGAR hiccup: report the gap anyway, never fail the run over it
            reason = f"no 13F-HR; the 13F-NT check failed ({e})"
        lines.append(f"NO {latest} FILING: {fund['short']} -- {reason}")
    return lines


def counts_line(series: pd.Series) -> str:
    """Render a value_counts as one readable line: 3 new / 8 added / 1 exited."""
    parts = [
        f"{n} {'unclassified' if pd.isna(k) else str(k).lower().replace('_', ' ')}"
        for k, n in series.value_counts(dropna=False).items()
    ]
    return " · ".join(parts) or "none"


def step_summary(title: str, lines: list[str]) -> None:
    """Put the run's numbers on the GitHub Actions run page, so a green check is readable
    without opening the log. No-op outside Actions."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        print("###", title, file=f)
        for line in lines:
            print("-", line, file=f)
        print(file=f)


def init_firestore():
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
    return firestore.client()


def main() -> int:
    load_dotenv(HERE / ".env")
    config = load_config()

    parser = argparse.ArgumentParser()
    parser.add_argument("--quarters", type=int, default=config["quarters"])
    parser.add_argument("--fund", type=str, default=None, help="CIK of a single fund")
    parser.add_argument("--dry-run", action="store_true", help="fetch and compute, but write nothing to Firestore or GCS")
    parser.add_argument("--refresh", choices=["none", "unknown", "all"], default="none", help="rebuild securities/ cache entries")
    args = parser.parse_args()
    if args.fund and not args.dry_run:
        parser.error("--fund requires --dry-run; publish the full roster to preserve consensus")

    identity = os.environ.get("EDGAR_IDENTITY")
    if not identity:
        print("ERROR: EDGAR_IDENTITY is not set. Copy ingest/.env.example to ingest/.env and fill it in.", file=sys.stderr)
        return 1
    edgar.set_identity(identity)

    funds = load_funds()
    if args.fund:
        funds = [f for f in funds if f["cik"] == args.fund]
        if not funds:
            print(f"ERROR: no fund with CIK {args.fund} in funds.json", file=sys.stderr)
            return 1

    try:
        db = init_firestore()
    except Exception as e:
        print(f"ERROR: could not initialize Firestore credentials: {e}", file=sys.stderr)
        return 1

    api_key = os.environ.get("OPENFIGI_API_KEY")

    base_by_fund: list[tuple[dict, pd.DataFrame]] = []
    ticker_hints: dict[str, str] = {}
    raw_by_filing: dict[tuple, bytes] = {}
    filing_frames: list[pd.DataFrame] = []
    amendment_notes: list[str] = []
    failed: list[str] = []
    for fund in funds:
        try:
            fetched = fetch_manager(fund, args.quarters)
        except Exception as e:
            print(f"ERROR: {fund['short']} ({fund['cik']}) failed: {e}", file=sys.stderr)
            failed.append(fund["short"])
            continue
        base_by_fund.append((fund, fetched.base))
        ticker_hints.update(fetched.ticker_hints)
        raw_by_filing.update(fetched.raw_by_filing)
        filing_frames.append(fetched.filings)
        amendment_notes += fetched.notes

    if failed and not args.dry_run:
        step_summary("Ingest failed", [f"FAILED: {', '.join(failed)}; published dataset unchanged"])
        return 1

    all_cusips = sorted({c for _, base in base_by_fund for c in base["cusip"]})
    securities = (
        ensure_securities(db, all_cusips, identity, api_key, args.refresh, ticker_hints, persist=not args.dry_run)
        if all_cusips
        else {}
    )

    enriched_frames = []
    for fund, base in base_by_fund:
        enriched = attach(base, securities)
        enriched_frames.append(enriched)
        if args.dry_run:
            print_dry_run_summary(fund["short"], enriched)

    for note in amendment_notes:
        print(f"amendment: {note}")
    fail_line = [f"FAILED: {', '.join(failed)}"] if failed else []
    holdings = pd.concat(enriched_frames, ignore_index=True) if enriched_frames else pd.DataFrame()
    if args.dry_run and len(holdings):
        unmapped = holdings["ticker"].isna().mean()
        print(f"\nTotal rows: {len(holdings)}, unmapped tickers: {unmapped:.1%}")

    if len(holdings):
        filings = pd.concat(filing_frames, ignore_index=True) if filing_frames else pd.DataFrame(columns=FILING_COLUMNS)
        tables = derive_all(holdings, funds, config, load_corporate_actions())
        tables["filings"] = filings

        # A dry run must not touch remote state, and the GCS archive is remote state.
        bucket_name = None if args.dry_run else os.environ.get("GCS_BUCKET")
        if bucket_name:
            from google.cloud import storage

            bucket = storage.Client().bucket(bucket_name)
            write_gcs(bucket, raw_by_filing, tables)

        if args.dry_run:
            print_dry_run_signals(tables)
        else:
            write_firestore(db, tables, funds, tables["periods"])
            write_last_ingest(tables, base_by_fund)

        latest = tables["periods"][-1]
        mqs = tables["manager_quarter_summary"]
        stale_lines = stale_manager_lines(base_by_fund, latest)
        for line in stale_lines:
            print(line)
        step_summary(
            f"Ingest {latest}" + (" (dry run)" if args.dry_run else ""),
            [
                f"{len(base_by_fund)} of {len(funds)} managers filed, {len(holdings):,} holding rows",
                f"positions: {counts_line(mqs[mqs['period'] == latest]['status'])}",
                f"unmapped tickers: {holdings['ticker'].isna().mean():.1%}",
            ]
            + [f"amendment: {note}" for note in amendment_notes]
            + stale_lines
            + fail_line,
        )
    else:
        step_summary("Ingest", ["no holdings fetched"] + fail_line)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
