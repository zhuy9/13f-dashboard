import re
from pathlib import Path

from ownership_fetch import header_fields, parse_filing, roster_ciks

FIXTURES = Path(__file__).parent / "fixtures"
XML_13D = (FIXTURES / "ownership_13d.xml").read_text(encoding="utf-8")
XML_13G = (FIXTURES / "ownership_13g.xml").read_text(encoding="utf-8")

# Small, fixture-scaled config -- not the production signals_config.json values.
CFG = {"purpose_max_chars": 400}

FUNDS = [
    {"cik": "1791786", "short": "Elliott", "cluster": "Activist", "aliases": ["1048445"]},
]

# list_filings() is untested here -- it's a single edgar.get_filings() network call.


def test_header_fields_reads_amendment_and_previous_accession():
    assert header_fields(XML_13D) == ("0001791786", 3, "0000902664-23-002314")


def test_header_fields_no_amendment_no_previous_for_initial_filing():
    assert header_fields(XML_13G) == ("0001791786", None, None)


def test_parse_filing_13d_amendment():
    row = parse_filing(XML_13D, "SCHEDULE 13D/A", "0000919574-26-004169", "2026-06-30", "Elliott Investment Management L.P.", CFG)
    assert row["form"] == "13D"
    assert row["is_amendment"] is True
    assert row["pct"] == 64.7
    assert row["shares"] == 133241535
    assert row["issuer_cik"] == "0001829726"
    assert row["cusip"] == "89679M104"
    assert row["event_date"] == "2026-06-30"
    assert row["url"].endswith("0000919574-26-004169-index.html")


def test_parse_filing_13g_initial():
    row = parse_filing(XML_13G, "SCHEDULE 13G", "0000919574-26-005513", "2026-08-14", "Elliott Investment Management L.P.", CFG)
    assert row["form"] == "13G"
    assert row["is_amendment"] is False
    assert row["pct"] == 5.8
    assert row["purpose"] is None


def test_parse_filing_no_reporting_persons_gives_null_pct():
    xml_no_persons = re.sub(r"<reportingPersons>.*?</reportingPersons>", "", XML_13D, flags=re.DOTALL)
    row = parse_filing(
        xml_no_persons, "SCHEDULE 13D/A", "0000919574-26-004169", "2026-06-30", "Elliott Investment Management L.P.", CFG
    )
    assert row["pct"] is None
    assert row["shares"] is None
    # No reporting person carries the filer's CIK either, so identity falls back to the header.
    assert row["filer_cik"] == "0001791786"


def test_roster_ciks_maps_alias_to_primary():
    mapping = roster_ciks(FUNDS)
    assert mapping["1048445"] == "1791786"
    assert mapping["1791786"] == "1791786"
