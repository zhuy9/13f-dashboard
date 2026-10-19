"""CLI: fetch, parse, and derive 13D/13G ownership events; write to Firestore/GCS."""

import argparse
import os
import sys
from datetime import datetime, timezone

import pandas as pd

from enrich import attach, cik_to_ticker, ensure_securities
from ownership_derive import derive_all
from ownership_fetch import FILING_COLUMNS, fetch_rows, list_filings
from ownership_store import RAW_PREFIX, STATE_BLOB, build_feed, build_investor_docs, build_issuer_docs
from pipeline import (
    counts_line,
    edgar_login,
    extend,
    gcs_bucket,
    init_firestore,
    load_config,
    load_funds,
    publish,
    read_state,
    since,
    step_summary,
    unseen,
    write_state,
)
from store import read_holder_counts


def _ticker_hints(rows: list[dict]) -> dict[str, str]:
    tickers = cik_to_ticker()
    return {r["cusip"]: tickers[r["issuer_cik"]] for r in rows if r["issuer_cik"] in tickers}


def _enrich(
    new_df: pd.DataFrame, rows: list[dict], db, api_key: str | None, persist: bool = True, refresh: str = "none"
) -> pd.DataFrame:
    """Some filings (notes, non-standard securities) carry no CUSIP -- give those an
    issuer-scoped fallback symbol instead of routing them through the CUSIP-keyed cache."""
    has_cusip = new_df["cusip"].notna()
    cusips = sorted(new_df.loc[has_cusip, "cusip"].unique())
    securities = ensure_securities(db, cusips, api_key, refresh, _ticker_hints(rows), persist=persist) if cusips else {}
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
    cfg = load_config()["ownership"]

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since", type=str, default=None)
    parser.add_argument("--until", type=str, default=None)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    edgar_login()  # edgartools sends this identity to SEC on every request
    bucket = gcs_bucket("ownership")
    funds = load_funds()
    db = init_firestore()

    state = read_state(bucket, STATE_BLOB)
    start = since(args.since, state, cfg)
    until = args.until or datetime.now(timezone.utc).date().isoformat()
    print(f"window: {start} .. {until}")

    rows, raw, failed = fetch_rows(unseen(list_filings(funds, start, until), state), cfg)
    print(f"fetched {len(rows)} new filings ({failed} failed)")

    new_df = pd.DataFrame(rows, columns=FILING_COLUMNS)
    if len(new_df):
        new_df = _enrich(new_df, rows, db, os.environ.get("OPENFIGI_API_KEY"), persist=not args.dry_run)

    filings = extend(state, new_df)
    if args.rebuild and len(filings):
        # The log keeps the ticker, sector and symbol each filing got when it was fetched, and
        # derive groups by that symbol. Re-key it from the cache so a changed ticker (SEC form,
        # a rename) keeps one history; the rewritten log is saved below.
        filings = _enrich(filings, filings.to_dict("records"), db, os.environ.get("OPENFIGI_API_KEY"), not args.dry_run, "all")
    if not len(filings):
        print("No filings in the window and no prior state; nothing to do.")
        step_summary(f"Ownership {start} .. {until}", ["no filings in the window"])
        return 1 if failed else 0

    # The 13F side of the join: how many tracked managers already held what these filings land on.
    holder_counts = read_holder_counts(db)

    tables = derive_all(filings, funds, cfg, holder_counts)
    touched = tables["events"][tables["events"]["accession"].isin(set(new_df["accession"]))]

    summary = [
        f"{len(new_df)} new filings, {failed} failed",
        f"events: {counts_line(touched['event'])}",
        f"priority: {counts_line(touched['priority'])}",
        f"13F holder counts: {len(holder_counts or {})} symbols",
    ]

    if args.dry_run:
        _print_dry_run(new_df, touched, tables["recent"], funds)
    else:
        only_symbols = None if args.rebuild else set(touched["symbol"])
        only_ciks = None if args.rebuild else set(touched["investor_cik"])
        pages = {
            "ownership_issuers": build_issuer_docs(tables, cfg, only_symbols),
            "ownership_investors": build_investor_docs(tables, funds, cfg, only_ciks),
        }
        count = publish(db, pages, "ownership/feed", build_feed(tables, cfg))
        write_state(bucket, STATE_BLOB, RAW_PREFIX, filings, raw)
        print(f"wrote {count} Firestore documents")
        summary.append(f"{count} Firestore documents written")

    step_summary(f"Ownership {start} .. {until}" + (" (dry run)" if args.dry_run else ""), summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
