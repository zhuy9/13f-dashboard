import io
from types import SimpleNamespace

import pandas as pd
import pytest
import urllib3
from urllib3.connectionpool import HTTPConnectionPool

import enrich
from enrich import attach, cik_to_ticker, ensure_securities, openfigi_map, ticker_to_cik

# Synthetic CUSIPs and FIGIs throughout: real CUSIPs are licensed and stay out of the repo.
SECURITIES = [
    {"composite_figi": figi, "ticker": ticker, "security_type": kind, "cik": cik, "sector": sector, "status": "active"}
    for figi, ticker, kind, cik, sector in [
        ("BBG000000001", "BRK-B", "Common Stock", "0001067983", "Financials"),
        ("BBG000000002", "BRK-A", "Common Stock", "0001067983", "Financials"),
        ("BBG000000003", "IVV", "ETP", "0001100663", ""),
        ("BBG000000004", "PDI", "Closed-End Fund", "0001510599", ""),
        ("BBG000000005", "CB", "Common Stock", "0000896159", "Financials"),
        ("BBG000000006", "TSLA", "Common Stock", "0001318605", "Consumer Discretionary"),
        ("BBG000000007", "XYZ", "Common Stock", "0000000777", "Technology"),
        ("BBG000000008", "GOOGL", "Common Stock", "0001652044", "Communication"),
        ("BBG000000009", "GOOG", "Common Stock", "0001652044", "Communication"),
        ("BBG000000010", "DE", "Common Stock", "0000315189", "Industrials"),
    ]
]
ISSUERS = {
    "0001067983": {"sic": "6331", "sic_description": "Fire, Marine & Casualty Insurance"},
    "0000896159": {"sic": "6331", "sic_description": "Fire, Marine & Casualty Insurance"},
    "0001318605": {"sic": "3711", "sic_description": "Motor Vehicles & Passenger Car Bodies"},
    "0001100663": {"sic": "", "sic_description": ""},
}


@pytest.fixture(autouse=True)
def fake_security_master(monkeypatch):
    by_figi = {r["composite_figi"]: r for r in SECURITIES}
    by_ticker = {r["ticker"]: r for r in SECURITIES}

    def security(key):
        key = key.strip().upper()
        return by_figi.get(key) or by_ticker.get(key.replace(".", "-").replace("/", "-").replace(" ", "-"))

    fake = SimpleNamespace(security=security, issuer=lambda cik: ISSUERS.get(cik), securities=lambda: list(SECURITIES))
    monkeypatch.setattr(enrich, "sm", fake)


class _FakeDb:
    """Just enough Firestore for ensure_securities: a cache that records what it writes."""

    def __init__(self, cached: dict | None = None):
        self.written, self.cached = {}, cached or {}

    def collection(self, _name):
        return SimpleNamespace(document=lambda cusip: cusip)

    def document(self, path):
        return path.removeprefix("securities/")

    def get_all(self, _refs):
        return [SimpleNamespace(exists=True, id=c, to_dict=lambda doc=doc: doc) for c, doc in self.cached.items()]

    def batch(self):
        return SimpleNamespace(set=self.written.__setitem__, commit=lambda: None)


def _enrich(monkeypatch, matches: dict, hints: dict | None = None, cached: dict | None = None, refresh="none", db=None):
    monkeypatch.setattr("enrich.openfigi_map", lambda cusips, key: {c: matches.get(c, {}) for c in cusips})
    db = db or _FakeDb(cached)
    return ensure_securities(db, list(matches) + list(cached or {}), None, refresh, hints), db


def test_a_security_resolves_by_figi_to_its_sec_form_ticker_cik_sic_and_sector(monkeypatch):
    out, db = _enrich(
        monkeypatch, {"00000A101": {"compositeFIGI": "BBG000000001", "ticker": "BRK/B"}}, hints={"00000A101": "BRKB"}
    )

    assert out["00000A101"] == {
        "cusip": "00000A101",
        "ticker": "BRK-B",  # SEC form, whatever form the hint or OpenFIGI used
        "cik": "0001067983",
        "sic": 6331,
        "sicDescription": "Fire, Marine & Casualty Insurance",
        "sector": "Financials",
    }
    assert db.written["00000A101"] == out["00000A101"]


