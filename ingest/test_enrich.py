from types import SimpleNamespace

from enrich import ensure_securities


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
