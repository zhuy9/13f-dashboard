"""GCS state (all-time transactions parquet + raw XML) and Firestore insider doc writer."""

import io
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

import pandas as pd
from firebase_admin import firestore

from store import _commit_in_batches, _records

logger = logging.getLogger(__name__)

STATE_BLOB = "parquet/insider_transactions.parquet"
RAW_PREFIX = "raw_insider/"

# Published on every trade row across insider/feed, insider_issuers/{symbol}, insider_people/{cik}.
TRADE_FIELDS = [
    "accession", "form", "is_amendment", "filed_at", "transaction_date", "issuer_cik", "issuer_name",
    "symbol", "owner_cik", "owner_name", "role", "is_derivative", "security", "code", "kind",
    "shares", "price", "value", "acquired_disposed", "shares_after", "aff10b5_one", "is_planned",
    "is_discretionary_sale", "first_buy_in_window", "holders13f", "priority", "footnotes", "url",
]  # fmt: skip

ISSUER_PEOPLE_FIELDS = ["owner_cik", "owner_name", "role", "buys", "sells", "net_shares", "last_trade_at"]
PERSON_ISSUER_FIELDS = ["symbol", "issuer_name", "role", "net_shares"]


def read_state(bucket) -> Optional[pd.DataFrame]:
    blob = bucket.blob(STATE_BLOB)
    if not blob.exists():
        return None
    return pd.read_parquet(io.BytesIO(blob.download_as_bytes()))


def write_state(bucket, transactions: pd.DataFrame, raw_by_accession: dict[str, str]) -> None:
    """Raw XML per new accession (best-effort) then the whole state parquet (must succeed)."""
    for accession, xml in raw_by_accession.items():
        try:
            bucket.blob(f"{RAW_PREFIX}{accession}.xml").upload_from_string(xml, content_type="application/xml")
        except Exception:
            logger.exception("GCS upload failed: %s%s.xml", RAW_PREFIX, accession)

    buf = io.BytesIO()
    transactions.to_parquet(buf, index=False)
    bucket.blob(STATE_BLOB).upload_from_string(buf.getvalue(), content_type="application/octet-stream")


def headline_counts(
    trades: pd.DataFrame, clusters: pd.DataFrame, start_date: str, now: Optional[date] = None, days: int = 7
) -> dict:
    """The Insiders page's headline tiles, over every trade on file with the window measured
    from `now` (not the newest filing) -- same fix as ownership's headline_counts, so a stalled
    pipeline reports zero instead of showing a permanently "busy" week."""
    now = now or datetime.now(timezone.utc).date()
    until, since = now.isoformat(), (now - timedelta(days=days)).isoformat()
    in_window = trades[(trades["filed_at"] > since) & (trades["filed_at"] <= until)]
    clustered_symbols = set(clusters["symbol"]) if len(clusters) else set()
    cluster_buys = in_window[(in_window["code"] == "P") & in_window["symbol"].isin(clustered_symbols)]
    return {
        "asOf": until,
        "windowDays": days,
        "windowSince": since,
        "startDate": start_date,
        "openMarketBuys": int((in_window["code"] == "P").sum()),
        "discretionarySales": int(in_window["is_discretionary_sale"].sum()),
        "clusterBuys": int(cluster_buys["symbol"].nunique()),
    }


def build_feed(tables: dict, cfg: dict, universe: dict, now: Optional[date] = None) -> dict:
    trades, clusters, vs_13f = tables["trades"], tables["clusters"], tables["vs_13f"]
    return {
        "updatedAt": firestore.SERVER_TIMESTAMP,
        "startDate": cfg["start_date"],
        "lastFiledAt": trades["filed_at"].max() if len(trades) else None,
        "universe": universe,
        "counts": {
            "filings": int(trades["accession"].nunique()),
            "trades": int(len(trades)),
            "issuers": int(trades["symbol"].nunique()),
            "people": int(trades["owner_cik"].nunique()),
        },
        "headline": headline_counts(trades, clusters, cfg["start_date"], now),
        "trades": _records(tables["recent"][TRADE_FIELDS]),
        "clusters": _records(clusters) if len(clusters) else [],
        "vsThirteenF": _records(vs_13f) if len(vs_13f) else [],
    }


def build_issuer_docs(tables: dict, cfg: dict, only_symbols: Optional[set] = None) -> dict[str, dict]:
    trades, summary, people = tables["trades"], tables["issuer_summary"], tables["people"]
    symbols = set(trades["symbol"].unique())
    if only_symbols is not None:
        symbols &= only_symbols

    docs = {}
    for symbol in symbols:
        sym_trades = trades[trades["symbol"] == symbol].sort_values(["filed_at", "accession"], ascending=[False, False])
        sym_summary = summary[summary["symbol"] == symbol]
        sym_people = people[people["symbol"] == symbol]
        meta = sym_trades.iloc[0]
        docs[symbol] = {
            "symbol": symbol,
            "issuerCik": meta["issuer_cik"],
            "issuerName": meta["issuer_name"],
            "sector": meta.get("sector") or "Unknown",
            "summary": _records(sym_summary)[0] if len(sym_summary) else None,
            "people": _records(sym_people[ISSUER_PEOPLE_FIELDS]),
            "trades": _records(sym_trades.head(cfg["max_trades_per_doc"])[TRADE_FIELDS]),
        }
    return docs


def build_people_docs(tables: dict, cfg: dict, only_ciks: Optional[set] = None) -> dict[str, dict]:
    trades, people = tables["trades"], tables["people"]
    ciks = set(trades["owner_cik"].unique())
    if only_ciks is not None:
        ciks &= only_ciks

    docs = {}
    for cik in ciks:
        cik_trades = trades[trades["owner_cik"] == cik].sort_values(["filed_at", "accession"], ascending=[False, False])
        cik_people = people[people["owner_cik"] == cik]
        meta = cik_trades.iloc[0]
        docs[cik] = {
            "cik": cik,
            "name": meta["owner_name"],
            "roles": sorted(cik_people["role"].unique()),
            "issuers": _records(cik_people[PERSON_ISSUER_FIELDS]),
            "trades": _records(cik_trades.head(cfg["max_trades_per_doc"])[TRADE_FIELDS]),
        }
    return docs


def write_firestore(db, feed: dict, issuer_docs: dict[str, dict], people_docs: dict[str, dict]) -> int:
    writes: list[tuple[str, dict]] = []
    for symbol, doc in issuer_docs.items():
        writes.append((f"insider_issuers/{quote(symbol, safe='')}", doc))
    for cik, doc in people_docs.items():
        writes.append((f"insider_people/{cik}", doc))
    _commit_in_batches(db, writes)
    _commit_in_batches(db, [("insider/feed", feed)])
    return len(writes) + 1