def test_funds_are_etf_fund_whether_security_master_knows_them_or_not(monkeypatch):
    out, _ = _enrich(
        monkeypatch,
        {
            "00000E101": {"compositeFIGI": "BBG000000003", "securityType": "ETP"},
            "00000E202": {"compositeFIGI": "BBG000000004", "securityType": "Closed-End Fund"},
            # not in security-master yet
            "00000E303": {"compositeFIGI": "BBG0000000Z1", "ticker": "NEWETF", "securityType": "ETP"},
            "00000E404": {"compositeFIGI": "BBG0000000Z6", "ticker": "NEWCEF", "securityType": "Closed-End Fund"},
        },
    )

    assert {e["sector"] for e in out.values()} == {"ETF / Fund"}
    assert out["00000E303"]["ticker"] == "NEWETF" and out["00000E303"]["cik"] is None


def test_without_a_figi_a_foreign_issuer_resolves_by_its_ticker(monkeypatch):
    """OpenFIGI has no FIGI for many CINS CUSIPs (Chubb, ASML); edgartools' ticker covers them."""
    out, _ = _enrich(monkeypatch, {"H0000C101": {}}, hints={"H0000C101": "CB"})

    assert out["H0000C101"]["ticker"] == "CB" and out["H0000C101"]["sector"] == "Financials"


def test_a_figi_security_master_lacks_is_never_matched_by_a_ticker_someone_else_now_holds(monkeypatch):
    """XYZ was this company's ticker before it was acquired; a new company trades as XYZ now."""
    out, _ = _enrich(monkeypatch, {"00000X101": {"compositeFIGI": "BBG0000000Z2", "ticker": "XYZ"}}, hints={"00000X101": "XYZ"})

    assert out["00000X101"] == {
        "cusip": "00000X101",
        "ticker": "XYZ",
        "cik": None,
        "sic": None,
        "sicDescription": None,
        "sector": "Unknown",
    }


def test_a_note_or_warrant_keeps_its_own_symbol_but_takes_its_issuers_cik_and_sector(monkeypatch):
    out, _ = _enrich(
        monkeypatch,
        {
            "00000T101": {"compositeFIGI": "BBG0000000Z3", "ticker": "TSLA 2 05/15/24"},
            "00000T202": {"compositeFIGI": "BBG0000000Z4", "ticker": "TSLA/WS"},
        },
    )

    assert out["00000T101"]["ticker"] == "TSLA 2 05/15/24"  # never merged into the stock's page
    assert out["00000T101"]["cik"] == "0001318605" and out["00000T101"]["sector"] == "Consumer Discretionary"
    assert out["00000T202"]["ticker"] == "TSLA/WS" and out["00000T202"]["sector"] == "Consumer Discretionary"


def test_an_issuer_level_hint_never_relabels_a_preferred_as_the_stock(monkeypatch):
    """ownership's hint is the issuer's ticker, not the CUSIP's. OpenFIGI's own ticker says this
    is a preferred, so it keeps that symbol and only borrows the issuer's CIK and sector."""
    out, _ = _enrich(monkeypatch, {"00000P101": {"ticker": "TSLA 8.75 PERP D"}}, hints={"00000P101": "TSLA"})

    assert out["00000P101"]["ticker"] == "TSLA 8.75 PERP D" and out["00000P101"]["cik"] == "0001318605"


def test_a_muni_fund_preferreds_state_code_is_not_read_as_a_ticker(monkeypatch):
    out, _ = _enrich(monkeypatch, {"00000M101": {"ticker": "DE MIQGEN 07/02/2026"}})

    assert out["00000M101"]["cik"] is None and out["00000M101"]["sector"] == "Unknown"  # DE is Delaware, not Deere


def test_refresh_all_rewrites_what_security_master_knows_and_keeps_what_it_cannot(monkeypatch):
    """Cached before the cutover: Berkshire B (in security-master) and a company acquired before
    security-master began (not in it). A full refresh moves the first to SEC form and keeps the
    second exactly as it was cached."""
    cached = {
        "00000A101": {"cusip": "00000A101", "ticker": "BRKB", "cik": "0001067983", "sic": 6331, "sector": "Financials"},
        "00000H101": {"cusip": "00000H101", "ticker": "HES", "cik": "0000004447", "sic": 2911, "sector": "Energy & Mining"},
    }
    matches = {"00000A101": {"compositeFIGI": "BBG000000001"}, "00000H101": {"compositeFIGI": "BBG0000000Z5", "ticker": "HES"}}
    monkeypatch.setattr("enrich.openfigi_map", lambda cusips, key: {c: matches[c] for c in cusips})

    def run(refresh: str):
        db = _FakeDb({c: dict(e) for c, e in cached.items()})
        return ensure_securities(db, list(cached), None, refresh), db

    out, db = run("none")
    assert out == cached and db.written == {}
    out, db = run("all")
    assert out["00000A101"]["ticker"] == "BRK-B" and out["00000H101"] == cached["00000H101"]
    assert list(db.written) == ["00000A101"]


