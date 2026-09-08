"""EDGAR 13F-HR fetch and normalize into base-table rows (minus symbol/ticker/sector)."""

from typing import NamedTuple, Optional

import numpy as np
import pandas as pd
from edgar import Company

BASE_COLUMNS = [
    "cik",
    "short",
    "period",
    "filed_at",
    "accession",
    "disclosed_by_amendment",
    "cusip",
    "name",
    "cls",
    "value",
    "shares",
    "put_call",
]

# Uppercased strings a stringified null leaves behind, plus the empty cell. No real US ticker.
_NOT_A_TICKER = {"", "NAN", "NONE", "NULL", "NA"}

_printed_columns = False


def fetch_filings(cik: str, quarters: int) -> list:
    """Every 13F-HR and 13F-HR/A filing covering the newest `quarters` report periods.

    The window is counted in report periods, not filings: an amended quarter has two or three
    filings, and slicing the filing list would silently drop the oldest quarter whenever a
    manager amended a recent one.
    """
    company = Company(cik)
    filings = list(company.get_filings(form="13F-HR", amendments=True))
    wanted = sorted({f.report_date for f in filings}, reverse=True)[:quarters]
    return [f for f in filings if f.report_date in wanted]


class Filing(NamedTuple):
    """One parsed 13F filing. `amendment_type` is edgartools' own reading of the cover page:
    "RESTATEMENT" (re-files the whole report), "NEW HOLDINGS" (adds previously-confidential
    positions only), or None when the filing is not an amendment or does not say."""

    accession: str
    url: str
    period: str
    filed_at: str
    is_amendment: bool
    amendment_type: Optional[str]
    amendment_no: int
    raw_xml: Optional[bytes]
    holdings: pd.DataFrame


def filing_rows(filing) -> Filing:
    global _printed_columns
    obj = filing.obj()
    df = obj.holdings
    if not _printed_columns:
        print("13F holdings columns:", df.columns.tolist())
        _printed_columns = True
    return Filing(
        accession=str(obj.accession_number),
        # The library's own accessor, not a URL we assemble: an accession's leading digits are
        # the filing agent's id, not the manager's CIK, so this cannot be rebuilt from the row.
        url=filing.homepage_url,
        period=str(obj.report_period),
        filed_at=str(filing.filing_date),
        is_amendment=bool(obj.is_amendment),
        amendment_type=obj.amendment_type,
        amendment_no=obj.amendment_number or 0,
        raw_xml=obj.infotable_xml.encode("utf-8") if obj.has_infotable() else None,
        holdings=df,
    )


def resolve_amendments(parsed: list[Filing]) -> tuple[list[tuple[Filing, pd.DataFrame]], list[str]]:
    """Which rows of one (cik, period)'s filings actually count, and what was skipped.

    A 13F-HR/A is not a second quarter of data, it is a correction to the first, and the two
    kinds do opposite things:

    - RESTATEMENT re-files the whole report and replaces what came before it.
    - NEW HOLDINGS adds positions that were previously confidential and must be unioned with
      the original. Letting it replace the original would drop the real portfolio.

    An amendment with no type is skipped and reported, never guessed at. Guessing wrong in one
    direction double-counts a restatement, and in the other direction deletes a portfolio, and
    the whole point of this function is that neither happens silently.
    `# ponytail:` the current 12-quarter window is entirely XML-era, where the cover page
    always carries the type. Revisit if the window ever reaches back to TXT-only filings.

    Returns (kept, notes): `kept` pairs each contributing filing with the rows it contributed,
    so a caller can tell which accession a holding came from.
    """
    by_accession = {f.accession: f for f in parsed}  # one filing counts once, however it arrived
    ordered = sorted(by_accession.values(), key=lambda f: (f.is_amendment, f.amendment_no, f.filed_at, f.accession))

    kept: list[tuple[Filing, pd.DataFrame]] = []
    notes: list[str] = []
    for filing in ordered:
        if not filing.is_amendment:
            kept.append((filing, filing.holdings))
            continue
        if filing.amendment_type == "RESTATEMENT":
            # Replaces everything so far, including an earlier amendment.
            kept = [(filing, filing.holdings)]
        elif filing.amendment_type == "NEW HOLDINGS":
            seen = _held_keys(kept)
            addition = filing.holdings[~_row_keys(filing.holdings).isin(seen)]
            if len(addition):
                kept.append((filing, addition))
            if len(addition) < len(filing.holdings):
                notes.append(
                    f"{filing.period}: {filing.accession} re-reported "
                    f"{len(filing.holdings) - len(addition)} holding(s) already on file; counted once"
                )
        else:
            notes.append(f"{filing.period}: {filing.accession} is an amendment with no type on its cover page; skipped")

    # Judged on what arrived, not on what survived: a restatement is *supposed* to leave only
    # itself in `kept`, and warning about that would cry wolf on the normal case.
    if ordered and all(filing.is_amendment for filing in ordered):
        notes.append(f"{ordered[0].period}: only amended filings are in the window; no original to compare against")
    return kept, notes


