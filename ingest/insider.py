"""CLI: fetch, parse, and derive Form 4 insider transactions; write to Firestore/GCS."""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import edgar
import pandas as pd
from dotenv import load_dotenv

from enrich import sec_ticker_to_cik
from ingest import counts_line, init_firestore, load_config, step_summary
from insider_derive import derive_all
from insider_fetch import TRANSACTION_COLUMNS, fetch_rows, list_filings, universe_ciks
from insider_store import build_feed, build_issuer_docs, build_people_docs, read_state, write_firestore, write_state
from store import read_holder_counts

HERE = Path(__file__).parent

if sys.platform == "win32":
    # edgartools prints a Unicode warning (e.g. a today's-filings notice) that crashes on the
    # legacy Windows console's cp1252 encoding. Never hits the Linux CI runner; local-dev only.
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")


def _since(args_since: str | None, state: pd.DataFrame | None, cfg: dict) -> str:
    if args_since:
        return args_since
    if state is not None and len(state):
        latest = datetime.strptime(state["filed_at"].max(), "%Y-%m-%d")
        return (latest - timedelta(days=cfg["refetch_overlap_days"])).date().isoformat()
    return cfg["start_date"]


def _dataset_meta(db) -> dict:
    snap = db.document("meta/latest").get()
    return (snap.to_dict() or {}) if snap.exists else {}


def _enrich_sector(df: pd.DataFrame, db, prefix: str) -> pd.DataFrame:
    """Form 4 carries no CUSIP, so `ensure_securities`/OpenFIGI never runs here -- sector comes
    from the already-published `stocks/{symbol}` doc, or "Unknown" when there isn't one."""
    out = df.copy()
    if not len(out):
        out["sector"] = []
        return out
    sector_by_symbol = {}
    for symbol in sorted(out["symbol"].unique()):
        snap = db.document(f"{prefix}stocks/{quote(symbol, safe='')}").get()
        sector_by_symbol[symbol] = (snap.to_dict() or {}).get("sector", "Unknown") if snap.exists else "Unknown"
    out["sector"] = out["symbol"].map(sector_by_symbol)
    return out


def _print_dry_run(new_df: pd.DataFrame, touched: pd.DataFrame, recent: pd.DataFrame) -> None:
    if not len(new_df):
        print("0 new transaction rows")
        return
    print("kind counts (new rows):", touched["kind"].value_counts(dropna=False).to_dict())
    print("priority counts (new rows):", touched["priority"].value_counts().to_dict())
    print("\ntop 15 owners by transaction count:")
    print(new_df["owner_name"].value_counts().head(15).to_string())
    print("\n20 most recent trades:")
    cols = ["filed_at", "transaction_date", "kind", "priority", "owner_name", "symbol", "shares", "value"]
    print(recent.head(20)[cols].to_string())


def main() -> int:
    load_dotenv(HERE / ".env")
    cfg = load_config()["insider"]

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since", type=str, default=None)
    parser.add_argument("--until", type=str, default=None)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    identity = os.environ.get("EDGAR_IDENTITY")
    if not identity:
        print("ERROR: EDGAR_IDENTITY is not set. Copy ingest/.env.example to ingest/.env and fill it in.", file=sys.stderr)
        return 1
    edgar.set_identity(identity)

    bucket_name = os.environ.get("GCS_BUCKET")
    if not bucket_name:
        print("ERROR: GCS_BUCKET is required for the insider pipeline.", file=sys.stderr)
        return 1
    from google.cloud import storage

    bucket = storage.Client().bucket(bucket_name)

    try:
        db = init_firestore()
    except Exception as e:
        print(f"ERROR: could not initialize Firestore credentials: {e}", file=sys.stderr)
        return 1

    holder_counts = read_holder_counts(db)
    if holder_counts is None:
        print("ERROR: meta/holder_counts is missing. Run ingest.py before insider.py.", file=sys.stderr)
        return 1

    meta = _dataset_meta(db)
    prefix = f"datasets/{meta['datasetId']}/" if meta.get("datasetId") else ""
    issuer_ciks, symbol_by_cik = universe_ciks(holder_counts, sec_ticker_to_cik(identity), cfg)

    state = read_state(bucket)
    since = _since(args.since, state, cfg)
    until = args.until or datetime.now(timezone.utc).date().isoformat()
    print(f"window: {since} .. {until}, universe: {len(issuer_ciks)} issuers")

    listed = list_filings(issuer_ciks, since, until)
    if state is not None and len(state):
        listed = listed[~listed["accession"].isin(set(state["accession"]))]

    rows, raw, failed = fetch_rows(listed, symbol_by_cik, cfg)
    print(f"fetched {len(rows)} new transaction rows ({failed} failed filings)")

    new_df = pd.DataFrame(rows, columns=TRANSACTION_COLUMNS)
    new_df = _enrich_sector(new_df, db, prefix)

    have_state = state is not None and len(state)
    if have_state and len(new_df):
        transactions = pd.concat([state, new_df], ignore_index=True)
    else:
        transactions = state if have_state else new_df
    if not len(transactions):
        print("No transactions in the window and no prior state; nothing to do.")
        step_summary(f"Insider {since} .. {until}", ["no transactions in the window"])
        return 1 if failed else 0

    tables = derive_all(transactions, cfg, holder_counts)
    new_accessions = set(new_df["accession"]) if len(new_df) else set()
    touched = tables["trades"][tables["trades"]["accession"].isin(new_accessions)]

    summary = [
        f"{len(new_df)} new transaction rows, {failed} failed filings",
        f"kinds: {counts_line(touched['kind'])}",
        f"priority: {counts_line(touched['priority'])}",
        f"universe: {len(issuer_ciks)} issuers, {len(holder_counts)} symbols in holder_counts",
    ]

    if args.dry_run:
        _print_dry_run(new_df, touched, tables["recent"])
    else:
        only_symbols = None if args.rebuild else set(touched["symbol"].unique())
        only_ciks = None if args.rebuild else set(touched["owner_cik"].unique())
        universe = {"symbols": len(symbol_by_cik), "asOfPeriod": meta.get("latestPeriod")}
        feed = build_feed(tables, cfg, universe)
        issuer_docs = build_issuer_docs(tables, cfg, only_symbols)
        people_docs = build_people_docs(tables, cfg, only_ciks)

        count = write_firestore(db, feed, issuer_docs, people_docs)
        write_state(bucket, transactions, raw)
        print(f"wrote {count} Firestore documents")
        summary.append(f"{count} Firestore documents written")

    step_summary(f"Insider {since} .. {until}" + (" (dry run)" if args.dry_run else ""), summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
