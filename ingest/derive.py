"""All derived signal tables, computed once per ingest run. Pure functions: DataFrame in, DataFrame/dict out."""

import numpy as np
import pandas as pd


def totals(h: pd.DataFrame) -> pd.DataFrame:
    """(cik, period) -> total_value (equity + options) and filed_at."""
    return h.groupby(["cik", "period"], as_index=False).agg(total_value=("value", "sum"), filed_at=("filed_at", "first"))


def _filed_ciks(h: pd.DataFrame) -> dict:
    return h.groupby("period")["cik"].apply(set).to_dict()


def _period_pairs(cur: pd.DataFrame, periods: list[str], filed: dict, key_col: str):
    """Yield (period, cik, key, cur_row, prev_row, manager_filed_prev) for every (cik, key) in
    `cur`'s current period, plus (when the manager also filed the prior period) the prior one.
    `cur_row`/`prev_row` are None when that side of the pair has no row for `key`.
    """
    by_period = {p: cur[cur["period"] == p] for p in periods}
    for i, period in enumerate(periods):
        prev_period = periods[i - 1] if i > 0 else None
        cur_p = by_period[period]
        prev_p = by_period.get(prev_period) if prev_period else None

        for cik in filed.get(period, set()):
            manager_filed_prev = prev_period is not None and cik in filed.get(prev_period, set())
            cur_pos = cur_p[cur_p["cik"] == cik].set_index(key_col)
            prev_pos = prev_p[prev_p["cik"] == cik].set_index(key_col) if manager_filed_prev else None

            keys = set(cur_pos.index) | (set(prev_pos.index) if manager_filed_prev else set())
            for key in keys:
                cur_row = cur_pos.loc[key] if key in cur_pos.index else None
                prev_row = prev_pos.loc[key] if manager_filed_prev and key in prev_pos.index else None
                yield period, cik, key, cur_row, prev_row, manager_filed_prev


