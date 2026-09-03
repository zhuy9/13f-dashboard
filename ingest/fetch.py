"""EDGAR 13F-HR fetch and normalize into base-table rows (minus symbol/ticker/sector)."""

from typing import Optional

import numpy as np
import pandas as pd
from edgar import Company

BASE_COLUMNS = ["cik", "short", "period", "filed_at", "cusip", "name", "cls", "value", "shares", "put_call"]

_printed_columns = False


def fetch_filings(cik: str, quarters: int) -> list:
    """Last `quarters` 13F-HR filings for `cik`, newest first. Ignores 13F-HR/A."""
    company = Company(cik)
    filings = company.get_filings(form="13F-HR", amendments=False)
    ordered = sorted(filings, key=lambda f: f.report_date, reverse=True)
    return ordered[:quarters]


def filing_rows(filing) -> tuple[str, str, Optional[bytes], pd.DataFrame]:
    """(period, filed_at, raw_xml, holdings DataFrame) for one filing."""
    global _printed_columns
    obj = filing.obj()
    df = obj.holdings
    if not _printed_columns:
        print("13F holdings columns:", df.columns.tolist())
        _printed_columns = True
    period = str(obj.report_period)
    filed_at = str(filing.filing_date)
    raw_xml = obj.infotable_xml.encode("utf-8") if obj.has_infotable() else None
    return period, filed_at, raw_xml, df


def normalize(df: pd.DataFrame, cik: str, short: str, period: str, filed_at: str) -> pd.DataFrame:
    """Raw holdings DataFrame -> base-table rows for one (cik, period)."""
    raw_put_call = df["PutCall"].astype(str).str.strip().str.upper()
    put_call = raw_put_call.mask(raw_put_call.isin(["", "NAN"]), np.nan).astype(object)
    rows = pd.DataFrame(
        {
            "cik": str(cik),
            "short": short,
            "period": period,
            "filed_at": filed_at,
            "cusip": df["Cusip"].astype(str).str.strip(),
            "name": df["Issuer"],
            "cls": df["Class"],
            "value": df["Value"].astype(int),
            "shares": df["SharesPrnAmount"].astype(int),
            "put_call": put_call,
        }
    )
    rows = rows[rows["cusip"] != ""]
    if rows.empty:
        return rows[BASE_COLUMNS]

    grouped = rows.groupby(["cik", "period", "cusip", "put_call"], dropna=False, as_index=False).agg(
        short=("short", "first"),
        filed_at=("filed_at", "first"),
        name=("name", "first"),
        cls=("cls", "first"),
        value=("value", "sum"),
        shares=("shares", "sum"),
    )
    return grouped[BASE_COLUMNS].reset_index(drop=True)


def edgar_ticker_hints(df: pd.DataFrame) -> dict[str, str]:
    """CUSIP -> ticker for rows where edgartools already resolved one on the raw holdings df.

    edgartools' own ticker resolution covers names OpenFIGI's free CUSIP mapping misses
    (foreign-domiciled, US-listed issuers like Chubb or ASML), so enrich.py prefers this
    hint and only falls back to OpenFIGI when a CUSIP has none.
    """
    cusip = df["Cusip"].astype(str).str.strip()
    ticker = df["Ticker"].astype(str).str.strip().str.upper()
    return {c: t for c, t in zip(cusip, ticker) if c and t and t != "NAN"}
