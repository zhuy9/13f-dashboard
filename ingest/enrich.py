"""CUSIP -> ticker (OpenFIGI) -> CIK + SIC (SEC) -> sector. Cached in Firestore `securities/`."""

import time
from typing import Optional

import pandas as pd
import requests

from api_constants import OPENFIGI_URL, SEC_SUBMISSIONS_URL, SEC_TICKER_TXT_URL, SEC_TICKERS_URL
from sectors import sic_to_sector


def openfigi_map(cusips: list[str], api_key: Optional[str] = None) -> dict[str, dict]:
    """CUSIP -> its best OpenFIGI match ({} when unmapped). The whole match, not just `ticker`:
    `securityType` is how an ETF is recognised ("ETP"), and no SIC code can say that. Batches
    per OpenFIGI's key/no-key limits."""
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
    """TICKER -> 10-digit zero-padded CIK, from both of SEC's ticker lists.

    `company_tickers.json` lists current registrants only. A company that deregisters -- taken
    private, or acquired -- is dropped from it, and because sector comes from the issuer's SIC
    code, which needs the CIK, the holding then has no sector at all. That is not a small edge
    case: a 13F window is 3 years long and an event-driven manager holds acquisition targets on
    purpose, so the names most likely to vanish are the ones it holds most.

    `ticker.txt` is the older list and keeps them, so it fills the gaps. company_tickers.json
    still wins where both have a ticker: it is the maintained one, and a recycled ticker should
    resolve to whoever holds it now, not to the company that used to.
    """
    headers = {"User-Agent": identity}

    txt = requests.get(SEC_TICKER_TXT_URL, headers=headers, timeout=30)
    txt.raise_for_status()
    mapping = {}
    for line in txt.text.splitlines():
        ticker, _, cik = line.partition("\t")
        if ticker and cik.strip().isdigit():
            mapping[ticker.strip().upper()] = cik.strip().zfill(10)

    resp = requests.get(SEC_TICKERS_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    mapping.update({row["ticker"]: str(row["cik_str"]).zfill(10) for row in resp.json().values()})
    return mapping


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
    persist: bool = True,
) -> dict[str, dict]:
    """Read the `securities/` cache, enrich whatever `refresh` asks for, write back, return the full map.

    `persist=False` keeps the enriched entries in memory and writes nothing -- what a dry run
    needs, since the cache is remote state a dry run must not advance.

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
        # Every CUSIP, not just the unhinted ones: a hint carries a ticker but no security type,
        # and edgartools hints ETFs too (SPY, IWM), so filtering here hid every fund from the
        # ETP rule. The hint still wins for the ticker itself, where its coverage is better.
        matches = openfigi_map(to_enrich, api_key) if to_enrich else {}
        ticker_to_cik = sec_ticker_to_cik(identity)
        for cusip in to_enrich:
            match = matches.get(cusip, {})
            ticker = ticker_hints.get(cusip) or match.get("ticker")
            security_type = match.get("securityType")  # "ETP"; securityType2 says "Mutual Fund"
            sic, sic_description = (None, None)
            # OpenFIGI names a bond "TSLA 2 05/15/24", so the first token is the issuer's
            # own ticker. No real US ticker contains a space, so this is a no-op for equities.
            issuer_cik = ticker_to_cik.get(ticker.split(" ")[0]) if ticker else None
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

        if persist:
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
