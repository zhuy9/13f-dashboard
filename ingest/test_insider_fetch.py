import re
from pathlib import Path

import pytest

import insider_fetch as ifetch

FIXTURES = Path(__file__).parent / "fixtures"
XML_BUY = (FIXTURES / "insider_form4_buy.xml").read_text(encoding="utf-8")
XML_PLANNED_SALE = (FIXTURES / "insider_form4_planned_sale.xml").read_text(encoding="utf-8")
XML_AWARD_TAX = (FIXTURES / "insider_form4_award_and_tax.xml").read_text(encoding="utf-8")

# Small, fixture-scaled config -- not the production signals_config.json values.
CFG = {"footnote_max_chars": 300}

SYMBOL_BY_CIK = {"0000101382": "UMBF", "0000320193": "AAPL", "0000789019": "MSFT"}

# list_filings() is untested here -- it's a single edgar.get_filings() network call.


@pytest.fixture(autouse=True)
def no_network_owner_lookup(monkeypatch):
    """`Form4.parse_xml` asks `edgar.entity.Entity(cik).data.is_company` per reporting owner
    to decide whether to reverse the name -- a real network call baked into edgartools itself,
    unrelated to anything in `insider_fetch.py`. Every fixture owner here is an individual."""

    class FakeEntityData:
        is_company = False

    class FakeEntity:
        def __init__(self, cik):
            pass

        def __bool__(self):
            return True

        data = FakeEntityData()

    monkeypatch.setattr("edgar.ownership.owners.Entity", FakeEntity)


def test_parse_filing_buy():
    rows = ifetch.parse_filing(XML_BUY, "4", "ACC1", "2026-09-03", "UMB Financial Corp", SYMBOL_BY_CIK, CFG)
    assert len(rows) == 1
    row = rows[0]
    assert row["code"] == "P"
    assert row["symbol"] == "UMBF"
    assert row["shares"] == 394.0553
    assert row["price"] == 139.60
    assert row["value"] == pytest.approx(394.0553 * 139.60)
    assert row["is_director"] is True
    assert row["is_officer"] is False
    assert row["is_ten_pct_owner"] is False
    assert row["is_derivative"] is False
    assert row["url"].endswith("ACC1-index.html")


def test_parse_filing_planned_sale():
    rows = ifetch.parse_filing(XML_PLANNED_SALE, "4", "ACC2", "2026-09-03", "Apple Inc.", SYMBOL_BY_CIK, CFG)
    assert len(rows) == 1
    assert rows[0]["code"] == "S"
    assert rows[0]["aff10b5_one"] is True


def test_parse_filing_award_and_tax():
    rows = ifetch.parse_filing(XML_AWARD_TAX, "4", "ACC3", "2026-09-01", "Microsoft Corp", SYMBOL_BY_CIK, CFG)
    assert {r["code"] for r in rows} == {"A", "F"}
    assert rows[0]["officer_title"] == "EVP, Chief Commercial Officer"


def test_parse_filing_amendment_flag():
    rows = ifetch.parse_filing(XML_BUY, "4/A", "ACC1A", "2026-09-03", "UMB Financial Corp", SYMBOL_BY_CIK, CFG)
    assert rows[0]["is_amendment"] is True


def test_parse_filing_no_reporting_owner_returns_empty_and_warns(capsys):
    stripped = re.sub(r"<reportingOwner>.*?</reportingOwner>", "", XML_BUY, flags=re.S)
    rows = ifetch.parse_filing(stripped, "4", "ACC4", "2026-09-03", "UMB Financial Corp", SYMBOL_BY_CIK, CFG)
    assert rows == []
    assert "no reporting owners" in capsys.readouterr().out


def test_universe_ciks_raises_when_holder_counts_missing():
    with pytest.raises(ValueError):
        ifetch.universe_ciks(None, {}, {"universe_min_holders": 1})


def test_universe_ciks_honours_min_holders():
    holder_counts = {"AAPL": 5, "MSFT": 0}
    ticker_to_cik = {"AAPL": "0000320193", "MSFT": "0000789019"}
    ciks, symbol_by_cik = ifetch.universe_ciks(holder_counts, ticker_to_cik, {"universe_min_holders": 1})
    assert ciks == {320193}
    assert symbol_by_cik == {"0000320193": "AAPL"}
