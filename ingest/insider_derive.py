"""Pure Form 4 derive functions: DataFrame in, DataFrame/dict out. No network, no Firestore."""

from datetime import timedelta
from typing import Optional

import pandas as pd

# Section K transaction-code -> kind table. Exhaustive: `kind()` falls back to OTHER for any
# code not listed here (J K L U V W Z I E H O).
CODE_KINDS: dict[str, str] = {
    "P": "BUY",
    "S": "SELL",
    "A": "AWARD",
    "M": "EXERCISE",
    "X": "EXERCISE",
    "F": "TAX",
    "G": "GIFT",
    "C": "CONVERSION",
    "D": "DISPOSITION_TO_ISSUER",
}


def kind(code: str) -> str:
    return CODE_KINDS.get(code, "OTHER")


def _role(row: pd.Series) -> str:
    parts = []
    if row["is_officer"]:
        title = row.get("officer_title")
        parts.append(f"Officer ({title})" if isinstance(title, str) and title else "Officer")
    if row["is_director"]:
        parts.append("Director")
    if row["is_ten_pct_owner"]:
        parts.append("10% Owner")
    return ", ".join(parts) if parts else "Other"


def _first_buy_in_window(trades: pd.DataFrame, cfg: dict) -> pd.Series:
    """True when this BUY is the owner's first on this (owner_cik, issuer_cik) timeline within
    `first_buy_lookback_days`; null when the log does not reach back that far from `start_date`
    -- absence of evidence is not evidence, same rule as `status = null` in the 13F table."""
    lookback = timedelta(days=cfg["first_buy_lookback_days"])
    start_date = pd.Timestamp(cfg["start_date"])
    out = pd.Series([None] * len(trades), index=trades.index, dtype="object")

    buys = trades[trades["kind"] == "BUY"]
    for (owner_cik, issuer_cik), group in buys.groupby(["owner_cik", "issuer_cik"]):
        dates = group["transaction_date"]
        for idx, date in dates.items():
            window_start = date - lookback
            earlier = dates[(dates < date) & (dates >= window_start)]
            if len(earlier):
                out[idx] = False
            elif window_start >= start_date:
                out[idx] = True
            # else: coverage doesn't reach back far enough -- stays None
    return out


def trades(transactions: pd.DataFrame, cfg: dict, holder_counts: Optional[dict[str, int]]) -> pd.DataFrame:
    out = transactions.copy()
    # A few real filers' transactionDate values carry a trailing UTC offset (e.g. "-05:00") on
    # what is otherwise always a bare calendar date -- keep only the YYYY-MM-DD prefix.
    out["transaction_date"] = pd.to_datetime(out["transaction_date"].astype(str).str[:10], format="%Y-%m-%d")

    out["kind"] = out["code"].map(kind)
    out["role"] = out.apply(_role, axis=1)
    out["is_open_market"] = out["code"].isin(["P", "S"])
    out["is_planned"] = out["aff10b5_one"] == True  # noqa: E712 -- must not conflate with NaN
    out["is_discretionary_sale"] = (out["code"] == "S") & (out["aff10b5_one"] == False)  # noqa: E712
    out["first_buy_in_window"] = _first_buy_in_window(out, cfg)
    out["holders13f"] = out["symbol"].map(holder_counts).fillna(0).astype(int) if holder_counts is not None else None

    threshold = cfg["min_open_market_value"]
    meets_value = out["value"].fillna(0) >= threshold
    high = out["kind"].eq("BUY") & out["is_open_market"] & (meets_value | out["first_buy_in_window"].eq(True))
    medium = out["kind"].eq("BUY") | (out["is_discretionary_sale"] & meets_value)
    out["priority"] = "LOW"
    out.loc[medium, "priority"] = "MEDIUM"
    out.loc[high, "priority"] = "HIGH"

    out["transaction_date"] = out["transaction_date"].dt.strftime("%Y-%m-%d")
    return out


CLUSTER_COLS = ["symbol", "issuer_cik", "issuer_name", "buyer_count", "buyers", "window_days"]


def _window(trades: pd.DataFrame, days: int) -> tuple[pd.Series, pd.Timestamp, pd.Timestamp]:
    """Dates parsed, plus `[as_of - days, as_of]` anchored to the newest date on file."""
    dates = pd.to_datetime(trades["transaction_date"])
    as_of = dates.max() if len(dates) else pd.Timestamp("1970-01-01")
    return dates, as_of - timedelta(days=days), as_of


