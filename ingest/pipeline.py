"""Plumbing shared by the three CLIs (ingest.py, ownership.py, insider.py): config, credentials,
the run summary, and the GCS-checkpointed filing log that ownership.py and insider.py both keep."""

import io
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

import edgar
import firebase_admin
import pandas as pd
from dotenv import load_dotenv
from firebase_admin import firestore
from google.cloud import storage

from store import commit_in_batches

HERE = Path(__file__).parent
logger = logging.getLogger(__name__)


def load_config() -> dict:
    return json.loads((HERE / "signals_config.json").read_text())


def load_funds() -> list[dict]:
    return json.loads((HERE / "funds.json").read_text())


def require_env(name: str, why: str) -> str:
    """The variable's value, or exit 1 naming it -- never echoing it, since it may be a secret."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"ERROR: {name} is not set. {why}")
    return value


def edgar_login() -> str:
    """Load ingest/.env, then register the identity EDGAR requires on every request."""
    if sys.platform == "win32":
        # edgartools prints Unicode warnings (a "today's filings" notice) that crash a cp1252
        # Windows console or pipe. Never hits the Linux CI runner; local-dev only.
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    load_dotenv(HERE / ".env")
    identity = require_env("EDGAR_IDENTITY", "Copy ingest/.env.example to ingest/.env and fill it in.")
    edgar.set_identity(identity)
    return identity


def init_firestore():
    try:
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app()
        return firestore.client()
    except Exception as e:
        sys.exit(f"ERROR: could not initialize Firestore credentials: {e}")


def gcs_bucket(pipeline: str):
    return storage.Client().bucket(require_env("GCS_BUCKET", f"It is required for the {pipeline} pipeline."))


def counts_line(series: pd.Series) -> str:
    """Render a value_counts as one readable line: 3 new · 8 added · 1 exited."""
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


# --- the filing log ownership.py and insider.py keep in GCS -------------------------------------


def since(arg: Optional[str], log: Optional[pd.DataFrame], cfg: dict) -> str:
    """`--since` when given, else a few days before the newest filing on file (a late index entry
    is caught on the next run), else the configured start date."""
    if arg:
        return arg
    if log is not None and len(log):
        latest = datetime.strptime(log["filed_at"].max(), "%Y-%m-%d")
        return (latest - timedelta(days=cfg["refetch_overlap_days"])).date().isoformat()
    return cfg["start_date"]


def read_state(bucket, blob_name: str) -> Optional[pd.DataFrame]:
    blob = bucket.blob(blob_name)
    if not blob.exists():
        return None
    return pd.read_parquet(io.BytesIO(blob.download_as_bytes()))


def write_state(bucket, blob_name: str, raw_prefix: str, log: pd.DataFrame, raw_by_accession: dict[str, str]) -> None:
    """Raw XML per new accession (best-effort), then the whole log parquet (must succeed)."""
    for accession, xml in raw_by_accession.items():
        try:
            bucket.blob(f"{raw_prefix}{accession}.xml").upload_from_string(xml, content_type="application/xml")
        except Exception:
            logger.exception("GCS upload failed: %s%s.xml", raw_prefix, accession)
    buf = io.BytesIO()
    log.to_parquet(buf, index=False)
    bucket.blob(blob_name).upload_from_string(buf.getvalue(), content_type="application/octet-stream")


def unseen(listed: pd.DataFrame, log: Optional[pd.DataFrame]) -> pd.DataFrame:
    """The listed filings the log does not already hold."""
    return listed if log is None else listed[~listed["accession"].isin(set(log["accession"]))]


def extend(log: Optional[pd.DataFrame], new: pd.DataFrame) -> pd.DataFrame:
    if log is None or not len(log):
        return new
    return pd.concat([log, new], ignore_index=True) if len(new) else log


def index_rows(index: pd.DataFrame) -> pd.DataFrame:
    """EDGAR full-index rows -> the (accession, form_raw, filing_date, cik, company) frame that
    `fetch_xml_rows` walks."""
    out = index[["accession_number", "form", "filing_date", "cik", "company"]].copy()
    out["filing_date"] = out["filing_date"].astype(str)  # to_pandas() gives datetime.date, not str
    return out.rename(columns={"accession_number": "accession", "form": "form_raw"}).reset_index(drop=True)


def fetch_xml_rows(listed: pd.DataFrame, parse: Callable[[str, object], Optional[list[dict]]]) -> tuple[list[dict], dict, int]:
    """(parsed rows, raw XML by accession, failed count). A filing that cannot be fetched or
    parsed is warned about and counted, never fatal: the refetch overlap retries it next run.
    `parse(xml, row)` returns the filing's rows, or None when it cannot read them."""
    rows: list[dict] = []
    raw_by_accession: dict[str, str] = {}
    failed = 0
    for row in listed.itertuples():
        try:
            # Positional, matching Filing's own (cik, company, form, filing_date, accession_no) order.
            xml = edgar.Filing(int(row.cik), row.company, row.form_raw, row.filing_date, row.accession).xml()
            parsed = parse(xml, row) if xml else None
            if parsed is None:
                raise ValueError("no structured XML" if not xml else "could not be parsed")
        except Exception as e:
            print(f"WARNING: {row.accession} skipped: {e}")
            failed += 1
            continue
        rows += parsed
        raw_by_accession[row.accession] = xml
    return rows, raw_by_accession, failed


def publish(db, collections: dict[str, dict[str, dict]], feed_path: str, feed: dict) -> int:
    """Every page, then the feed last, so the feed never links a page this run has not written.
    Doc ids are quote()d: a ticker like "ABC/U" must stay one path segment, as the web's
    encodeURIComponent expects. Returns the number of documents written."""
    writes = [(f"{name}/{quote(doc_id, safe='')}", doc) for name, docs in collections.items() for doc_id, doc in docs.items()]
    commit_in_batches(db, writes)
    commit_in_batches(db, [(feed_path, feed)])
    return len(writes) + 1


def newest_first(log: pd.DataFrame, key: str, only: Optional[set] = None):
    """(value, its rows newest filing first) for each distinct `key`, or each one in `only`.
    One sort and one groupby, not a full-table filter per value: a --rebuild spans thousands."""
    ordered = log.sort_values(["filed_at", "accession"], ascending=False, kind="stable")
    for value, rows in ordered.groupby(key, sort=False):
        if only is None or value in only:
            yield value, rows
