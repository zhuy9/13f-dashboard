"""13D/13G event derivation: filings -> events (per investor x issuer timeline) -> stakes.

Pure functions: DataFrame in, DataFrame/dict out. No I/O.
"""

from typing import Optional

import pandas as pd


def _as_list(value) -> list[str]:
    """`reporting_ciks` arrives as a Python list from a fresh fetch, a numpy array after a
    parquet round-trip, or a `|`-joined string from a CSV fixture -- accept any of them."""
    if isinstance(value, str):
        return value.split("|") if value else []
    if hasattr(value, "__iter__"):
        return list(value)
    return []  # None or a scalar NaN


def _unpad(cik) -> Optional[str]:
    """`funds.json` CIKs/aliases are unpadded ("1791786"); real filer/reporting CIKs are
    zero-padded 10-digit strings ("0001791786"). Normalize before comparing either way."""
    return str(int(cik)) if cik else None


def investor_map(funds: list[dict]) -> dict[str, dict]:
    """Every roster CIK and alias (unpadded) -> {cik, name, short, cluster}."""
    mapping: dict[str, dict] = {}
    for fund in funds:
        info = {"cik": fund["cik"], "name": fund["name"], "short": fund["short"], "cluster": fund["cluster"]}
        mapping[fund["cik"]] = info
        for alias in fund.get("aliases", []):
            mapping[alias] = info
    return mapping


def _canonicalize(row: pd.Series, imap: dict[str, dict]) -> tuple:
    """(investor_cik, is_roster, investor_name, short, cluster) -- header filer CIK checked
    first, then any reporting-person CIK; unmatched filers keep their own (unpadded) CIK."""
    for cik in [row["filer_cik"], *_as_list(row["reporting_ciks"])]:
        info = imap.get(_unpad(cik))
        if info:
            return info["cik"], True, info["name"], info["short"], info["cluster"]
    return _unpad(row["filer_cik"]), False, row["investor_name"], None, None


def _classify(row: pd.Series, cfg: dict) -> Optional[str]:
    """The 8 event rules from docs/PLAN.md section J, first match wins."""
    if not row["has_prev"]:
        return None if row["is_amendment"] else "NEW"
    prev_pct, pct = row["prev_pct"], row["pct"]
    if pd.isna(prev_pct) or pd.isna(pct):
        return None
    if prev_pct < cfg["exit_below_pct"]:
        return "NEW"
    if pct < cfg["exit_below_pct"]:
        return "EXITED"
    if row["prev_form"] != row["form"]:
        return f"SWITCHED_TO_{row['form']}"
    if abs(pct - prev_pct) >= cfg["min_change_pp"]:
        return "INCREASED" if pct > prev_pct else "DECREASED"
    return "UPDATED"


def _priority(row: pd.Series) -> str:
    form, event, activist, roster = row["form"], row["event"], row["is_activist"], row["is_roster"]
    if (form == "13D" and event in {"NEW", "SWITCHED_TO_13D"}) or (activist and event in {"NEW", "INCREASED", "SWITCHED_TO_13D"}):
        return "HIGH"
    if (
        (form == "13D" and event in {"INCREASED", "DECREASED", "EXITED"})
        or (form == "13G" and event == "NEW")
        or (form == "13D" and event == "UPDATED" and roster)
    ):
        return "MEDIUM"
    return "LOW"


def events(filings: pd.DataFrame, funds: list[dict], cfg: dict) -> pd.DataFrame:
    """One row per filing, canonicalized to a roster investor where applicable and
    classified against the previous filing on the same (investor, cusip) timeline."""
    imap = investor_map(funds)
    out = filings.copy()

    canon = out.apply(lambda r: _canonicalize(r, imap), axis=1, result_type="expand")
    out["investor_cik"], out["is_roster"], out["investor_name"], out["short"], out["cluster"] = (
        canon[0],
        canon[1],
        canon[2],
        canon[3],
        canon[4],
    )
    out["is_activist"] = out["is_roster"] & out["cluster"].fillna("").str.contains("Activist")

    sort_amendment = out["amendment_no"].fillna(0)
    out = out.assign(_sort_amendment=sort_amendment)
    out = out.sort_values(["investor_cik", "cusip", "filed_at", "_sort_amendment", "accession"]).drop(columns="_sort_amendment")
    out = out.reset_index(drop=True)

    grouped = out.groupby(["investor_cik", "cusip"], sort=False)
    out["prev_pct"] = grouped["pct"].shift(1)
    out["prev_form"] = grouped["form"].shift(1)
    out["prev_accession_in_log"] = grouped["accession"].shift(1)
    out["has_prev"] = out["prev_accession_in_log"].notna()

    out["event"] = out.apply(lambda r: _classify(r, cfg), axis=1)
    out["change_pp"] = out["pct"] - out["prev_pct"]
    out["priority"] = out.apply(_priority, axis=1)

    return out.drop(columns=["has_prev", "prev_form"])


def stakes(events_df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """The latest event row per (investor_cik, cusip) -- `events_df` must already be in
    timeline order (as returned by `events`)."""
    out = events_df.groupby(["investor_cik", "cusip"], sort=False, as_index=False).tail(1).copy()
    out["is_current"] = out["pct"].notna() & (out["pct"] >= cfg["exit_below_pct"])
    return out.reset_index(drop=True)


def recent(events_df: pd.DataFrame, n: int) -> pd.DataFrame:
    """The newest `n` event rows, newest first."""
    return events_df.sort_values(["filed_at", "accession"], ascending=[False, False]).head(n).reset_index(drop=True)


def derive_all(filings: pd.DataFrame, funds: list[dict], cfg: dict) -> dict:
    ev = events(filings, funds, cfg)
    return {
        "filings": filings,
        "events": ev,
        "stakes": stakes(ev, cfg),
        "recent": recent(ev, cfg["recent_events"]),
    }
