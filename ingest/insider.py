"""CLI: fetch, parse, and derive Form 4 insider transactions; write to Firestore/GCS."""

import argparse
import sys
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd

from enrich import sec_ticker_to_cik
from insider_derive import derive_all
from insider_fetch import TRANSACTION_COLUMNS, fetch_rows, list_filings, universe_ciks
from insider_store import RAW_PREFIX, STATE_BLOB, build_cluster_doc, build_feed, build_issuer_docs, build_people_docs
from pipeline import (
    counts_line,
    edgar_login,
    extend,
    gcs_bucket,
    init_firestore,
    load_config,
    publish,
    read_state,
    since,
    step_summary,
    unseen,
    write_state,
)
from store import read_holder_counts, read_published


def _enrich_sector(df: pd.DataFrame, db, prefix: str) -> pd.DataFrame:
    """Form 4 carries no CUSIP, so `ensure_securities`/OpenFIGI never runs here -- sector comes
    from the already-published `stocks/{symbol}` doc, or "Unknown" when there isn't one."""
    doc_ids = {symbol: quote(symbol, safe="") for symbol in df["symbol"].unique()}
    refs = [db.document(f"{prefix}stocks/{doc_id}") for doc_id in doc_ids.values()]
    # One batched read for the whole run, not a round trip per symbol.
    sector = {
        snap.id: (snap.to_dict() or {}).get("sector", "Unknown") for snap in (db.get_all(refs) if refs else []) if snap.exists
    }
    return df.assign(sector=df["symbol"].map(lambda s: sector.get(doc_ids[s], "Unknown")))


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
    cfg = load_config()["insider"]

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since", type=str, default=None)
    parser.add_argument("--until", type=str, default=None)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    identity = edgar_login()
    bucket = gcs_bucket("insider")
    db = init_firestore()

    holder_counts = read_holder_counts(db)
    if holder_counts is None:
        sys.exit("ERROR: meta/holder_counts is missing. Run ingest.py before insider.py.")

    meta, prefix = read_published(db)
    issuer_ciks, symbol_by_cik = universe_ciks(holder_counts, sec_ticker_to_cik(identity), cfg)

    state = read_state(bucket, STATE_BLOB)
    start = since(args.since, state, cfg)
    until = args.until or datetime.now(timezone.utc).date().isoformat()
    print(f"window: {start} .. {until}, universe: {len(issuer_ciks)} issuers")

    rows, raw, failed = fetch_rows(unseen(list_filings(issuer_ciks, start, until), state), symbol_by_cik, cfg)
    print(f"fetched {len(rows)} new transaction rows ({failed} failed filings)")

    new_df = _enrich_sector(pd.DataFrame(rows, columns=TRANSACTION_COLUMNS), db, prefix)
    transactions = extend(state, new_df)
    if not len(transactions):
        print("No transactions in the window and no prior state; nothing to do.")
        step_summary(f"Insider {start} .. {until}", ["no transactions in the window"])
        return 1 if failed else 0

    tables = derive_all(transactions, cfg, holder_counts)
    touched = tables["trades"][tables["trades"]["accession"].isin(set(new_df["accession"]))]

    summary = [
        f"{len(new_df)} new transaction rows, {failed} failed filings",
        f"kinds: {counts_line(touched['kind'])}",
        f"priority: {counts_line(touched['priority'])}",
        f"universe: {len(issuer_ciks)} issuers, {len(holder_counts)} symbols in holder_counts",
    ]

    if args.dry_run:
        _print_dry_run(new_df, touched, tables["recent"])
    else:
        only_symbols = None if args.rebuild else set(touched["symbol"])
        only_ciks = None if args.rebuild else set(touched["owner_cik"])
        universe = {"symbols": len(symbol_by_cik), "asOfPeriod": meta.get("latestPeriod")}
        pages = {
            "insider_issuers": build_issuer_docs(tables, cfg, only_symbols),
            "insider_people": build_people_docs(tables, cfg, only_ciks),
            "insider": {"clusters": build_cluster_doc(tables)},
        }
        count = publish(db, pages, "insider/feed", build_feed(tables, cfg, universe))
        write_state(bucket, STATE_BLOB, RAW_PREFIX, transactions, raw)
        print(f"wrote {count} Firestore documents")
        summary.append(f"{count} Firestore documents written")

    step_summary(f"Insider {start} .. {until}" + (" (dry run)" if args.dry_run else ""), summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
