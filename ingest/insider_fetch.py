"""EDGAR Form 4/4-A listing and parsing. `Form4.from_xml` is broken (raises `TypeError`
on this edgartools version) -- call `parse_xml`, same trap as Schedule13D in Milestone 8."""

import re
from typing import Optional

import edgar
import pandas as pd
from edgar.ownership import Form4

from ownership_fetch import filing_url

FORMS = ["4", "4/A"]

# Produced by `parse_filing`. `sector` is attached later from `stocks/{symbol}`, same
# split as the other two pipelines -- Form 4 carries no CUSIP, so no enrich step runs here.
TRANSACTION_COLUMNS = (
    "accession form is_amendment filed_at transaction_date issuer_cik issuer_name symbol "
    "owner_cik owner_name is_director is_officer is_ten_pct_owner officer_title "
    "is_derivative security code shares price value acquired_disposed shares_after "
    "aff10b5_one footnotes url"
).split()


def universe_ciks(holder_counts: Optional[dict], ticker_to_cik: dict[str, str], cfg: dict) -> tuple[set[int], dict[str, str]]:
    """Issuer CIKs (int) for symbols held by >= `universe_min_holders` tracked managers at the
    latest 13F quarter, plus the `{cik10: symbol}` map `parse_filing` resolves symbols with.

    `holder_counts is None` means ingest has never run -- that is not an empty universe."""
    if holder_counts is None:
        raise ValueError("meta/holder_counts is missing; run ingest.py before insider.py")

    min_holders = cfg["universe_min_holders"]
    ciks: set[int] = set()
    symbol_by_cik: dict[str, str] = {}
    for symbol, n in holder_counts.items():
        if n < min_holders:
            continue
        cik10 = ticker_to_cik.get(symbol)
        if not cik10:
            continue
        ciks.add(int(cik10))
        symbol_by_cik[cik10] = symbol
    return ciks, symbol_by_cik


def list_filings(issuer_ciks: set[int], since: str, until: str) -> pd.DataFrame:
    """New Form 4/4-A filings on our issuer universe in `[since, until]`, deduped.

    The index lists a filing once per associated CIK (issuer + every reporting owner), so
    filtering on the issuer CIK *before* `drop_duplicates` selects exactly our universe's
    filings in one listing request."""
    filings = edgar.get_filings(form=FORMS, filing_date=f"{since}:{until}")
    df = filings.to_pandas()
    df = df[df["cik"].isin(issuer_ciks)].drop_duplicates("accession_number")

    out = df[["accession_number", "form", "filing_date", "cik", "company"]].copy()
    out["filing_date"] = out["filing_date"].astype(str)
    return out.rename(columns={"accession_number": "accession", "form": "form_raw"}).reset_index(drop=True)


def to_filing(row) -> "edgar.Filing":
    return edgar.Filing(int(row.cik), row.company, row.form_raw, row.filing_date, row.accession)


def _footnote_text(footnotes, ids: str, max_chars: int) -> str:
    text = " ".join(footnotes.get(fid, "") for fid in re.split(r"[,\s]+", ids) if fid)
    return text[:max_chars]


def _transaction_rows(obj: Form4) -> list[tuple[bool, dict]]:
    """Every row of `non_derivative_table`/`derivative_table`, tagged with `is_derivative`.

    These raw tables carry `AcquiredDisposed`/`Remaining` per row; the higher-level
    `to_dataframe()`/`get_transaction_activities()` summaries don't, so this reads the
    tables directly instead."""
    rows = []
    for is_derivative, table in ((False, obj.non_derivative_table), (True, obj.derivative_table)):
        data = table.transactions.data
        if data is None or data.empty:
            continue
        rows += [(is_derivative, rec) for rec in data.to_dict("records")]
    return rows


def parse_filing(
    xml: str, form_raw: str, accession: str, filed_at: str, company: str, symbol_by_cik: dict[str, str], cfg: dict
) -> list[dict]:
    """One `xml()` string -> one row per (transaction, reporting owner). `[]`, not `None`,
    when the filing has no transactions or no reporting owners -- both malformed, not empty."""
    obj = Form4.parse_xml(xml)
    owners = list(obj.reporting_owners)
    if not owners:
        print(f"WARNING: {accession} has no reporting owners; skipping")
        return []

    transactions = _transaction_rows(obj)
    if not transactions:
        print(f"WARNING: {accession} has no transactions; skipping")
        return []

    issuer_cik = (obj.issuer.cik or "").zfill(10) or None
    # Resolution order: our own ticker->CIK map, then the XML's own ticker, then a fallback.
    symbol = symbol_by_cik.get(issuer_cik) or obj.issuer.ticker or f"_ISSUER{issuer_cik}"
    url = filing_url(issuer_cik, accession)

    rows = []
    for owner in owners:
        for is_derivative, rec in transactions:
            price = rec.get("Price")
            shares = rec.get("Shares")
            value = shares * price if price else None
            rows.append(
                {
                    "accession": accession,
                    "form": "4",
                    "is_amendment": form_raw.endswith("/A"),
                    "filed_at": filed_at,
                    "transaction_date": rec.get("Date"),
                    "issuer_cik": issuer_cik,
                    "issuer_name": obj.issuer.name or company,
                    "symbol": symbol,
                    "owner_cik": (owner.cik or "").zfill(10),
                    "owner_name": owner.name,
                    "is_director": bool(owner.is_director),
                    "is_officer": bool(owner.is_officer),
                    "is_ten_pct_owner": bool(owner.is_ten_pct_owner),
                    "officer_title": owner.officer_title or None,
                    "is_derivative": is_derivative,
                    "security": rec.get("Security"),
                    "code": rec.get("Code"),
                    "shares": shares,
                    "price": price,
                    "value": value,
                    "acquired_disposed": rec.get("AcquiredDisposed"),
                    "shares_after": rec.get("Remaining"),
                    "aff10b5_one": obj.aff10b5_one,
                    "footnotes": _footnote_text(obj.footnotes, rec.get("footnotes") or "", cfg["footnote_max_chars"]),
                    "url": url,
                }
            )
    return rows


def fetch_rows(listed: pd.DataFrame, symbol_by_cik: dict[str, str], cfg: dict) -> tuple[list[dict], dict[str, str], int]:
    """(new transaction rows, raw XML by accession, failed count). Per-filing try/except:
    warn and continue, same contract as `ownership_fetch.fetch_rows`."""
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
        try:
            parsed_rows = parse_filing(xml, row.form_raw, row.accession, row.filing_date, row.company, symbol_by_cik, cfg)
        except Exception as e:
            print(f"WARNING: {row.accession} could not be parsed; skipping ({e})")
            failed += 1
            continue
        rows += parsed_rows
        raw_by_accession[row.accession] = xml

    return rows, raw_by_accession, failed
