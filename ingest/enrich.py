"""CUSIP -> composite FIGI (OpenFIGI) -> ticker, CIK, SIC and sector (security-master). Cached in
Firestore `securities/`.

CUSIPs are licensed, so security-master (https://github.com/zhuy9/security-master) cannot hold
them; OpenFIGI is the private bridge from a CUSIP to the FIGI it is keyed by. security-master
only knows securities listed since it started (2026-10-19), so a cached entry is overwritten only
when it knows that exact security: a holding acquired or delisted before then keeps the entry it
was cached with.
"""

import re
from typing import Optional

import pandas as pd
import requests
import security_master as sm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from store import commit_in_batches

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
FUND_TYPES = ("ETP", "Closed-End Fund")
# OpenFIGI names a note "TSLA 2 05/15/24" and a warrant "NPWR/WS": the issuer's ticker, then a
# slash or a number. Muni-fund preferreds read "DE MIQGEN 07/02/2026", where "DE" is a state, not
# Deere, so a word after the space does not count.
INSTRUMENT_OF = re.compile(r"(\S+?)(?:/|\s\d)")

# OpenFIGI throws the odd 429/5xx; retry after 0, 4, 8 and 16 s (or the server's Retry-After)
# instead of failing the run. POST included: an OpenFIGI mapping is a pure lookup.
_HTTP = requests.Session()
_HTTP.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(total=4, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET", "POST"))
    ),
)


def openfigi_map(cusips: list[str], api_key: Optional[str] = None) -> dict[str, dict]:
    """CUSIP -> its best OpenFIGI match ({} when unmapped). The whole match, not just `ticker`:
    `compositeFIGI` is the security-master key and `securityType` says "ETP". Batches per
    OpenFIGI's key/no-key limits."""
    batch_size = 100 if api_key else 10
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    result: dict[str, dict] = {}
    for i in range(0, len(cusips), batch_size):
        batch = cusips[i : i + batch_size]
        body = [{"idType": "ID_CUSIP", "idValue": c} for c in batch]
        resp = _HTTP.post(OPENFIGI_URL, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        for cusip, item in zip(batch, resp.json()):
            data = item.get("data") or []
            result[cusip] = next((d for d in data if d.get("exchCode") == "US"), data[0]) if data else {}
    return result


def lookup(hint: Optional[str], match: dict) -> tuple[Optional[dict], bool]:
    """The security-master row for a holding, and whether it is that same security.

    By composite FIGI first. By ticker only when OpenFIGI has no FIGI -- its gap for
    foreign-domiciled issuers (CINS CUSIPs: Chubb, ASML) -- because a dead security's ticker may
    belong to another company by now. A note ("TSLA 2 05/15/24") or warrant ("NPWR/WS") is not
    in security-master; the issuer's stock is (INSTRUMENT_OF), and lends the note its CIK and
    sector but not its symbol."""
    figi = match.get("compositeFIGI")
    tickers = [t for t in (hint, match.get("ticker")) if t]
    row = sm.security(figi) if figi else next((r for t in tickers if (r := sm.security(t))), None)
    if row:
        return row, True
    issuer = next((r for t in tickers if (m := INSTRUMENT_OF.match(t)) and (r := sm.security(m[1]))), None)
    return issuer, False


def entry(cusip: str, hint: Optional[str], match: dict) -> tuple[dict, bool]:
    """The cache entry for one CUSIP, and whether security-master knew this exact security."""
    if INSTRUMENT_OF.match(match.get("ticker") or ""):
        # OpenFIGI says this is a note, preferred or warrant. A hint may be the issuer's own ticker
        # (ownership's hint is per issuer, not per CUSIP), which would relabel it as the stock.
        hint = None
    row, same = lookup(hint, match)
    issuer = sm.issuer(row["cik"]) if row and row["cik"] else None
    if (row and row["security_type"] in FUND_TYPES) or (not row and match.get("securityType") in FUND_TYPES):
        sector = "ETF / Fund"  # a fund's own SIC (investment offices) says nothing about what it holds
    else:
        sector = (row or {}).get("sector") or "Unknown"
    return {
        "cusip": cusip,
        "ticker": row["ticker"] if same else hint or match.get("ticker"),
        "cik": row["cik"] if row and row["cik"] else None,
        "sic": int(issuer["sic"]) if issuer and issuer["sic"] else None,
        "sicDescription": issuer["sic_description"] if issuer and issuer["sic_description"] else None,
        "sector": sector,
    }, same


def ensure_securities(
    db,
    cusips: list[str],
    api_key: Optional[str] = None,
    refresh: str = "none",
    ticker_hints: Optional[dict[str, str]] = None,
    persist: bool = True,
) -> dict[str, dict]:
    """Read the `securities/` cache, enrich whatever `refresh` asks for, write back, return the full map.

    `persist=False` keeps the enriched entries in memory and writes nothing -- what a dry run
    needs, since the cache is remote state a dry run must not advance.

    `refresh`: "none" fills gaps only, "unknown" also redoes entries that came back Unknown,
    "all" re-resolves every entry -- the one to reach for after security-master's rules change.
    A cached entry is replaced only when security-master knows that exact security, so a refresh
    never erases what was cached for a holding that left the market before security-master began.

    `ticker_hints` (CUSIP -> ticker, from edgartools' own resolution) is used only where OpenFIGI
    has no FIGI for the CUSIP.
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
        matches = openfigi_map(to_enrich, api_key)
        written: dict[str, dict] = {}
        for cusip in to_enrich:
            new, same = entry(cusip, ticker_hints.get(cusip), matches.get(cusip, {}))
            if cusip in cached and not same:
                continue  # left the market before security-master began: keep what was cached
            cached[cusip] = written[cusip] = new
        if persist and written:
            commit_in_batches(db, [(f"securities/{cusip}", doc) for cusip, doc in written.items()])

    return {c: cached[c] for c in cusips}


def ticker_to_cik() -> dict[str, str]:
    """SEC-form ticker -> 10-digit CIK, for every active security security-master lists."""
    return {r["ticker"]: r["cik"] for r in sm.securities() if r["cik"]}


def cik_to_ticker() -> dict[str, str]:
    """10-digit CIK -> one ticker per issuer: a common share first, then the shortest ticker, then
    alphabetical (GOOG before GOOGL, BRK-A before BRK-B)."""
    rows = sorted(
        (r for r in sm.securities() if r["cik"]),
        key=lambda r: (r["security_type"] != "Common Stock", len(r["ticker"]), r["ticker"]),
    )
    out: dict[str, str] = {}
    for r in rows:
        out.setdefault(r["cik"], r["ticker"])
    return out


def attach(df: pd.DataFrame, securities: dict[str, dict]) -> pd.DataFrame:
    """Add ticker, sector, symbol columns from the securities cache."""
    out = df.copy()
    out["ticker"] = out["cusip"].map(lambda c: securities.get(c, {}).get("ticker"))
    out["sector"] = out["cusip"].map(lambda c: securities.get(c, {}).get("sector", "Unknown"))
    out["symbol"] = out["ticker"].where(out["ticker"].notna(), "_" + out["cusip"])
    return out
