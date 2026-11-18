"""Pure facts for the quarterly issue (docs/PLAN.md section M): frames and dicts in, a dict out.
No network, no Firestore, no files. quarterly_text.py adds the sentences."""

from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pandas as pd

from store import records

STALE_HOURS = 6
EVENT_WINDOWS = ("quarter", "since")
_QUARTERS = {"03": "Q1", "06": "Q2", "09": "Q3", "12": "Q4"}
_STAKE_EVENTS = {"NEW", "INCREASED", "SWITCHED_TO_13D"}
NET_COLS = [
    "symbol", "name", "buyers", "sellers", "net", "new_count", "added_count", "trimmed_count",
    "sold_out_count", "manager_count", "avg_weight",
]  # fmt: skip
STAKE_COLS = [
    "filed_at", "form", "event", "priority", "investor_cik", "investor_name", "short", "is_roster",
    "is_activist", "symbol", "issuer_name", "pct", "change_pp", "holders13f", "url",
]  # fmt: skip


def label(period: str) -> str:
    """Same text as web/src/format.ts quarterLabel: "2026-09-30" -> "2026 Q3"."""
    year, month, _ = period.split("-")
    return f"{year} {_QUARTERS.get(month, month)}"


def issue_period(periods: list[str], coverage: list[dict], total: int, min_coverage: float) -> Optional[tuple[str, str]]:
    """(P, prev): the newest period, other than the oldest, that enough managers have filed."""
    filed = {c["period"]: len(c["filed"]) for c in coverage}
    ordered = sorted(periods)
    for i in range(len(ordered) - 1, 0, -1):
        if total and filed.get(ordered[i], 0) / total >= min_coverage:
            return ordered[i], ordered[i - 1]
    return None


def windows(period: str, prev_period: str, today: str) -> dict:
    day = timedelta(days=1)
    next_end = (pd.Timestamp(period) + pd.offsets.QuarterEnd(1)).date().isoformat()
    return {
        "quarter": {"start": (date.fromisoformat(prev_period) + day).isoformat(), "end": period},
        "since": {"start": (date.fromisoformat(period) + day).isoformat(), "end": min(today, next_end)},
    }


def stale_tables(updated: dict[str, Optional[datetime]], published_at: datetime) -> list[str]:
    """Tables missing from GCS (None) or written well before the snapshot they should match."""
    oldest = published_at - timedelta(hours=STALE_HOURS)
    return sorted(name for name, at in updated.items() if at is None or at < oldest)


