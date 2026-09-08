from types import SimpleNamespace

from enrich import ensure_securities


class _FakeDb:
    """Just enough Firestore for ensure_securities: an empty cache that records what it writes."""

    def __init__(self):
        self.written = {}

    def collection(self, _name):
        return SimpleNamespace(document=lambda cusip: cusip)

    def get_all(self, _refs):
        return []

    def batch(self):
        return SimpleNamespace(set=self.written.__setitem__, commit=lambda: None)


def _enrich_one(monkeypatch, cusip, ticker, security_type, sic) -> dict:
    monkeypatch.setattr("enrich.openfigi_map", lambda cusips, key: {cusip: {"ticker": ticker, "securityType2": security_type}})
    monkeypatch.setattr("enrich.sec_ticker_to_cik", lambda identity: {ticker: "0000000001"})
    monkeypatch.setattr("enrich.sec_sic", lambda cik, identity: (sic, "desc"))
    return ensure_securities(_FakeDb(), [cusip], "a@b.com")[cusip]


def test_an_etf_is_sectored_from_openfigi_not_from_its_sic(monkeypatch):
    """securityType2 is the only field that says "ETF". An ETF's SIC is 6726, investment
    offices, which the range table would otherwise file under Financials."""
    itot = _enrich_one(monkeypatch, "046428715", "ITOT", "ETP", 6726)

    assert itot["sector"] == "ETF / Fund"
    assert itot["sic"] == 6726  # still recorded, just no longer what decides


def test_a_common_stock_still_takes_its_sector_from_the_sic(monkeypatch):
    aapl = _enrich_one(monkeypatch, "037833100", "AAPL", "Common Stock", 3571)

    assert aapl["sector"] == "Technology"