def test_refresh_unknown_only_revisits_entries_that_came_back_unknown(monkeypatch):
    cached = {
        "H0000C101": {"cusip": "H0000C101", "ticker": "CB", "cik": None, "sic": None, "sector": "Unknown"},
        "00000A101": {"cusip": "00000A101", "ticker": "BRKB", "cik": "0001067983", "sic": 6331, "sector": "Financials"},
    }
    matches = {"H0000C101": {}, "00000A101": {"compositeFIGI": "BBG000000001"}}
    monkeypatch.setattr("enrich.openfigi_map", lambda cusips, key: {c: matches[c] for c in cusips})
    db = _FakeDb({c: dict(e) for c, e in cached.items()})

    out = ensure_securities(db, list(cached), None, "unknown", {"H0000C101": "CB"})

    assert out["H0000C101"]["sector"] == "Financials" and out["00000A101"]["ticker"] == "BRKB"
    assert list(db.written) == ["H0000C101"]


def test_persist_false_enriches_in_memory_and_writes_no_cache_entry(monkeypatch):
    """A dry run must not advance remote state, and the securities/ cache is remote state."""
    monkeypatch.setattr("enrich.openfigi_map", lambda cusips, key: {"00000A101": {"compositeFIGI": "BBG000000001"}})
    db = _FakeDb()

    out = ensure_securities(db, ["00000A101"], None, "none", None, persist=False)

    assert out["00000A101"]["ticker"] == "BRK-B" and db.written == {}


def test_cik_maps_prefer_a_common_share_then_the_shortest_ticker():
    assert ticker_to_cik()["BRK-B"] == "0001067983" and ticker_to_cik()["IVV"] == "0001100663"
    assert cik_to_ticker()["0001067983"] == "BRK-A"  # same length: alphabetical
    assert cik_to_ticker()["0001652044"] == "GOOG"  # GOOG before GOOGL


def test_a_ticker_rename_keeps_one_continuous_position_and_share_classes_stay_apart():
    """Identifier continuity comes from the cache being keyed by CUSIP, not by ticker: one cached
    entry per security supplies the symbol for every quarter, so a renamed ticker does not split a
    holding into two symbols. Two share classes carry two CUSIPs and stay two positions."""
    securities = {"00000G101": {"ticker": "GOOGL", "sector": "Tech"}, "00000G202": {"ticker": "GOOG", "sector": "Tech"}}
    filed_over_two_quarters = pd.DataFrame(
        {"cusip": ["00000G101", "00000G101", "00000G202"], "period": ["2026-03-31", "2026-06-30", "2026-06-30"]}
    )

    out = attach(filed_over_two_quarters, securities)

    assert list(out["symbol"]) == ["GOOGL", "GOOGL", "GOOG"]
    assert out[out["period"] == "2026-06-30"]["symbol"].nunique() == 2


def _serve(monkeypatch, replies):
    """Answer HTTP requests from `replies` below requests/urllib3, so the real retry policy runs."""
    replies = iter(replies)

    def fake_make_request(self, conn, method, url, **kwargs):
        status, body = next(replies)
        return urllib3.HTTPResponse(body=io.BytesIO(body), status=status, preload_content=False)

    monkeypatch.setattr(HTTPConnectionPool, "_make_request", fake_make_request)
    monkeypatch.setattr("urllib3.util.retry.time.sleep", lambda s: None)


def test_an_openfigi_rate_limit_is_retried_on_the_post(monkeypatch):
    """OpenFIGI's mapping call is a POST, which urllib3 does not retry unless told to."""
    _serve(
        monkeypatch, [(429, b""), (200, b'[{"data": [{"ticker": "BRK/B", "exchCode": "US", "compositeFIGI": "BBG000000001"}]}]')]
    )

    assert openfigi_map(["00000A101"])["00000A101"]["compositeFIGI"] == "BBG000000001"
