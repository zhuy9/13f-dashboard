"""CLI: fetch, parse, and derive 13D/13G ownership events; write to Firestore/GCS."""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import edgar
import pandas as pd
from dotenv import load_dotenv

from enrich import attach, ensure_securities, sec_ticker_to_cik
from ingest import init_firestore, load_config, load_funds
from ownership_derive import derive_all
from ownership_fetch import FILING_COLUMNS, fetch_rows, list_filings
from ownership_store import build_feed, build_investor_docs, build_issuer_docs, read_state, write_firestore, write_state

HERE = Path(__file__).parent


def _since(args_since: str | None, state: pd.DataFrame | None, cfg: dict) -> str:
    if args_since:
        return args_since
    if state is not None and len(state):
        latest = datetime.strptime(state["filed_at"].max(), "%Y-%m-%d")
        return (latest - timedelta(days=cfg["refetch_overlap_days"])).date().isoformat()
    return cfg["start_date"]


def _ticker_hints(rows: list[dict], identity: str) -> dict[str, str]:
    cik_to_ticker: dict[str, str] = {}
    for ticker, cik in sec_ticker_to_cik(identity).items():
        cik_to_ticker.setdefault(cik, ticker)
    return {r["cusip"]: cik_to_ticker[r["issuer_cik"]] for r in rows if r["issuer_cik"] in cik_to_ticker}


def _enrich(new_df: pd.DataFrame, rows: list[dict], db, identity: str, api_key: str | None) -> pd.DataFrame:
    """Some filings (notes, non-standard securities) carry no CUSIP -- give those an
    issuer-scoped fallback symbol instead of routing them through the CUSIP-keyed cache."""
    has_cusip = new_df["cusip"].notna()
    cusips = sorted(new_df.loc[has_cusip, "cusip"].unique())
    securities = ensure_securities(db, cusips, identity, api_key, False, _ticker_hints(rows, identity)) if cusips else {}
    resolved = attach(new_df[has_cusip], securities)

    unresolved = new_df[~has_cusip].copy()
    if len(unresolved):
        unresolved["ticker"] = None
        unresolved["sector"] = "Unknown"
        unresolved["symbol"] = "_ISSUER" + unresolved["issuer_cik"].fillna(unresolved["accession"])

    return pd.concat([resolved, unresolved], ignore_index=True) if len(unresolved) else resolved


def _print_dry_run(new_df: pd.DataFrame, touched_events: pd.DataFrame, recent: pd.DataFrame, funds: list[dict]) -> None:
    if not len(new_df):
        print("0 new filings")
        return
    print("event counts (new filings):", touched_events["event"].value_counts(dropna=False).to_dict())
    print("priority counts (new filings):", touched_events["priority"].value_counts().to_dict())
    print("\ntop 15 filers by filing count:")
    print(new_df["investor_name"].value_counts().head(15).to_string())

    unmatched = touched_events[~touched_events["is_roster"]]
    for short in (f["short"] for f in funds):
        hits = unmatched[unmatched["investor_name"].str.contains(short, case=False, na=False)]
        for _, r in hits.drop_duplicates("filer_cik").iterrows():
            print(f"  unmatched filer looks like roster manager '{short}': {r['investor_name']} (filer_cik={r['filer_cik']})")

    print("\n20 most recent events:")
    print(recent.head(20)[["filed_at", "form", "event", "priority", "investor_name", "symbol", "pct"]].to_string())


def main() -> int:
    load_dotenv(HERE / ".env")
    cfg = load_config()["ownership"]

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
        print("ERROR: GCS_BUCKET is required for the ownership pipeline.", file=sys.stderr)
        return 1
    from google.cloud import storage

    bucket = storage.Client().bucket(bucket_name)

    funds = load_funds()
    try:
        db = init_firestore()
    except Exception as e:
        print(f"ERROR: could not initialize Firestore credentials: {e}", file=sys.stderr)
        return 1

    state = read_state(bucket)
    since = _since(args.since, state, cfg)
    until = args.until or datetime.now(timezone.utc).date().isoformat()
    print(f"window: {since} .. {until}")

    listed = list_filings(funds, since, until)
    if state is not None and len(state):
        listed = listed[~listed["accession"].isin(set(state["accession"]))]

    rows, raw, failed = fetch_rows(listed, cfg)
    print(f"fetched {len(rows)} new filings ({failed} failed)")

    new_df = pd.DataFrame(rows, columns=FILING_COLUMNS)
    if len(new_df):
        new_df = _enrich(new_df, rows, db, identity, os.environ.get("OPENFIGI_API_KEY"))

    have_state = state is not None and len(state)
    if have_state and len(new_df):
        filings = pd.concat([state, new_df], ignore_index=True)
    else:
        filings = state if have_state else new_df
    if not len(filings):
        print("No filings in the window and no prior state; nothing to do.")
        return 1 if failed else 0

    tables = derive_all(filings, funds, cfg)
    new_accessions = set(new_df["accession"]) if len(new_df) else set()
    touched = tables["events"][tables["events"]["accession"].isin(new_accessions)]

    if args.dry_run:
        _print_dry_run(new_df, touched, tables["recent"], funds)
        return 1 if failed else 0

    only_symbols = None if args.rebuild else set(touched["symbol"].unique())
    only_ciks = None if args.rebuild else set(touched["investor_cik"].unique())
    feed = build_feed(tables, cfg)
    issuer_docs = build_issuer_docs(tables, cfg, only_symbols)
    investor_docs = build_investor_docs(tables, funds, cfg, only_ciks)

    write_state(bucket, filings, raw)
    count = write_firestore(db, feed, issuer_docs, investor_docs)
    print(f"wrote {count} Firestore documents")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