def _row_keys(df: pd.DataFrame) -> pd.Series:
    """The identity of a holding within one filing, for spotting a re-reported position."""
    return df["Cusip"].astype(str).str.strip() + "|" + df["PutCall"].astype(str).str.strip().str.upper()


def _held_keys(kept: list[tuple[Filing, pd.DataFrame]]) -> set[str]:
    return {key for _, df in kept for key in _row_keys(df)}


def filed_notice(cik: str, period: str) -> bool:
    """True when `cik` filed a 13F-NT for `period`: a notice that it holds positions but reported
    none itself, because another manager filed them. That manager's name and CIK are on the
    notice's cover page under "List of Other Managers Reporting for this Manager", and the CIK
    belongs in the fund's `aliases13f`. Without this check the quarter just looks empty."""
    return any(str(f.report_date) == period for f in Company(cik).get_filings(form="13F-NT", amendments=False))


def collapse(rows: pd.DataFrame) -> pd.DataFrame:
    """Sum duplicates into the one row per (cik, period, cusip, put_call) the base table promises.

    Duplicates come from one filing repeating a security, or from an `aliases13f` book split
    across two filer CIKs in the same quarter."""
    if rows.empty:
        return rows[BASE_COLUMNS]
    grouped = rows.groupby(["cik", "period", "cusip", "put_call"], dropna=False, as_index=False).agg(
        short=("short", "first"),
        filed_at=("filed_at", "first"),
        # Every accession that fed the row, so a summed position stays traceable to its sources.
        accession=("accession", lambda s: ",".join(sorted(set(s)))),
        disclosed_by_amendment=("disclosed_by_amendment", "max"),
        name=("name", "first"),
        cls=("cls", "first"),
        value=("value", "sum"),
        shares=("shares", "sum"),
    )
    return grouped[BASE_COLUMNS].reset_index(drop=True)


def normalize(df: pd.DataFrame, cik: str, short: str, filing: Filing) -> pd.DataFrame:
    """Raw holdings DataFrame -> base-table rows for one filing.

    `df` is passed separately from `filing.holdings` because an additive amendment contributes
    only the subset of its rows that `resolve_amendments` accepted.
    """
    raw_put_call = df["PutCall"].astype(str).str.strip().str.upper()
    put_call = raw_put_call.mask(raw_put_call.isin(["", "NAN"]), np.nan).astype(object)
    rows = pd.DataFrame(
        {
            "cik": str(cik),
            "short": short,
            "period": filing.period,
            "filed_at": filing.filed_at,
            "accession": filing.accession,
            # The filing that first disclosed the holding, not when it was bought. A position
            # revealed by an amendment was held all along -- often it was confidential, not new.
            "disclosed_by_amendment": filing.is_amendment,
            "cusip": df["Cusip"].astype(str).str.strip(),
            "name": df["Issuer"],
            "cls": df["Class"],
            "value": df["Value"].astype(int),
            "shares": df["SharesPrnAmount"].astype(int),
            "put_call": put_call,
        }
    )
    return collapse(rows[rows["cusip"] != ""])


def edgar_ticker_hints(df: pd.DataFrame) -> dict[str, str]:
    """CUSIP -> ticker for rows where edgartools already resolved one on the raw holdings df.

    edgartools' own ticker resolution covers names OpenFIGI's free CUSIP mapping misses
    (foreign-domiciled, US-listed issuers like Chubb or ASML), so enrich.py prefers this
    hint and only falls back to OpenFIGI when a CUSIP has none.

    A missing ticker survives `astype(str)` as the literal "NAN" or "NONE", and a hint is
    believed absolutely: it suppresses the OpenFIGI lookup, and `enrich.attach` makes the
    ticker the symbol. So one sentinel leaking through merges every CUSIP carrying it into
    a single fake stock -- which is exactly what "NONE" did.
    """
    cusip = df["Cusip"].astype(str).str.strip()
    ticker = df["Ticker"].astype(str).str.strip().str.upper()
    return {c: t for c, t in zip(cusip, ticker) if c and t not in _NOT_A_TICKER}
