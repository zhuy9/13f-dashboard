"""GCS state (all-time filings parquet + raw XML) and Firestore ownership doc writer."""

import io
import logging
from typing import Optional
from urllib.parse import quote

import pandas as pd
from firebase_admin import firestore

from store import _commit_in_batches, _records

logger = logging.getLogger(__name__)

STATE_BLOB = "parquet/ownership_filings.parquet"
RAW_PREFIX = "raw_ownership/"

EVENT_FIELDS = [
    "accession", "form", "is_amendment", "amendment_no", "filed_at", "event_date",
    "investor_cik", "investor_name", "short", "is_roster", "is_activist",
    "issuer_cik", "issuer_name", "symbol", "sector", "shares", "pct", "prev_pct",
    "change_pp", "event", "priority", "purpose", "url",
]  # fmt: skip

STAKE_FIELDS = [
    "investor_cik", "investor_name", "short", "is_roster", "is_activist",
    "issuer_cik", "issuer_name", "symbol", "sector", "form", "pct", "shares",
    "change_pp", "event", "filed_at", "accession", "url",
]  # fmt: skip


def read_state(bucket) -> Optional[pd.DataFrame]:
    blob = bucket.blob(STATE_BLOB)
    if not blob.exists():
        return None
    return pd.read_parquet(io.BytesIO(blob.download_as_bytes()))


def write_state(bucket, filings: pd.DataFrame, raw_by_accession: dict[str, str]) -> None:
    """Raw XML per new accession (best-effort) then the whole state parquet (must succeed)."""
    for accession, xml in raw_by_accession.items():
        try:
            bucket.blob(f"{RAW_PREFIX}{accession}.xml").upload_from_string(xml, content_type="application/xml")
        except Exception:
            logger.exception("GCS upload failed: %s%s.xml", RAW_PREFIX, accession)

    buf = io.BytesIO()
    filings.to_parquet(buf, index=False)
    bucket.blob(STATE_BLOB).upload_from_string(buf.getvalue(), content_type="application/octet-stream")


def build_feed(tables: dict, cfg: dict) -> dict:
    filings, events = tables["filings"], tables["events"]
    return {
        "updatedAt": firestore.SERVER_TIMESTAMP,
        "startDate": cfg["start_date"],
        "lastFiledAt": filings["filed_at"].max() if len(filings) else None,
        "counts": {
            "filings": int(len(filings)),
            "investors": int(events["investor_cik"].nunique()),
            "issuers": int(events["symbol"].nunique()),
        },
        "events": _records(tables["recent"][EVENT_FIELDS]),
    }


def build_issuer_docs(tables: dict, cfg: dict, only_symbols: Optional[set] = None) -> dict[str, dict]:
    events, stakes = tables["events"], tables["stakes"]
    symbols = set(events["symbol"].unique())
    if only_symbols is not None:
        symbols &= only_symbols

    docs = {}
    for symbol in symbols:
        sym_events = events[events["symbol"] == symbol].sort_values(["filed_at", "accession"], ascending=[False, False])
        sym_stakes = stakes[(stakes["symbol"] == symbol) & stakes["is_current"]]
        meta = sym_events.iloc[0]
        docs[symbol] = {
            "symbol": symbol,
            "issuerCik": meta["issuer_cik"],
            "issuerName": meta["issuer_name"],
            "sector": meta["sector"],
            "holders": _records(sym_stakes[STAKE_FIELDS]),
            "events": _records(sym_events.head(cfg["max_events_per_doc"])[EVENT_FIELDS]),
        }
    return docs


def build_investor_docs(tables: dict, funds: list[dict], cfg: dict, only_ciks: Optional[set] = None) -> dict[str, dict]:
    events, stakes = tables["events"], tables["stakes"]
    name_by_cik = {f["cik"]: f["name"] for f in funds}
    ciks = set(events["investor_cik"].unique())
    if only_ciks is not None:
        ciks &= only_ciks

    docs = {}
    for cik in ciks:
        cik_events = events[events["investor_cik"] == cik].sort_values(["filed_at", "accession"], ascending=[False, False])
        cik_stakes = stakes[(stakes["investor_cik"] == cik) & stakes["is_current"]]
        meta = cik_events.iloc[0]
        docs[cik] = {
            "cik": cik,
            "name": name_by_cik.get(cik, meta["investor_name"]),
            "short": meta["short"] if meta["is_roster"] else None,
            "cluster": meta["cluster"] if meta["is_roster"] else None,
            "isRoster": bool(meta["is_roster"]),
            "isActivist": bool(meta["is_activist"]),
            "stakes": _records(cik_stakes[STAKE_FIELDS]),
            "events": _records(cik_events.head(cfg["max_events_per_doc"])[EVENT_FIELDS]),
        }
    return docs


def write_firestore(db, feed: dict, issuer_docs: dict[str, dict], investor_docs: dict[str, dict]) -> int:
    writes: list[tuple[str, dict]] = [("ownership/feed", feed)]
    for symbol, doc in issuer_docs.items():
        writes.append((f"ownership_issuers/{quote(symbol, safe='')}", doc))
    for cik, doc in investor_docs.items():
        writes.append((f"ownership_investors/{cik}", doc))
    _commit_in_batches(db, writes)
    return len(writes)
