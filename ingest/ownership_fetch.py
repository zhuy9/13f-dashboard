"""EDGAR Schedule 13D/13G listing and structured-XML parsing (mandatory since 2024-12-18).
`Schedule13D`/`Schedule13G` don't read `headerData` -- `header_fields` does that."""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import edgar
import pandas as pd
from edgar.beneficial_ownership.schedule13 import Schedule13D, Schedule13G

FORMS = ["SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A"]

# Produced by `parse_filing`. `ticker`/`sector`/`symbol` are attached later by
# `enrich.attach`, same split as `fetch.BASE_COLUMNS` for 13F.
FILING_COLUMNS = (
    "accession form is_amendment amendment_no filed_at event_date filer_cik "
    "reporting_ciks investor_name issuer_cik issuer_name cusip shares pct "
    "purpose prev_accession url"
).split()


def roster_ciks(funds: list[dict]) -> dict[str, str]:
    """Every roster CIK and alias (unpadded string) -> the roster's primary CIK."""
    mapping: dict[str, str] = {}
    for fund in funds:
        mapping[fund["cik"]] = fund["cik"]
        for alias in fund.get("aliases", []):
            mapping[alias] = fund["cik"]
    return mapping


def list_filings(funds: list[dict], since: str, until: str) -> pd.DataFrame:
    """New 13D (universe-wide) + 13G (roster only) filings in `[since, until]`, deduped.

    The index lists a filing once per associated CIK (subject company + every filer), so the
    surviving row's `cik` may be the subject company -- `header_fields` finds the real filer."""
    roster = roster_ciks(funds)
    filings = edgar.get_filings(form=FORMS, filing_date=f"{since}:{until}", amendments=True)
    df = filings.to_pandas().drop_duplicates("accession_number")

    is_13d = df["form"].str.startswith("SCHEDULE 13D")
    is_roster_13g = df["form"].str.startswith("SCHEDULE 13G") & df["cik"].astype(str).isin(roster)
    df = df[is_13d | is_roster_13g]

    out = df[["accession_number", "form", "filing_date", "cik", "company"]].copy()
    out["filing_date"] = out["filing_date"].astype(str)  # to_pandas() gives datetime.date, not str
    return out.rename(columns={"accession_number": "accession", "form": "form_raw"}).reset_index(drop=True)


def to_filing(row) -> "edgar.Filing":
    # Positional, matching Filing's own (cik, company, form, filing_date, accession_no) order.
    return edgar.Filing(int(row.cik), row.company, row.form_raw, row.filing_date, row.accession)


def filing_url(filer_cik: str, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(filer_cik)}/{accession.replace('-', '')}/{accession}-index.html"


def header_fields(xml: str) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """(filer_cik 10-digit, amendment_no, previous_accession) from the XML `headerData`."""
    root = ET.fromstring(xml)
    cik_el = root.find(".//{*}filerCredentials/{*}cik")
    filer_cik = cik_el.text.strip().zfill(10) if cik_el is not None and cik_el.text else None
    amendment_el = root.find(".//{*}coverPageHeader/{*}amendmentNo")
    amendment_no = int(amendment_el.text.strip()) if amendment_el is not None and amendment_el.text else None
    prev_el = root.find(".//{*}previousAccessionNumber")
    prev_accession = prev_el.text.strip() if prev_el is not None and prev_el.text else None
    return filer_cik, amendment_no, prev_accession


def _iso_date(mmddyyyy: Optional[str]) -> Optional[str]:
    if not mmddyyyy:
        return None
    return datetime.strptime(mmddyyyy, "%m/%d/%Y").date().isoformat()


def parse_filing(xml: str, form_raw: str, accession: str, filed_at: str, company: str, cfg: dict) -> Optional[dict]:
    """One `xml()` string -> one FILING_COLUMNS row, or None when it can't be parsed."""
    is_13d = form_raw.startswith("SCHEDULE 13D")
    schedule_cls = Schedule13D if is_13d else Schedule13G
    try:
        parsed = schedule_cls.parse_xml(xml)
    except ValueError:
        return None
    # `filing` is a required constructor arg but nothing below reads its own fields.
    dummy_filing = edgar.Filing(0, company, form_raw, filed_at, accession)
    obj = schedule_cls(filing=dummy_filing, amendment_number=None, **parsed)

    filer_cik, amendment_no, prev_accession = header_fields(xml)
    reporting_ciks = [p.cik.strip().zfill(10) for p in obj.reporting_persons if p.cik and p.cik.strip()]
    filer_cik = filer_cik or (reporting_ciks[0] if reporting_ciks else None)
    if not filer_cik:
        return None

    matched = next((p for p in obj.reporting_persons if p.cik and p.cik.strip().zfill(10) == filer_cik), None)
    if matched:
        investor_name = matched.name
    elif obj.reporting_persons:
        investor_name = obj.reporting_persons[0].name
    else:
        investor_name = company
    has_persons = bool(obj.reporting_persons)
    pct = obj.total_percent if has_persons else None
    shares = obj.total_shares if has_persons else None

    purpose = None
    if is_13d and obj.items.item4_purpose_of_transaction:
        purpose = obj.items.item4_purpose_of_transaction[: cfg["purpose_max_chars"]]

    issuer_cik = obj.issuer_info.cik.strip().zfill(10) if obj.issuer_info.cik else None

    return {
        "accession": accession,
        "form": "13D" if is_13d else "13G",
        "is_amendment": form_raw.endswith("/A"),
        "amendment_no": amendment_no,
        "filed_at": filed_at,
        "event_date": _iso_date(obj.event_date),
        "filer_cik": filer_cik,
        "reporting_ciks": reporting_ciks,
        "investor_name": investor_name,
        "issuer_cik": issuer_cik,
        "issuer_name": obj.issuer_info.name or None,
        "cusip": obj.issuer_info.cusip or None,
        "shares": shares,
        "pct": pct,
        "purpose": purpose,
        "prev_accession": prev_accession,
        "url": filing_url(filer_cik, accession),
    }


def fetch_rows(listed: pd.DataFrame, cfg: dict) -> tuple[list[dict], dict[str, str], int]:
    """(new filing rows, raw XML by accession, failed count). Per-filing try/except: warn and continue."""
    rows: list[dict] = []
    raw_by_accession: dict[str, str] = {}
    failed = 0

    for row in listed.itertuples():
        try:
            xml = to_filing(row).xml()
        except Exception as e:
            print(f"WARNING: {row.accession} fetch failed: {e}")
            failed += 1
            continue
        if not xml:
            print(f"WARNING: {row.accession} has no structured XML; skipping (retried within the refetch window)")
            failed += 1
            continue
        parsed_row = parse_filing(xml, row.form_raw, row.accession, row.filing_date, row.company, cfg)
        if parsed_row is None:
            print(f"WARNING: {row.accession} could not be parsed; skipping")
            failed += 1
            continue
        rows.append(parsed_row)
        raw_by_accession[row.accession] = xml

    return rows, raw_by_accession, failed
