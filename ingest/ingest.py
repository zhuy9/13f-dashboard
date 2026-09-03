"""CLI: fetch, normalize, and enrich 13F holdings for the tracked managers."""

import argparse
import json
import os
import sys
from pathlib import Path

import edgar
import firebase_admin
import pandas as pd
from dotenv import load_dotenv
from firebase_admin import firestore

from derive import derive_all
from enrich import attach, ensure_securities
from fetch import BASE_COLUMNS, edgar_ticker_hints, fetch_filings, filing_rows, normalize
from store import write_firestore, write_gcs

HERE = Path(__file__).parent


def load_funds() -> list[dict]:
    return json.loads((HERE / "funds.json").read_text())


def load_config() -> dict:
    return json.loads((HERE / "signals_config.json").read_text())


def fetch_manager(fund: dict, quarters: int) -> tuple[pd.DataFrame, dict[str, str], dict[tuple, bytes]]:
    filings = fetch_filings(fund["cik"], quarters)
    frames = []
    ticker_hints: dict[str, str] = {}
    raw_by_filing: dict[tuple, bytes] = {}
    for f in filings:
        period, filed_at, raw_xml, df = filing_rows(f)
        frames.append(normalize(df, fund["cik"], fund["short"], period, filed_at))
        ticker_hints.update(edgar_ticker_hints(df))
        if raw_xml:
            raw_by_filing[(fund["cik"], period)] = raw_xml
    base = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=BASE_COLUMNS)
    return base, ticker_hints, raw_by_filing


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
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh-unknown", action="store_true")
    args = parser.parse_args()

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
    failed: list[str] = []
    for fund in funds:
        try:
            base, fund_hints, fund_raw = fetch_manager(fund, args.quarters)
        except Exception as e:
            print(f"ERROR: {fund['short']} ({fund['cik']}) failed: {e}", file=sys.stderr)
            failed.append(fund["short"])
            continue
        base_by_fund.append((fund, base))
        ticker_hints.update(fund_hints)
        raw_by_filing.update(fund_raw)

    all_cusips = sorted({c for _, base in base_by_fund for c in base["cusip"]})
    securities = ensure_securities(db, all_cusips, identity, api_key, args.refresh_unknown, ticker_hints) if all_cusips else {}

    enriched_frames = []
    for fund, base in base_by_fund:
        enriched = attach(base, securities)
        enriched_frames.append(enriched)
        if args.dry_run:
            print_dry_run_summary(fund["short"], enriched)

    holdings = pd.concat(enriched_frames, ignore_index=True) if enriched_frames else pd.DataFrame()
    if args.dry_run and len(holdings):
        unmapped = holdings["ticker"].isna().mean()
        print(f"\nTotal rows: {len(holdings)}, unmapped tickers: {unmapped:.1%}")

    if len(holdings):
        tables = derive_all(holdings, funds, config)

        bucket_name = os.environ.get("GCS_BUCKET")
        if bucket_name:
            from google.cloud import storage

            bucket = storage.Client().bucket(bucket_name)
            write_gcs(bucket, raw_by_filing, tables)

        if args.dry_run:
            print_dry_run_signals(tables)
        else:
            write_firestore(db, tables, funds, tables["periods"])

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