def clusters(trades: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per symbol, distinct buyers in the last `cluster_window_days`; kept when the count is
    >= `cluster_min_insiders`."""
    dates, window_start, as_of = _window(trades, cfg["cluster_window_days"])
    buys = trades[(trades["kind"] == "BUY") & dates.between(window_start, as_of)]

    rows = []
    for symbol, group in buys.groupby("symbol"):
        buyers = sorted(group["owner_cik"].unique())
        if len(buyers) < cfg["cluster_min_insiders"]:
            continue
        meta = group.iloc[0]
        rows.append(
            {
                "symbol": symbol,
                "issuer_cik": meta["issuer_cik"],
                "issuer_name": meta["issuer_name"],
                "buyer_count": len(buyers),
                "buyers": buyers,
                "window_days": cfg["cluster_window_days"],
            }
        )
    return pd.DataFrame(rows, columns=CLUSTER_COLS)


def issuer_summary(trades: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per symbol, over open-market rows only. Planned and discretionary sales are counted
    separately and never summed into one "insider selling" number."""
    market = trades[trades["is_open_market"]]
    rows = []
    for symbol, group in market.groupby("symbol"):
        buys = group[group["code"] == "P"]
        sells = group[group["code"] == "S"]
        meta = group.iloc[0]
        rows.append(
            {
                "symbol": symbol,
                "issuer_cik": meta["issuer_cik"],
                "issuer_name": meta["issuer_name"],
                "buyers": buys["owner_cik"].nunique(),
                "sellers": sells["owner_cik"].nunique(),
                "boughtShares": buys["shares"].sum(),
                "soldShares": sells["shares"].sum(),
                "boughtValue": buys["value"].sum(),
                "soldValue": sells["value"].sum(),
                "discretionarySellers": sells[sells["is_discretionary_sale"]]["owner_cik"].nunique(),
                "plannedSellers": sells[sells["is_planned"]]["owner_cik"].nunique(),
                "lastTradeAt": group["transaction_date"].max(),
            }
        )
    return pd.DataFrame(rows)


def vs_13f(trades: pd.DataFrame, clusters: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Symbols with >= 1 open-market BUY in `cluster_window_days` and `holders13f >= 1` --
    "insiders are buying something the tracked managers already own", the cross-pipeline table."""
    dates, window_start, as_of = _window(trades, cfg["cluster_window_days"])
    buys = trades[(trades["code"] == "P") & dates.between(window_start, as_of) & (trades["holders13f"] >= 1)]

    clustered_symbols = set(clusters["symbol"]) if len(clusters) else set()
    rows = []
    for symbol, group in buys.groupby("symbol"):
        meta = group.iloc[0]
        rows.append(
            {
                "symbol": symbol,
                "issuer_cik": meta["issuer_cik"],
                "issuer_name": meta["issuer_name"],
                "buyers": group["owner_cik"].nunique(),
                "boughtValue": group["value"].sum(),
                "holders13f": int(meta["holders13f"]),
                "hasCluster": symbol in clustered_symbols,
            }
        )
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values(["holders13f", "buyers", "boughtValue"], ascending=False).reset_index(drop=True)
    return out


def people(trades: pd.DataFrame) -> pd.DataFrame:
    """One row per (owner, issuer): role, buy/sell counts and net shares -- projected/grouped
    into `insider_issuers`/`insider_people` docs at the store layer."""
    rows = []
    for (owner_cik, issuer_cik), group in trades.groupby(["owner_cik", "issuer_cik"]):
        meta = group.iloc[-1]
        market = group[group["is_open_market"]]
        buys = market[market["code"] == "P"]
        sells = market[market["code"] == "S"]
        rows.append(
            {
                "owner_cik": owner_cik,
                "owner_name": meta["owner_name"],
                "issuer_cik": issuer_cik,
                "issuer_name": meta["issuer_name"],
                "symbol": meta["symbol"],
                "role": meta["role"],
                "buys": len(buys),
                "sells": len(sells),
                "net_shares": buys["shares"].sum() - sells["shares"].sum(),
                "last_trade_at": group["transaction_date"].max(),
            }
        )
    return pd.DataFrame(rows)


def recent(trades: pd.DataFrame, n: int) -> pd.DataFrame:
    return trades.sort_values(["filed_at", "accession"], ascending=[False, False]).head(n)


def derive_all(transactions: pd.DataFrame, cfg: dict, holder_counts: Optional[dict[str, int]]) -> dict:
    t = trades(transactions, cfg, holder_counts)
    c = clusters(t, cfg)
    return {
        "transactions": transactions,
        "trades": t,
        "clusters": c,
        "issuer_summary": issuer_summary(t, cfg),
        "vs_13f": vs_13f(t, c, cfg),
        "people": people(t),
        "recent": recent(t, cfg["recent_trades"]),
    }