def manager_quarter_summary(h: pd.DataFrame, periods: list[str]) -> pd.DataFrame:
    """Table A: per (cik, period, symbol), equity only."""
    equity = h[h["put_call"].isna()]
    tot = totals(h).set_index(["cik", "period"])["total_value"]
    filed = _filed_ciks(h)

    cur = equity.groupby(["cik", "period", "symbol"], as_index=False).agg(
        short=("short", "first"), name=("name", "first"), value=("value", "sum"), shares=("shares", "sum")
    )
    cur["total_value"] = cur.apply(lambda r: tot[(r["cik"], r["period"])], axis=1)
    cur["weight"] = cur["value"] / cur["total_value"]

    rows = []
    for period, cik, symbol, cur_row, prev_row, manager_filed_prev in _period_pairs(cur, periods, filed, "symbol"):
        if cur_row is not None:
            short, name = cur_row["short"], cur_row["name"]
            value, shares, weight = cur_row["value"], cur_row["shares"], cur_row["weight"]
        else:
            short, name = prev_row["short"], prev_row["name"]
            value, shares, weight = 0, 0, 0.0

        if not manager_filed_prev:
            prev_value = prev_shares = prev_weight = None
            status = None
        elif prev_row is None:
            prev_value = prev_shares = prev_weight = None
            status = "NEW"
        else:
            prev_value, prev_shares, prev_weight = prev_row["value"], prev_row["shares"], prev_row["weight"]
            if cur_row is None:
                status = "SOLD_OUT"
            elif shares > prev_shares:
                status = "ADDED"
            elif shares < prev_shares:
                status = "TRIMMED"
            else:
                status = "UNCHANGED"

        change = (weight - prev_weight) if prev_weight is not None else None
        rows.append(
            {
                "cik": cik,
                "period": period,
                "symbol": symbol,
                "short": short,
                "name": name,
                "value": value,
                "shares": shares,
                "weight": weight,
                "prev_value": prev_value,
                "prev_shares": prev_shares,
                "prev_weight": prev_weight,
                "change": change,
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def manager_sector_exposure(h: pd.DataFrame, periods: list[str]) -> pd.DataFrame:
    """Table B: per (cik, period, sector), equity value over total_value (equity + options)."""
    equity = h[h["put_call"].isna()]
    tot = totals(h).set_index(["cik", "period"])["total_value"]
    filed = _filed_ciks(h)

    cur = equity.groupby(["cik", "period", "sector"], as_index=False).agg(value=("value", "sum"))
    cur["total_value"] = cur.apply(lambda r: tot[(r["cik"], r["period"])], axis=1)
    cur["weight"] = cur["value"] / cur["total_value"]

    rows = []
    for period, cik, sector, cur_row, prev_row, manager_filed_prev in _period_pairs(cur, periods, filed, "sector"):
        weight = float(cur_row["weight"]) if cur_row is not None else 0.0
        if manager_filed_prev:
            prev_weight = float(prev_row["weight"]) if prev_row is not None else 0.0
            change = weight - prev_weight
        else:
            prev_weight = None
            change = None
        rows.append(
            {"cik": cik, "period": period, "sector": sector, "weight": weight, "prev_weight": prev_weight, "change": change}
        )
    return pd.DataFrame(rows)


def stock_quarter_summary(mqs: pd.DataFrame, managers_per_period: dict) -> pd.DataFrame:
    """Table C: per (period, symbol), equity only."""
    rows = []
    for (period, symbol), grp in mqs.groupby(["period", "symbol"]):
        name = grp["name"].iloc[0]
        holders_df = grp[grp["value"] > 0]
        sold_out_df = grp[grp["status"] == "SOLD_OUT"]
        status_counts = grp["status"].value_counts()
        managers_total = managers_per_period[period]

        holders = holders_df.sort_values("weight", ascending=False)[
            ["cik", "short", "value", "shares", "weight", "prev_weight", "change", "status"]
        ].to_dict("records")
        sold_out = sold_out_df[["cik", "short", "prev_weight"]].to_dict("records")

        rows.append(
            {
                "period": period,
                "symbol": symbol,
                "name": name,
                "manager_count": len(holders_df),
                "managers_total": managers_total,
                "pct_holding": len(holders_df) / managers_total if managers_total else 0.0,
                "avg_weight": float(holders_df["weight"].mean()) if len(holders_df) else 0.0,
                "median_weight": float(holders_df["weight"].median()) if len(holders_df) else 0.0,
                "max_weight": float(holders_df["weight"].max()) if len(holders_df) else 0.0,
                "total_value": int(holders_df["value"].sum()),
                "new_count": int(status_counts.get("NEW", 0)),
                "added_count": int(status_counts.get("ADDED", 0)),
                "trimmed_count": int(status_counts.get("TRIMMED", 0)),
                "unchanged_count": int(status_counts.get("UNCHANGED", 0)),
                "sold_out_count": int(status_counts.get("SOLD_OUT", 0)),
                "holders": holders,
                "sold_out": sold_out,
            }
        )
    return pd.DataFrame(rows)


def stock_trend(sqs: pd.DataFrame) -> pd.DataFrame:
    """Table D: per symbol, one row per period sqs covers."""
    rows = []
    for symbol, grp in sqs.groupby("symbol"):
        prev_holder_ciks = None
        for _, r in grp.sort_values("period").iterrows():
            holder_ciks = {holder["cik"] for holder in r["holders"]}
            if prev_holder_ciks is None:
                new_managers = exited_managers = 0
            else:
                new_managers = len(holder_ciks - prev_holder_ciks)
                exited_managers = len(prev_holder_ciks - holder_ciks)
            rows.append(
                {
                    "symbol": symbol,
                    "period": r["period"],
                    "manager_count": r["manager_count"],
                    "avg_weight": r["avg_weight"],
                    "median_weight": r["median_weight"],
                    "max_weight": r["max_weight"],
                    "new_managers": new_managers,
                    "exited_managers": exited_managers,
                    "net_change": new_managers - exited_managers,
                }
            )
            prev_holder_ciks = holder_ciks
    return pd.DataFrame(rows)


def conviction_score(sqs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Adds avg_change, raw, and score (0-100, relative within each period) to sqs."""
    score_cfg = cfg["score"]
    out = sqs.copy()

    def avg_change(holders: list[dict]) -> float:
        vals = [
            h["weight"] if h["status"] == "NEW" else h["change"] for h in holders if h["status"] == "NEW" or pd.notna(h["change"])
        ]
        return sum(vals) / len(vals) if vals else 0.0

    out["avg_change"] = out["holders"].apply(avg_change)
    accumulation = (out["avg_change"].clip(lower=0) / score_cfg["accumulation_scale"] + 1).clip(
        upper=score_cfg["accumulation_cap"]
    )
    out["raw"] = (
        out["manager_count"]
        * (1 + out["avg_weight"] / score_cfg["weight_scale"])
        * (1 + out["new_count"] * score_cfg["new_bonus"])
        * (1 + out["added_count"] * score_cfg["added_bonus"])
        * accumulation
    )

    def score_within_period(raw: pd.Series) -> pd.Series:
        peak = raw.max()
        if not peak:
            return pd.Series([0] * len(raw), index=raw.index)
        return (100 * raw / peak).round().astype(int)

    out["score"] = out.groupby("period")["raw"].transform(score_within_period)
    return out.drop(columns=["raw"])


def _status_change(holders: list[dict], statuses: set[str]) -> float:
    vals = []
    for h in holders:
        if h["status"] not in statuses:
            continue
        vals.append(h["weight"] if h["status"] == "NEW" else h["change"])
    return sum(vals) / len(vals) if vals else 0.0


def _top_per_period(df: pd.DataFrame, sort_col: str, ascending: bool, top_n: int | None) -> pd.DataFrame:
    ordered = df.sort_values(["period", sort_col], ascending=[True, ascending])
    if top_n is None:
        return ordered
    return ordered.groupby("period", group_keys=False).head(top_n)


def consensus_tables(sqs: pd.DataFrame, mqs: pd.DataFrame, trend: pd.DataFrame, cfg: dict) -> dict:
    """Table E: the 8 consensus/leaderboard tables."""
    top_n = cfg["top_n"]
    symbol_names = mqs.drop_duplicates("symbol").set_index("symbol")["name"]
    tables = {}

    buys = sqs[(sqs["new_count"] + sqs["added_count"]) >= cfg["consensus_min_managers"]].copy()
    buys["new_buyers"] = buys["new_count"]
    buys["added"] = buys["added_count"]
    buys["avg_weight_increase"] = buys["holders"].apply(lambda hs: _status_change(hs, {"NEW", "ADDED"}))
    tables["consensus_buys"] = _top_per_period(
        buys[["period", "symbol", "name", "new_buyers", "added", "avg_weight", "avg_weight_increase", "score"]],
        "score",
        False,
        None,
    )

    exits = sqs[(sqs["sold_out_count"] + sqs["trimmed_count"]) >= cfg["consensus_min_managers"]].copy()
    exits["sold_out"] = exits["sold_out_count"]
    exits["trimmed"] = exits["trimmed_count"]
    exits["avg_reduction"] = (
        mqs[mqs["status"].isin(["SOLD_OUT", "TRIMMED"])]
        .groupby(["period", "symbol"])["change"]
        .mean()
        .reindex(list(zip(exits["period"], exits["symbol"])))
        .values
    )
    exits = exits.sort_values(["period", "sold_out", "trimmed"], ascending=[True, False, False])
    tables["consensus_exits"] = exits[["period", "symbol", "name", "sold_out", "trimmed", "avg_reduction"]]

    min_w = cfg["high_conviction_min_weight"]
    hc = sqs.copy()
    hc["qualifying"] = hc["holders"].apply(lambda hs: [h for h in hs if h["weight"] >= min_w])
    hc["managers"] = hc["qualifying"].apply(len)
    hc = hc[hc["managers"] >= cfg["high_conviction_min_managers"]]
    hc["avg_weight"] = hc["qualifying"].apply(lambda qs: sum(q["weight"] for q in qs) / len(qs))
    hc["max_weight"] = hc["qualifying"].apply(lambda qs: max(q["weight"] for q in qs))
    hc = hc.rename(columns={"new_count": "new", "added_count": "added"})
    hc = hc.sort_values(["period", "managers", "avg_weight"], ascending=[True, False, False])
    tables["high_conviction"] = hc[["period", "symbol", "name", "managers", "avg_weight", "max_weight", "new", "added"]]

    tables["biggest_new"] = _top_per_period(
        mqs[mqs["status"] == "NEW"][["period", "cik", "short", "symbol", "name", "weight", "value"]], "weight", False, top_n
    )
    tables["biggest_adds"] = _top_per_period(
        mqs[mqs["status"] == "ADDED"][["period", "cik", "short", "symbol", "name", "weight", "change", "value"]],
        "change",
        False,
        top_n,
    )
    tables["biggest_trims"] = _top_per_period(
        mqs[mqs["status"].isin(["TRIMMED", "SOLD_OUT"])][
            ["period", "cik", "short", "symbol", "name", "weight", "change", "value"]
        ],
        "change",
        True,
        top_n,
    )

    trend_sorted = trend.sort_values(["symbol", "period"])
    trend_sorted["prev_count"] = trend_sorted.groupby("symbol")["manager_count"].shift(1).fillna(0).astype(int)
    latest = trend["period"].max()
    fg = trend_sorted[(trend_sorted["period"] == latest) & (trend_sorted["net_change"] > 0)].copy()
    fg["name"] = fg["symbol"].map(symbol_names)
    fg = fg.rename(columns={"manager_count": "count"}).sort_values("net_change", ascending=False).head(top_n)
    tables["fastest_growing"] = fg[["symbol", "name", "prev_count", "count", "new_managers", "exited_managers", "net_change"]]

    tables["top_signals"] = _top_per_period(
        sqs[sqs["manager_count"] >= cfg["consensus_min_managers"]][
            ["period", "symbol", "name", "score", "manager_count", "avg_weight", "new_count", "added_count"]
        ],
        "score",
        False,
        top_n,
    )
    return tables


def sector_rotation(mse: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Table F: per (period, sector), over managers with a defined QoQ change."""
    valid = mse.dropna(subset=["change"])
    threshold = cfg["sector_move_threshold"]
    grouped = (
        valid.groupby(["period", "sector"])
        .agg(
            avg_weight=("weight", "mean"),
            avg_prev_weight=("prev_weight", "mean"),
            avg_change=("change", "mean"),
            increasing=("change", lambda s: int((s > threshold).sum())),
            decreasing=("change", lambda s: int((s < -threshold).sum())),
        )
        .reset_index()
    )
    return grouped.sort_values(["period", "avg_change"], ascending=[True, False])


def manager_similarity(mqs: pd.DataFrame) -> dict:
    """Table G: cosine similarity over equity weight vectors, per period."""
    result = {}
    for period, grp in mqs.groupby("period"):
        pivot = grp.pivot_table(index="cik", columns="symbol", values="weight", fill_value=0.0, aggfunc="sum")
        ciks = pivot.index.tolist()
        vectors = pivot.to_numpy()
        norms = np.linalg.norm(vectors, axis=1)
        outer_norms = np.outer(norms, norms)
        with np.errstate(divide="ignore", invalid="ignore"):
            sim = np.where(outer_norms > 0, (vectors @ vectors.T) / outer_norms, 0.0)

        most_similar = {}
        for i, cik in enumerate(ciks):
            others = sorted(((ciks[j], float(sim[i, j])) for j in range(len(ciks)) if j != i), key=lambda t: -t[1])
            most_similar[cik] = [{"cik": c, "score": s} for c, s in others[:5]]

        result[period] = {"ciks": ciks, "matrix": sim.tolist(), "most_similar": most_similar}
    return result


def options_exposure(h: pd.DataFrame) -> pd.DataFrame:
    """Table H: per (period, symbol) with any option row."""
    options = h[h["put_call"].notna()]
    rows = []
    for (period, symbol), _ in options.groupby(["period", "symbol"]):
        at_symbol = h[(h["period"] == period) & (h["symbol"] == symbol)]
        rows.append(
            {
                "period": period,
                "symbol": symbol,
                "equity_holders": sorted(at_symbol[at_symbol["put_call"].isna()]["cik"].unique().tolist()),
                "call_holders": sorted(at_symbol[at_symbol["put_call"] == "CALL"]["cik"].unique().tolist()),
                "put_holders": sorted(at_symbol[at_symbol["put_call"] == "PUT"]["cik"].unique().tolist()),
            }
        )
    return pd.DataFrame(rows)


def clusters(mqs: pd.DataFrame, mse: pd.DataFrame, funds: list[dict]) -> dict:
    """Table I: per period, per cluster label from funds.json."""
    cik_to_cluster = {f["cik"]: f["cluster"] for f in funds}
    labels = sorted(set(cik_to_cluster.values()))

    result = {}
    for period in sorted(mqs["period"].unique()):
        period_mqs = mqs[(mqs["period"] == period) & (mqs["value"] > 0)]
        period_mse = mse[mse["period"] == period]
        result[period] = {}

        for label in labels:
            members = sorted(cik for cik, cluster in cik_to_cluster.items() if cluster == label)
            cluster_rows = period_mqs[period_mqs["cik"].isin(members)]

            if cluster_rows.empty:
                common_holdings, top_sector = [], None
            else:
                by_symbol = cluster_rows.groupby("symbol").agg(holder_count=("cik", "nunique"), avg_weight=("weight", "mean"))
                common = by_symbol[by_symbol["holder_count"] >= len(members) / 2].sort_values("avg_weight", ascending=False)
                common_holdings = common.head(10).index.tolist()

                cluster_sectors = period_mse[period_mse["cik"].isin(members)]
                top_sector = (
                    (cluster_sectors.groupby("sector")["weight"].sum() / len(members)).idxmax() if len(cluster_sectors) else None
                )

            result[period][label] = {
                "label": label,
                "members": members,
                "common_holdings": common_holdings,
                "top_sector": top_sector,
            }
    return result


def derive_all(h: pd.DataFrame, funds: list[dict], cfg: dict) -> dict:
    periods = sorted(h["period"].unique())
    managers_per_period = {p: len(ciks) for p, ciks in _filed_ciks(h).items()}

    mqs = manager_quarter_summary(h, periods)
    mse = manager_sector_exposure(h, periods)
    sqs = conviction_score(stock_quarter_summary(mqs, managers_per_period), cfg)
    trend = stock_trend(sqs)

    return {
        "periods": periods,
        "holdings": h,
        "totals": totals(h),
        "symbols": h[["symbol", "name", "sector"]].drop_duplicates("symbol").reset_index(drop=True),
        "manager_quarter_summary": mqs,
        "manager_sector_exposure": mse,
        "stock_quarter_summary": sqs,
        "stock_trend": trend,
        **consensus_tables(sqs, mqs, trend, cfg),
        "sector_rotation": sector_rotation(mse, cfg),
        "manager_similarity": manager_similarity(mqs),
        "options_exposure": options_exposure(h),
        "clusters": clusters(mqs, mse, funds),
    }