def _ticked(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows without a ticker (`_ISSUER...`, `_` placeholders): there is no page to link."""
    return df[~df["symbol"].astype(str).str.startswith("_")]


def _section(id_: str, df: pd.DataFrame, cap: Optional[int]) -> dict:
    return {"id": id_, "total": int(len(df)), "noData": [], "rows": records(df if cap is None else df.head(cap))}


def _managers(row, side: str) -> list[dict]:
    """The managers behind one side of a net row, biggest weight first."""
    statuses = {"NEW", "ADDED"} if side == "buy" else {"TRIMMED"}
    held = sorted((h for h in row.holders if h["status"] in statuses), key=lambda h: -(h.get("weight") or 0))
    gone = sorted(row.sold_out, key=lambda h: -(h.get("prev_weight") or 0)) if side == "sell" else []
    return [{"cik": h["cik"], "short": h["short"]} for h in [*held, *gone]]


def _net_lists(c: pd.DataFrame, min_managers: int, cap: int) -> tuple[list[dict], pd.DataFrame]:
    c = c.assign(buyers=c["new_count"] + c["added_count"], sellers=c["trimmed_count"] + c["sold_out_count"])
    c = c.assign(net=c["buyers"] - c["sellers"])
    split = (c["buyers"] >= min_managers) & (c["sellers"] >= min_managers) & (c["net"].abs() < min_managers)
    bought = c[(c["buyers"] >= min_managers) & (c["net"] > 0) & ~split]
    bought = bought.sort_values(["net", "buyers", "symbol"], ascending=[False, False, True])
    sold = c[(c["sellers"] >= min_managers) & (c["net"] < 0) & ~split]
    sold = sold.sort_values(["net", "sellers", "symbol"], ascending=[True, False, True])
    both = c[split].assign(_n=c["buyers"] + c["sellers"]).sort_values(["_n", "symbol"], ascending=[False, True])

    def side(df: pd.DataFrame, which: str) -> pd.DataFrame:
        managers = [_managers(r, which) for r in df.itertuples()]
        other = df["sellers"] if which == "buy" else df["buyers"]
        return df[NET_COLS].assign(**{f"{which}er_managers": managers, "contested": other >= min_managers})

    split_rows = both[["symbol", "name", "buyers", "sellers", "net"]].assign(
        buyer_managers=[_managers(r, "buy") for r in both.itertuples()],
        seller_managers=[_managers(r, "sell") for r in both.itertuples()],
    )
    sections = [
        _section("bought", side(bought, "buy"), cap),
        _section("sold", side(sold, "sell"), cap),
        _section("split", split_rows, cap),
    ]
    return sections, bought


def _conviction(now: pd.DataFrame, before: pd.DataFrame) -> dict:
    cols = ["symbol", "name", "managers", "avg_weight", "max_weight"]
    parts = [
        now[~now["symbol"].isin(before["symbol"])].assign(change="ENTERED"),
        now[now["symbol"].isin(before["symbol"])].assign(change="STAYED"),
        before[~before["symbol"].isin(now["symbol"])].assign(change="LEFT"),
    ]
    ordered = [p.sort_values(["managers", "avg_weight"], ascending=False)[[*cols, "change"]] for p in parts]
    return _section("conviction", pd.concat(ordered), None)


def _in(df: pd.DataFrame, window: dict) -> pd.Series:
    """Filed inside the window, both ends included. filed_at is ISO text, so text order is date order."""
    return (df["filed_at"] >= window["start"]) & (df["filed_at"] <= window["end"])


def _covered(df: pd.DataFrame, wins: dict, start_date: str) -> pd.Series:
    """Filed in any window the log covers (the windows not in `noData`)."""
    mask = pd.Series(False, index=df.index)
    for name in EVENT_WINDOWS:
        if wins[name]["start"] >= start_date:
            mask |= _in(df, wins[name])
    return mask


def _event_section(
    id_: str, df: pd.DataFrame, wins: dict, start_date: str, cap: int, build: Callable[[pd.DataFrame], pd.DataFrame]
) -> dict:
    """One section over both windows: rows sorted and capped per window, totals before the cap. A
    window the pipeline's log does not cover is listed in `noData` and gets no rows or total."""
    no_data = [name for name in EVENT_WINDOWS if wins[name]["start"] < start_date]
    parts = {name: build(df[_in(df, wins[name])]).assign(window=name) for name in EVENT_WINDOWS if name not in no_data}
    return {
        "id": id_,
        "total": int(sum(len(p) for p in parts.values())),
        "windowTotals": {name: int(len(p)) for name, p in parts.items()},
        "noData": no_data,
        "rows": [row for p in parts.values() for row in records(p.head(cap))],
    }


def _stakes(events: pd.DataFrame) -> pd.DataFrame:
    roster = events["is_roster"].astype(bool) & events["event"].ne("UPDATED")
    held = events["priority"].eq("HIGH") & events["holders13f"].fillna(0).ge(1)
    keep = events[events["event"].notna() & (roster | held)]
    return keep.sort_values(["is_roster", "filed_at", "accession"], ascending=False)[STAKE_COLS]


def _insider_buys(trades: pd.DataFrame, cluster_min: int) -> pd.DataFrame:
    buys = trades[trades["kind"].eq("BUY") & trades["is_primary"]]
    out = buys.groupby("symbol", as_index=False).agg(
        issuer_name=("issuer_name", "first"),
        buyers=("filer_group", "nunique"),
        value=("value", "sum"),
        holders13f=("holders13f", "first"),
    )
    out["is_cluster"] = out["buyers"] >= cluster_min
    return out.sort_values(["buyers", "value", "symbol"], ascending=[False, False, True])


def _insider_sales(trades: pd.DataFrame) -> pd.DataFrame:
    """Section K's definitions exactly: planned and discretionary are counted apart, never summed."""
    sells = trades[trades["code"].eq("S") & trades["is_primary"]]
    disc, planned = sells[sells["is_discretionary_sale"]], sells[sells["is_planned"]]
    out = sells.groupby("symbol").agg(issuer_name=("issuer_name", "first"), holders13f=("holders13f", "first"))
    out["discretionary_sellers"] = disc.groupby("symbol")["filer_group"].nunique()
    out["discretionary_value"] = disc.groupby("symbol")["value"].sum()
    out["planned_sellers"] = planned.groupby("symbol")["filer_group"].nunique()
    out["planned_value"] = planned.groupby("symbol")["value"].sum()
    counts = ["discretionary_sellers", "planned_sellers"]
    out = out.fillna({c: 0 for c in [*counts, "discretionary_value", "planned_value"]}).astype({c: int for c in counts})
    out = out[out["discretionary_sellers"] >= 1].reset_index()
    return out.sort_values(["discretionary_sellers", "discretionary_value", "symbol"], ascending=[False, False, True])


def _cross(bought: pd.DataFrame, events: pd.DataFrame, trades: pd.DataFrame, names: dict, min_insiders: int, cap: int) -> dict:
    """Symbols in at least two of: 13F net buying (every `bought` row), a HIGH 13D-style event,
    and `min_insiders` insider buyers over the covered windows together."""
    b = bought.set_index("symbol")
    high = events[events["priority"].eq("HIGH") & events["event"].isin(_STAKE_EVENTS)]
    d = high.sort_values(["filed_at", "accession"], ascending=False).drop_duplicates("symbol").set_index("symbol")
    buys = trades[trades["kind"].eq("BUY") & trades["is_primary"]]
    insiders = buys.groupby("symbol")["filer_group"].nunique()
    insiders = insiders[insiders >= min_insiders]
    issuer = {**trades.groupby("symbol")["issuer_name"].first(), **d["issuer_name"], **names}

    rows = []
    for symbol in set(b.index) | set(d.index) | set(insiders.index):
        signals = [s for s, has in (("13F", b.index), ("13D", d.index), ("INSIDER", insiders.index)) if symbol in has]
        if len(signals) < 2:
            continue
        event = d.loc[symbol] if symbol in d.index else None
        rows.append(
            {
                "symbol": symbol,
                "name": issuer.get(symbol),
                "signals": signals,
                "buyers": int(b.loc[symbol, "buyers"]) if symbol in b.index else None,
                "net": int(b.loc[symbol, "net"]) if symbol in b.index else None,
                "investor": None if event is None else (event["short"] if event["is_roster"] else event["investor_name"]),
                "investorCik": None if event is None else event["investor_cik"],
                "isRoster": None if event is None else bool(event["is_roster"]),
                "insiderBuyers": int(insiders.get(symbol, 0)),
            }
        )
    rows.sort(key=lambda r: (-len(r["signals"]), r["net"] is None, -(r["net"] or 0), r["symbol"]))
    return {"id": "cross", "total": len(rows), "noData": [], "rows": rows[:cap]}


def facts(
    tables: dict[str, pd.DataFrame],
    events: pd.DataFrame,
    trades: pd.DataFrame,
    meta: dict,
    period: str,
    prev: str,
    today: str,
    cfg: dict,
) -> dict:
    """The issue doc of section M without its text: no headline, lede, titles or summaries."""
    q, cap = cfg["quarterly"], cfg["quarterly"]["rows_per_section"]
    wins = windows(period, prev, today)
    summary = tables["stock_quarter_summary"]
    c = _ticked(summary)
    events, trades = _ticked(events), _ticked(trades)
    ev_start, ins_start = cfg["ownership"]["start_date"], cfg["insider"]["start_date"]

    net_sections, bought = _net_lists(c, cfg["consensus_min_managers"], cap)
    new_positions = _ticked(tables["biggest_new"]).sort_values("weight", ascending=False)
    sectors = tables["sector_rotation"].sort_values("avg_change", ascending=False)
    sector_cols = ["sector", "avg_weight", "avg_prev_weight", "avg_change", "increasing", "decreasing"]
    covered_events = events[_covered(events, wins, ev_start)]
    covered_trades = trades[_covered(trades, wins, ins_start)]

    cov = next((x for x in meta["coverage"] if x["period"] == period), {"filed": [], "missing": []})
    return {
        "period": period,
        "prevPeriod": prev,
        "label": label(period),
        "datasetId": meta.get("datasetId"),
        "windows": wins,
        "coverage": {"filed": len(cov["filed"]), "total": len(meta["managers"]), "missing": list(cov["missing"])},
        "totals": {
            "opened": int(summary["new_count"].sum()),
            "closed": int(summary["sold_out_count"].sum()),
            "added": int(summary["added_count"].sum()),
            "trimmed": int(summary["trimmed_count"].sum()),
            "unchanged": int(summary["unchanged_count"].sum()),
        },
        "sections": [
            *net_sections,
            _section("new_positions", new_positions[["cik", "short", "symbol", "name", "weight", "value"]], cap),
            _conviction(_ticked(tables["high_conviction"]), _ticked(tables["high_conviction_prev"])),
            _section("sectors", sectors[sector_cols], None),
            _event_section("stakes", events, wins, ev_start, cap, _stakes),
            _event_section(
                "insider_buys", trades, wins, ins_start, cap, lambda t: _insider_buys(t, cfg["insider"]["cluster_min_insiders"])
            ),
            _event_section("insider_sales", trades, wins, ins_start, cap, _insider_sales),
            _cross(bought, covered_events, covered_trades, dict(zip(c["symbol"], c["name"])), q["cross_min_insider_buyers"], cap),
        ],
        "ai": None,
    }
