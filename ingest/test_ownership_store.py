import json
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import pytest

from ownership_derive import derive_all
from ownership_store import build_feed, build_investor_docs, build_issuer_docs

FIXTURE = Path(__file__).parent / "fixtures" / "ownership_small.csv"

FUNDS = [
    {
        "cik": "1791786",
        "name": "Elliott Investment Management L.P.",
        "short": "Elliott",
        "cluster": "Activist",
        "aliases": ["1048445"],
    },
]

# Small, fixture-scaled config -- not the production signals_config.json values.
CFG = {"exit_below_pct": 5.0, "min_change_pp": 0.1, "recent_events": 300, "max_events_per_doc": 500, "start_date": "2024-12-18"}

STR_COLS = {"accession": str, "filer_cik": str, "reporting_ciks": str, "issuer_cik": str, "cusip": str, "prev_accession": str}


@pytest.fixture
def tables() -> dict:
    filings = pd.read_csv(FIXTURE, dtype=STR_COLS)
    # None of the fixture's dummy CUSIPs resolve to a real ticker -- mirrors enrich.attach's
    # "_"+cusip fallback so build_issuer_docs has something to key by.
    filings["symbol"] = "_" + filings["cusip"]
    filings["sector"] = "Unknown"
    return derive_all(filings, FUNDS, CFG)


def test_feed_events_newest_first_and_capped(tables):
    feed = build_feed(tables, CFG)
    dates = [e["filedAt"] for e in feed["events"]]
    assert dates == sorted(dates, reverse=True)
    assert len(feed["events"]) <= CFG["recent_events"]


def test_issuer_doc_keyed_by_unresolved_symbol(tables):
    docs = build_issuer_docs(tables, CFG)
    key = quote("_AAA000000", safe="")
    assert key in docs
    assert docs[key]["symbol"] == "_AAA000000"


def test_issuer_docs_only_symbols_filters(tables):
    docs = build_issuer_docs(tables, CFG, only_symbols={"_AAA000000"})
    assert set(docs) == {"_AAA000000"}


def test_investor_docs_only_ciks_filters(tables):
    docs = build_investor_docs(tables, FUNDS, CFG, only_ciks={"1791786"})
    assert set(docs) == {"1791786"}


def test_elliott_alias_investor_doc(tables):
    docs = build_investor_docs(tables, FUNDS, CFG)
    elliott = docs["1791786"]
    assert elliott["isRoster"] is True
    assert elliott["isActivist"] is True
    assert elliott["short"] == "Elliott"


def test_docs_are_json_serializable(tables):
    feed = build_feed(tables, CFG)
    feed["updatedAt"] = "SERVER_TIMESTAMP"  # not JSON-serializable, and not under test here
    json.dumps(feed)
    for doc in build_issuer_docs(tables, CFG).values():
        json.dumps(doc)
    for doc in build_investor_docs(tables, FUNDS, CFG).values():
        json.dumps(doc)
