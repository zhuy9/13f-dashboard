"""CLI: build the quarterly issue from what the three pipelines already stored, then write it to
Firestore. No SEC request. Contract: docs/PLAN.md section M."""

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

from insider_derive import trades
from insider_store import STATE_BLOB as INSIDER_LOG
from ownership_derive import events
from ownership_store import STATE_BLOB as OWNERSHIP_LOG
from pipeline import HERE, gcs_bucket, init_firestore, load_config, load_funds, publish, read_state, step_summary
from quarterly_derive import facts, issue_period, stale_tables
from quarterly_llm import ai_notes
from quarterly_text import add_text
from store import read_published

TABLES = ["stock_quarter_summary", "biggest_new", "high_conviction", "sector_rotation"]
INDEX = "quarterly/index"


def merge_index(index: Optional[dict], issue: dict) -> dict:
    """The index with this issue's entry added or replaced, newest period first."""
    entry = {k: issue[k] for k in ("period", "label", "headline", "builtAt")}
    others = [e for e in (index or {}).get("issues", []) if e["period"] != issue["period"]]
    return {"updatedAt": issue["builtAt"], "issues": sorted([*others, entry], key=lambda e: e["period"], reverse=True)}


def _read_tables(bucket, period: str, prev: str, published_at: datetime) -> dict[str, pd.DataFrame]:
    """The per-period Parquet the issue needs. Any table missing or older than the snapshot stops
    the run before anything is written: an old table beside a new snapshot looks right but is not."""
    paths = {name: f"parquet/{name}/{period}.parquet" for name in TABLES}
    paths["high_conviction_prev"] = f"parquet/high_conviction/{prev}.parquet"
    blobs = {name: bucket.get_blob(path) for name, path in paths.items()}
    stale = stale_tables({name: blob.updated if blob else None for name, blob in blobs.items()}, published_at)
    if stale:
        sys.exit(f"ERROR: missing or stale Parquet in GCS: {', '.join(stale)}. Nothing written.")
    return {name: pd.read_parquet(io.BytesIO(blob.download_as_bytes())) for name, blob in blobs.items()}


def _pick_period(meta: dict, wanted: Optional[str], min_coverage: float) -> tuple[str, str]:
    periods = sorted(meta["periods"])
    if wanted:
        if wanted not in periods[1:]:
            sys.exit(f"ERROR: --period must be one of {', '.join(periods[1:])}.")
        return wanted, periods[periods.index(wanted) - 1]
    picked = issue_period(periods, meta["coverage"], len(meta["managers"]), min_coverage)
    if picked is None:
        sys.exit("ERROR: no quarter has enough managers filed for an issue.")
    return picked


def _print_issue(issue: dict) -> None:
    cov = issue["coverage"]
    print(f"{issue['label']} ({issue['period']}, previous {issue['prevPeriod']})")
    print("windows:", issue["windows"])
    print(f"coverage: {cov['filed']} of {cov['total']} filed; missing: {cov['missing']}")
    print("totals:", issue["totals"])
    print("headline:", issue["headline"])
    print("lede:", issue["lede"])
    for s in issue["sections"]:
        no_data = f", no data: {s['noData']}" if s["noData"] else ""
        first = [r.get("symbol") or r.get("sector") for r in s["rows"][:3]]
        print(f"\n[{s['id']}] total {s['total']}{no_data}; first rows {first}\n  {s['summary']}")
    print(f"\nissue size: {len(json.dumps(issue)):,} bytes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--period", type=str, default=None, help="build an older issue (YYYY-MM-DD)")
    parser.add_argument("--no-ai", action="store_true", help="publish template text only; drops stored AI notes")
    args = parser.parse_args()

    load_dotenv(HERE / ".env")
    cfg = load_config()
    db = init_firestore()
    bucket = gcs_bucket("quarterly")
    meta, _ = read_published(db)
    if meta is None:
        sys.exit("ERROR: meta/latest is missing. Run ingest.py before quarterly.py.")
    period, prev = _pick_period(meta, args.period, cfg["quarterly"]["min_coverage"])

    tables = _read_tables(bucket, period, prev, meta["updatedAt"])
    summary = tables["stock_quarter_summary"]
    # Holders at the issue's own quarter, not meta/holder_counts (the latest quarter only).
    held = summary[summary["manager_count"] > 0]
    holders = dict(zip(held["symbol"], held["manager_count"].astype(int)))
    ownership_log, insider_log = read_state(bucket, OWNERSHIP_LOG), read_state(bucket, INSIDER_LOG)
    if ownership_log is None or insider_log is None:
        sys.exit("ERROR: the ownership or insider log is missing in GCS. Nothing written.")
    # ponytail: a back issue reads both logs as they are on file today, not as they were known then.
    found = facts(
        tables,
        events(ownership_log, load_funds(), cfg["ownership"], holders),
        trades(insider_log, cfg["insider"], holders),
        meta,
        period,
        prev,
        datetime.now(timezone.utc).date().isoformat(),
        cfg,
    )
    issue = {**add_text(found, cfg), "builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    if args.dry_run:
        _print_issue(issue)
    else:
        if not args.no_ai:
            stored = (db.document(f"quarterly/{period}").get().to_dict() or {}).get("ai")
            issue = {**issue, "ai": ai_notes(issue, cfg["quarterly"], stored)}
        snap = db.document(INDEX).get()
        index = merge_index(snap.to_dict() if snap.exists else None, issue)
        print(f"wrote {publish(db, {'quarterly': {period: issue}}, INDEX, index)} Firestore documents")

    step_summary(
        f"Quarterly issue {issue['label']}" + (" (dry run)" if args.dry_run else ""),
        [issue["headline"], *(f"{s['id']}: {s['total']}" for s in issue["sections"])],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
