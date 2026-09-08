"""CUSIP -> ticker (OpenFIGI) -> CIK + SIC (SEC) -> sector. Cached in Firestore `securities/`."""

import time
from typing import Optional

import pandas as pd
import requests

from api_constants import OPENFIGI_URL, SEC_SUBMISSIONS_URL, SEC_TICKERS_URL
from sectors import sic_to_sector


def openfigi_map(cusips: list[str], api_key: Optional[str] = None) -> dict[str, dict]:
    """CUSIP -> its best OpenFIGI match ({} when unmapped). The whole match, not just `ticker`:
    `securityType2` is how an ETF is recognised, and no SIC code can say that. Batches per
    OpenFIGI's key/no-key limits."""
    batch_size = 100 if api_key else 10
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    result: dict[str, dict] = {}
    for i in range(0, len(cusips), batch_size):
        batch = cusips[i : i + batch_size]
        body = [{"idType": "ID_CUSIP", "idValue": c} for c in batch]
        resp = requests.post(OPENFIGI_URL, json=body, headers=headers, timeout=30)
        if resp.status_code == 429:
            time.sleep(6)
            resp = requests.post(OPENFIGI_URL, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        for cusip, item in zip(batch, resp.json()):
            data = item.get("data") or []
            result[cusip] = next((d for d in data if d.get("exchCode") == "US"), data[0]) if data else {}
    return result


def sec_ticker_to_cik(identity: str) -> dict[str, str]:
    """TICKER -> 10-digit zero-padded CIK, from SEC's company_tickers.json."""
    headers = {"User-Agent": identity}
    resp = requests.get(SEC_TICKERS_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    return {row["ticker"]: str(row["cik_str"]).zfill(10) for row in resp.json().values()}


def sec_sic(cik10: str, identity: str) -> tuple[Optional[int], Optional[str]]:
    """(sic, sicDescription) for a 10-digit CIK, from SEC's submissions API."""
    headers = {"User-Agent": identity}
    url = SEC_SUBMISSIONS_URL.format(cik10=cik10)
    resp = requests.get(url, headers=headers, timeout=30)
    time.sleep(0.11)
    if resp.status_code == 404:
        return None, None
    resp.raise_for_status()
    data = resp.json()
    sic = data.get("sic")
    return (int(sic) if sic else None), data.get("sicDescription")


def ensure_securities(
    db,
    cusips: list[str],
    identity: str,
    api_key: Optional[str] = None,
    refresh: str = "none",
    ticker_hints: Optional[dict[str, str]] = None,
) -> dict[str, dict]:
    """Read the `securities/` cache, enrich whatever `refresh` asks for, write back, return the full map.

    `refresh`: "none" fills gaps only, "unknown" also redoes entries that came back Unknown,
    "all" rebuilds every entry -- the one to reach for after a rule changes, since a cached
    sector is never revisited otherwise.

    `ticker_hints` (CUSIP -> ticker, from edgartools' own resolution) is preferred over
    OpenFIGI, which has coverage gaps for foreign-domiciled US-listed issuers.
    """
    cusips = sorted(set(cusips))
    ticker_hints = ticker_hints or {}
    collection = db.collection("securities")

    cached: dict[str, dict] = {}
    refs = [collection.document(cusip) for cusip in cusips]
    for snap in db.get_all(refs):
        if snap.exists:
            cached[snap.id] = snap.to_dict()

    def stale(cusip: str) -> bool:
        return refresh == "all" or (refresh == "unknown" and cached[cusip].get("sector") == "Unknown")

    to_enrich = [c for c in cusips if c not in cached or stale(c)]

    if to_enrich:
        need_openfigi = [c for c in to_enrich if not ticker_hints.get(c)]
        matches = openfigi_map(need_openfigi, api_key) if need_openfigi else {}
        ticker_to_cik = sec_ticker_to_cik(identity)
        for cusip in to_enrich:
            match = matches.get(cusip, {})
            ticker = ticker_hints.get(cusip) or match.get("ticker")
            security_type = match.get("securityType2")
            sic, sic_description = (None, None)
            issuer_cik = ticker_to_cik.get(ticker) if ticker else None
            if issuer_cik:
                sic, sic_description = sec_sic(issuer_cik, identity)
            cached[cusip] = {
                "cusip": cusip,
                "ticker": ticker,
                "cik": issuer_cik,
                "sic": sic,
                "sicDescription": sic_description,
                "sector": sic_to_sector(sic, security_type),
            }

        for i in range(0, len(to_enrich), 400):
            batch = db.batch()
            for cusip in to_enrich[i : i + 400]:
                batch.set(collection.document(cusip), cached[cusip])
            batch.commit()

    return {c: cached[c] for c in cusips}


def attach(df: pd.DataFrame, securities: dict[str, dict]) -> pd.DataFrame:
    """Add ticker, sector, symbol columns from the securities cache."""
    out = df.copy()
    out["ticker"] = out["cusip"].map(lambda c: securities.get(c, {}).get("ticker"))
    out["sector"] = out["cusip"].map(lambda c: securities.get(c, {}).get("sector", "Unknown"))
    out["symbol"] = out["ticker"].where(out["ticker"].notna(), "_" + out["cusip"])
    return out
