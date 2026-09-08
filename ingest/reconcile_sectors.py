"""Dev tool: score `sectors.py` against GICS, using the S&P 500 as ground truth.

Not part of the pipeline and not imported by it. Run it after editing SIC_RANGES:

    python reconcile_sectors.py            # score, and list what still disagrees
    python reconcile_sectors.py --propose  # suggest carves the evidence supports

SIC is an SEC filing code, GICS is what the finance world means by "sector", and the two do
not line up: one SIC can hold Ametek, Keysight and Danaher. So this reports an agreement rate,
not a pass/fail, and a `--propose` carve is only offered where every S&P member of a code
disagrees with us, or where our answer is right for almost none of them. Codes that are
genuinely mixed are left to their range on purpose.

Reads the live `securities/` cache for the SIC codes we assigned, so it needs no credentials
(the collection is world-readable) but does need the network.
"""

import argparse
import collections
import io
import json
import urllib.parse
import urllib.request

import pandas as pd
import requests

from sectors import sic_to_sector

FIRESTORE = "https://firestore.googleapis.com/v1/projects/form-13f-dashboard/databases/(default)/documents"
SP500_CSV = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"

# GICS sector name -> ours. Identical names are listed anyway, so a rename on either side shows up.
GICS_TO_OURS = {
    "Information Technology": "Technology",
    "Communication Services": "Communication",
    "Energy": "Energy & Mining",
    "Real Estate": "Real Estate",
    "Materials": "Materials",
    "Industrials": "Industrials",
    "Health Care": "Health Care",
    "Financials": "Financials",
    "Consumer Discretionary": "Consumer Discretionary",
    "Consumer Staples": "Consumer Staples",
    "Utilities": "Utilities",
}


def cached_securities() -> pd.DataFrame:
    """Every `securities/` doc, as (sic, ticker, cik, desc). Ids only, so this is cheap."""
    docs, token = [], None
    while True:
        query = [("pageSize", "300")] + [("mask.fieldPaths", f) for f in ("sic", "ticker", "cik", "sicDescription")]
        if token:
            query.append(("pageToken", token))
        page = json.load(urllib.request.urlopen(f"{FIRESTORE}/securities?{urllib.parse.urlencode(query)}"))
        docs += page.get("documents", [])
        token = page.get("nextPageToken")
        if not token:
            return pd.DataFrame(
                [
                    {
                        "sic": _value(d, "sic"),
                        "ticker": _value(d, "ticker"),
                        "cik": _value(d, "cik"),
                        "desc": _value(d, "sicDescription"),
                    }
                    for d in docs
                ]
            )


def _value(doc: dict, key: str):
    field = doc.get("fields", {}).get(key) or {}
    return field.get("stringValue") or field.get("integerValue")


def scored() -> pd.DataFrame:
    """One row per S&P 500 name we have a SIC for, with our sector and the GICS one."""
    sp500 = pd.read_csv(io.StringIO(requests.get(SP500_CSV, timeout=30).text))
    sp500["cik10"] = sp500["CIK"].astype(int).astype(str).str.zfill(10)
    truth_by_cik = dict(zip(sp500["cik10"], sp500["GICS Sector"]))

    out = cached_securities()
    out = out[out["sic"].notna() & out["cik"].notna()].drop_duplicates("cik")
    out["truth"] = out["cik"].map(truth_by_cik).map(GICS_TO_OURS)
    out = out[out["truth"].notna()].copy()
    out["ours"] = out["sic"].map(lambda s: sic_to_sector(int(s)))
    out["ok"] = out["ours"] == out["truth"]
    return out


def report(df: pd.DataFrame) -> None:
    print(f"scored {len(df)} S&P 500 names: {df['ok'].sum()} agree = {df['ok'].mean():.1%}\n")
    print("per-sector recall (of the GICS truth, how many we get right):")
    for truth, grp in sorted(df.groupby("truth"), key=lambda kv: -len(kv[1])):
        print(f"  {truth:<24} {grp['ok'].sum():>3}/{len(grp):<4} {grp['ok'].mean():5.0%}")
    print("\nremaining disagreements, worst SIC first:")
    bad = df[~df["ok"]]
    for (sic, ours, truth), grp in sorted(bad.groupby(["sic", "ours", "truth"]), key=lambda kv: -len(kv[1]))[:20]:
        tickers = ", ".join(str(t) for t in grp["ticker"].head(4))
        print(f"  SIC {sic}  ours={ours:<22} GICS={truth:<22} n={len(grp):<3} {str(grp['desc'].iloc[0])[:32]:<33} {tickers}")


def propose(df: pd.DataFrame) -> None:
    print("carves the evidence supports (paste above the broad ranges in sectors.py):")
    for sic, grp in sorted(df.groupby("sic"), key=lambda kv: int(kv[0])):
        truths, ours = collections.Counter(grp["truth"]), grp["ours"].iloc[0]
        unanimous = len(truths) == 1 and len(grp) >= 2 and list(truths)[0] != ours
        hopeless = len(grp) >= 3 and grp["ok"].mean() < 0.25
        if not (unanimous or hopeless):
            continue
        best = truths.most_common(1)[0][0]
        if best == ours:
            continue
        why = "unanimous" if unanimous else f"we are right for {grp['ok'].sum()}/{len(grp)}"
        print(f'    ({sic}, {sic}, "{best}"),  # {why}: {", ".join(str(t) for t in grp["ticker"].head(4))}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--propose", action="store_true", help="suggest SIC carves instead of scoring")
    args = parser.parse_args()
    df = scored()
    propose(df) if args.propose else report(df)
