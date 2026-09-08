from types import SimpleNamespace

import pandas as pd

from enrich import attach, ensure_securities, sec_ticker_to_cik


class _FakeDb:
    """Just enough Firestore for ensure_securities: an empty cache that records what it writes."""

    def __init__(self, cached: dict | None = None):
        self.written, self.cached = {}, cached or {}

    def collection(self, _name):
        return SimpleNamespace(document=lambda cusip: cusip)

    def get_all(self, _refs):
        return [SimpleNamespace(exists=True, id=c, to_dict=lambda doc=doc: doc) for c, doc in self.cached.items()]

    def batch(self):
        return SimpleNamespace(set=self.written.__setitem__, commit=lambda: None)


def test_refresh_all_rebuilds_a_cached_entry_that_refresh_unknown_would_skip(monkeypatch):
    """The ETP rule landed after these entries were cached. A fund already stored as Financials
    is not Unknown, so only refresh="all" revisits it."""
    monkeypatch.setattr("enrich.openfigi_map", lambda cusips, key: {"046428715": {"ticker": "ITOT", "securityType": "ETP"}})
    monkeypatch.setattr("enrich.sec_ticker_to_cik", lambda identity: {"ITOT": "0000000001"})
    monkeypatch.setattr("enrich.sec_sic", lambda cik, identity: (6726, "Investment Offices"))
    stale = {"cusip": "046428715", "ticker": "ITOT", "sector": "Financials"}

    def sector(refresh: str) -> str:
        db = _FakeDb({"046428715": dict(stale)})
        return ensure_securities(db, ["046428715"], "a@b.com", None, refresh)["046428715"]["sector"]

    assert sector("none") == "Financials"
    assert sector("unknown") == "Financials"
    assert sector("all") == "ETF / Fund"


def _enrich_one(monkeypatch, cusip, ticker, security_type, sic) -> dict:
    monkeypatch.setattr("enrich.openfigi_map", lambda cusips, key: {cusip: {"ticker": ticker, "securityType": security_type}})
    monkeypatch.setattr("enrich.sec_ticker_to_cik", lambda identity: {ticker: "0000000001"})
    monkeypatch.setattr("enrich.sec_sic", lambda cik, identity: (sic, "desc"))
    return ensure_securities(_FakeDb(), [cusip], "a@b.com")[cusip]


def test_an_etf_is_sectored_from_openfigi_not_from_its_sic(monkeypatch):
    """securityType is the only field that says "ETF" -- securityType2 says "Mutual Fund". An ETF's SIC is 6726, investment
    offices, which the range table would otherwise file under Financials."""
    itot = _enrich_one(monkeypatch, "046428715", "ITOT", "ETP", 6726)

    assert itot["sector"] == "ETF / Fund"
    assert itot["sic"] == 6726  # still recorded, just no longer what decides


def test_persist_false_enriches_in_memory_and_writes_no_cache_entry(monkeypatch):
    """A dry run must not advance remote state, and the securities/ cache is remote state.
    The enriched entry is still returned, so the run's own output is unaffected."""
    monkeypatch.setattr("enrich.openfigi_map", lambda cusips, key: {"037833100": {"ticker": "AAPL", "securityType": "Common"}})
    monkeypatch.setattr("enrich.sec_ticker_to_cik", lambda identity: {"AAPL": "0000320193"})
    monkeypatch.setattr("enrich.sec_sic", lambda cik, identity: (3571, "Electronic Computers"))
    db = _FakeDb()  # empty cache: a miss, the case that would otherwise write

    out = ensure_securities(db, ["037833100"], "a@b.com", None, "none", None, persist=False)

    assert out["037833100"]["ticker"] == "AAPL"
    assert db.written == {}


def test_a_ticker_rename_keeps_one_continuous_position_and_share_classes_stay_apart():
    """Identifier continuity comes from the cache being keyed by CUSIP, not by ticker: one
    cached entry per security supplies the symbol for every quarter, so a company that renamed
    its ticker does not split into two symbols mid-history and read as a sell plus a buy.

    Two share classes carry two CUSIPs, so they stay two positions -- which is right. They are
    separately reported securities, not one holding to be merged."""
    securities = {
        "38259P508": {"ticker": "GOOGL", "sector": "Tech"},  # renamed from GOOG in 2014
        "02079K107": {"ticker": "GOOG", "sector": "Tech"},  # the other class, its own CUSIP
    }
    filed_over_two_quarters = pd.DataFrame(
        {
            "cusip": ["38259P508", "38259P508", "02079K107"],
            "period": ["2026-03-31", "2026-06-30", "2026-06-30"],
        }
    )

    out = attach(filed_over_two_quarters, securities)

    assert list(out["symbol"]) == ["GOOGL", "GOOGL", "GOOG"]
    assert out[out["period"] == "2026-06-30"]["symbol"].nunique() == 2


def test_a_deregistered_ticker_still_resolves_to_its_cik(monkeypatch):
    """A company that goes private is dropped from company_tickers.json, and without a CIK it
    gets no SIC and therefore no sector. ticker.txt keeps it, so the gap is fillable -- 15% of
    the symbols on the site were sitting in Unknown for exactly this reason, and an
    event-driven manager holds acquisition targets on purpose."""

    class _Resp:
        def __init__(self, text="", payload=None):
            self.text, self._payload = text, payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    def fake_get(url, headers, timeout):
        if url.endswith("ticker.txt"):
            return _Resp(text="ea\t712515\naapl\t320193\n")  # ticker.txt keeps EA
        return _Resp(payload={"0": {"ticker": "AAPL", "cik_str": 320193}})  # json dropped it

    monkeypatch.setattr("enrich.requests.get", fake_get)

    mapping = sec_ticker_to_cik("a@b.com")

    assert mapping["EA"] == "0000712515", "a deregistered ticker must still resolve"
    assert mapping["AAPL"] == "0000320193"


def test_the_maintained_list_wins_when_a_ticker_appears_in_both(monkeypatch):
    """A ticker can be reassigned to a different company after the first one leaves. The
    maintained list says who holds it now, so it has to override the archival one."""

    class _Resp:
        def __init__(self, text="", payload=None):
            self.text, self._payload = text, payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    def fake_get(url, headers, timeout):
        if url.endswith("ticker.txt"):
            return _Resp(text="xyz\t111\n")
        return _Resp(payload={"0": {"ticker": "XYZ", "cik_str": 999}})

    monkeypatch.setattr("enrich.requests.get", fake_get)

    assert sec_ticker_to_cik("a@b.com")["XYZ"] == "0000000999"
