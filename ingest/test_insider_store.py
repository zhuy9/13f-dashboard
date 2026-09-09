import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pandas as pd
import pytest

from insider_derive import derive_all
from insider_store import build_feed, build_issuer_docs, build_people_docs, headline_counts, write_firestore

FIXTURE = Path(__file__).parent / "fixtures" / "insider_small.csv"

# Small, fixture-scaled config -- not the production signals_config.json values.
CFG = {
    "start_date": "2025-09-01",
    "min_open_market_value": 100000,
    "cluster_min_insiders": 3,
    "cluster_window_days": 90,
    "first_buy_lookback_days": 365,
    "recent_trades": 300,
    "max_trades_per_doc": 500,
}

STR_COLS = {"accession": str, "issuer_cik": str, "owner_cik": str}
HOLDER_COUNTS = {"TSTA": 2}
UNIVERSE = {"symbols": 4, "asOfPeriod": "2026-06-30"}


@pytest.fixture
def tables() -> dict:
    transactions = pd.read_csv(FIXTURE, dtype=STR_COLS)
    return derive_all(transactions, CFG, HOLDER_COUNTS)


def test_feed_shape_matches_section_k(tables):
    feed = build_feed(tables, CFG, UNIVERSE)
    assert set(feed) == {
        "updatedAt",
        "startDate",
        "lastFiledAt",
        "universe",
        "counts",
        "headline",
        "trades",
        "clusters",
        "vsThirteenF",
    }
    assert set(feed["counts"]) == {"filings", "trades", "issuers", "people"}
    assert feed["universe"] == UNIVERSE


def test_issuer_doc_shape_matches_section_k(tables):
    docs = build_issuer_docs(tables, CFG)
    doc = docs["TSTA"]
    assert set(doc) == {"symbol", "issuerCik", "issuerName", "sector", "summary", "people", "trades"}
    assert doc["summary"]["boughtShares"] > 0
    assert doc["people"][0].keys() >= {"ownerCik", "ownerName", "role", "buys", "sells", "netShares", "lastTradeAt"}


def test_person_doc_shape_matches_section_k(tables):
    docs = build_people_docs(tables, CFG)
    cik = tables["trades"].iloc[0]["owner_cik"]
    doc = docs[cik]
    assert set(doc) == {"cik", "name", "roles", "issuers", "trades"}
    assert doc["issuers"][0].keys() >= {"symbol", "issuerName", "role", "netShares"}


def test_issuer_docs_only_symbols_filters(tables):
    docs = build_issuer_docs(tables, CFG, only_symbols={"TSTA"})
    assert set(docs) == {"TSTA"}


def test_issuer_docs_rebuild_covers_every_symbol(tables):
    touched_docs = build_issuer_docs(tables, CFG, only_symbols={"TSTA"})
    rebuilt_docs = build_issuer_docs(tables, CFG, only_symbols=None)
    assert set(touched_docs) < set(rebuilt_docs)
    assert set(rebuilt_docs) == set(tables["trades"]["symbol"].unique())


def test_people_docs_only_ciks_filters(tables):
    cik = tables["trades"].iloc[0]["owner_cik"]
    docs = build_people_docs(tables, CFG, only_ciks={cik})
    assert set(docs) == {cik}


def test_docs_are_json_serializable(tables):
    feed = build_feed(tables, CFG, UNIVERSE)
    feed["updatedAt"] = "SERVER_TIMESTAMP"  # not JSON-serializable, and not under test here
    json.dumps(feed)
    for doc in build_issuer_docs(tables, CFG).values():
        json.dumps(doc)
    for doc in build_people_docs(tables, CFG).values():
        json.dumps(doc)


def test_every_doc_is_under_a_megabyte(tables):
    for doc in build_issuer_docs(tables, CFG).values():
        assert len(json.dumps(doc, default=str)) < 1_000_000
    for doc in build_people_docs(tables, CFG).values():
        assert len(json.dumps(doc, default=str)) < 1_000_000


def test_headline_counts_reads_zero_when_the_pipeline_has_been_quiet(tables):
    """A stalled pipeline must report zero for the window, not whatever the newest filing was
    -- the window is measured from `now`, injected here, not from the newest filing on file."""
    latest = tables["trades"]["filed_at"].max()
    long_after = date.fromisoformat(latest) + timedelta(days=30)

    counts = headline_counts(tables["trades"], tables["clusters"], CFG["start_date"], now=long_after)

    assert counts["openMarketBuys"] == 0
    assert counts["discretionarySales"] == 0
    assert counts["asOf"] == long_after.isoformat()


def test_headline_counts_sees_trades_inside_the_window(tables):
    latest = tables["trades"]["filed_at"].max()
    just_after = date.fromisoformat(latest) + timedelta(days=1)

    counts = headline_counts(tables["trades"], tables["clusters"], CFG["start_date"], now=just_after)

    assert counts["openMarketBuys"] >= 1


class _OrderedDb:
    """Just enough Firestore to record the order documents are committed in."""

    def __init__(self):
        self.commit_order: list[str] = []

    def document(self, path):
        return path

    def batch(self):
        docs: list[str] = []
        return SimpleNamespace(set=lambda ref, data: docs.append(ref), commit=lambda: self.commit_order.extend(docs))


def test_write_firestore_commits_the_feed_last(tables):
    db = _OrderedDb()
    issuer_docs = build_issuer_docs(tables, CFG)
    people_docs = build_people_docs(tables, CFG)
    feed = build_feed(tables, CFG, UNIVERSE)

    count = write_firestore(db, feed, issuer_docs, people_docs)

    assert db.commit_order[-1] == "insider/feed"
    assert count == len(issuer_docs) + len(people_docs) + 1


def test_issuer_doc_id_encodes_slash_matching_web_encodeuricomponent():
    assert quote("ABC/U", safe="") == "ABC%2FU"
