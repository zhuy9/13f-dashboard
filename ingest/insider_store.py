"""Insider Firestore documents. The GCS transaction log they are built from is kept by pipeline.py."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from firebase_admin import firestore

from pipeline import newest_first
from store import records

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


def headline_counts(
    trades: pd.DataFrame, clusters: pd.DataFrame, start_date: str, now: Optional[date] = None, days: int = 7
) -> dict:
    """The Insiders page's headline tiles, over every trade on file with the window measured
    from `now` (not the newest filing) -- same fix as ownership's headline_counts, so a stalled
    pipeline reports zero instead of showing a permanently "busy" week."""
    now = now or datetime.now(timezone.utc).date()
    until, since = now.isoformat(), (now - timedelta(days=days)).isoformat()
    in_window = trades[(trades["filed_at"] > since) & (trades["filed_at"] <= until)]
    clustered_symbols = set(clusters["symbol"])
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
        "trades": records(tables["recent"][TRADE_FIELDS]),
        "clusters": records(clusters),
        "vsThirteenF": records(vs_13f),
    }


def build_issuer_docs(tables: dict, cfg: dict, only_symbols: Optional[set] = None) -> dict[str, dict]:
    summary = dict(tuple(tables["issuer_summary"].groupby("symbol")))
    people = tables["people"]
    people_by_symbol = dict(tuple(people.groupby("symbol")))
    docs = {}
    for symbol, trades in newest_first(tables["trades"], "symbol", only_symbols):
        meta = trades.iloc[0]
        docs[symbol] = {
            "symbol": symbol,
            "issuerCik": meta["issuer_cik"],
            "issuerName": meta["issuer_name"],
            "sector": meta.get("sector") or "Unknown",
            "summary": records(summary[symbol])[0] if symbol in summary else None,
            "people": records(people_by_symbol.get(symbol, people.iloc[:0])[ISSUER_PEOPLE_FIELDS]),
            "trades": records(trades.head(cfg["max_trades_per_doc"])[TRADE_FIELDS]),
        }
    return docs


def build_people_docs(tables: dict, cfg: dict, only_ciks: Optional[set] = None) -> dict[str, dict]:
    people = tables["people"]
    people_by_cik = dict(tuple(people.groupby("owner_cik")))
    docs = {}
    for cik, trades in newest_first(tables["trades"], "owner_cik", only_ciks):
        mine = people_by_cik.get(cik, people.iloc[:0])
        docs[cik] = {
            "cik": cik,
            "name": trades.iloc[0]["owner_name"],
            "roles": sorted(mine["role"].unique()),
            "issuers": records(mine[PERSON_ISSUER_FIELDS]),
            "trades": records(trades.head(cfg["max_trades_per_doc"])[TRADE_FIELDS]),
        }
    return docs
