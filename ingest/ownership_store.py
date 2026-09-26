"""Ownership Firestore documents. The GCS filing log they are built from is kept by pipeline.py."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from firebase_admin import firestore

from pipeline import newest_first
from store import records

STATE_BLOB = "parquet/ownership_filings.parquet"
RAW_PREFIX = "raw_ownership/"

EVENT_FIELDS = [
    "accession", "form", "is_amendment", "amendment_no", "filed_at", "event_date",
    "investor_cik", "investor_name", "short", "is_roster", "is_activist",
    "issuer_cik", "issuer_name", "symbol", "sector", "shares", "pct", "prev_pct",
    "change_pp", "event", "priority", "purpose", "url", "holders13f",
]  # fmt: skip

STAKE_FIELDS = [
    "investor_cik", "investor_name", "short", "is_roster", "is_activist",
    "issuer_cik", "issuer_name", "symbol", "sector", "form", "pct", "shares",
    "change_pp", "event", "filed_at", "accession", "url",
]  # fmt: skip


def headline_counts(events: pd.DataFrame, start_date: str, now: Optional[date] = None, days: int = 7) -> dict:
    """The Ownership page's headline tiles, counted here rather than in the browser.

    Two things were wrong with counting them from the feed. The feed is the newest
    `recent_events` rows only, so any count over it silently means "among the last 300 events"
    however it is labelled. And the seven-day window was measured back from the newest filing
    in the feed rather than from today, so it could never report zero -- a pipeline stalled for
    a month still showed a busy week.

    Each count carries the window and scope it was computed over, because "New 13Ds" with no
    date range attached is not an answer.
    """
    now = now or datetime.now(timezone.utc).date()
    until = now.isoformat()
    since = (now - timedelta(days=days)).isoformat()
    # String comparison: filed_at is an ISO date, which sorts chronologically as text.
    in_window = events[(events["filed_at"] > since) & (events["filed_at"] <= until)]
    entries = events["is_activist"] & events["event"].isin(["NEW", "SWITCHED_TO_13D"])
    return {
        "asOf": until,
        "windowDays": days,
        "windowSince": since,
        "filingsInWindow": int(in_window["accession"].nunique()),
        "startDate": start_date,
        "new13dSinceStart": int(((events["event"] == "NEW") & (events["form"] == "13D")).sum()),
        "activistEntriesSinceStart": int(entries.sum()),
    }


def build_feed(tables: dict, cfg: dict, now: Optional[date] = None) -> dict:
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
        # Over every event on file, not over the truncated `recent` feed below it.
        "headline": headline_counts(events, cfg["start_date"], now),
        "events": records(tables["recent"][EVENT_FIELDS]),
    }


def build_issuer_docs(tables: dict, cfg: dict, only_symbols: Optional[set] = None) -> dict[str, dict]:
    stakes = tables["stakes"]
    current = dict(tuple(stakes[stakes["is_current"]].groupby("symbol")))
    docs = {}
    for symbol, events in newest_first(tables["events"], "symbol", only_symbols):
        meta = events.iloc[0]
        docs[symbol] = {
            "symbol": symbol,
            "issuerCik": meta["issuer_cik"],
            "issuerName": meta["issuer_name"],
            "sector": meta["sector"],
            "holders": records(current.get(symbol, stakes.iloc[:0])[STAKE_FIELDS]),
            "events": records(events.head(cfg["max_events_per_doc"])[EVENT_FIELDS]),
        }
    return docs


def build_investor_docs(tables: dict, funds: list[dict], cfg: dict, only_ciks: Optional[set] = None) -> dict[str, dict]:
    stakes = tables["stakes"]
    current = dict(tuple(stakes[stakes["is_current"]].groupby("investor_cik")))
    name_by_cik = {f["cik"]: f["name"] for f in funds}
    docs = {}
    for cik, events in newest_first(tables["events"], "investor_cik", only_ciks):
        meta = events.iloc[0]
        docs[cik] = {
            "cik": cik,
            "name": name_by_cik.get(cik, meta["investor_name"]),
            "short": meta["short"] if meta["is_roster"] else None,
            "cluster": meta["cluster"] if meta["is_roster"] else None,
            "isRoster": bool(meta["is_roster"]),
            "isActivist": bool(meta["is_activist"]),
            "stakes": records(current.get(cik, stakes.iloc[:0])[STAKE_FIELDS]),
            "events": records(events.head(cfg["max_events_per_doc"])[EVENT_FIELDS]),
        }
    return docs
