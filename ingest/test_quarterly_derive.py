import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from quarterly_derive import facts, issue_period, label, stale_tables, windows

P, PREV, TODAY = "2026-09-30", "2026-06-30", "2026-11-17"
CFG = {
    "consensus_min_managers": 3,
    "ownership": {"start_date": "2024-12-18"},
    "insider": {"start_date": "2025-09-01", "cluster_min_insiders": 3},
    "quarterly": {"rows_per_section": 10, "cross_min_insider_buyers": 2},
}


def _c(symbol: str, new=0, added=0, trimmed=0, sold_out=0, unchanged=0) -> dict:
    """One stock_quarter_summary row; holder `i` is manager `M<i>` with a shrinking weight."""
    statuses = ["NEW"] * new + ["ADDED"] * added + ["TRIMMED"] * trimmed + ["UNCHANGED"] * unchanged
    holders = [{"cik": str(i), "short": f"M{i}", "weight": 0.1 - i / 100, "status": s} for i, s in enumerate(statuses)]
    sold = [{"cik": str(90 + i), "short": f"X{i}", "prev_weight": 0.01 * (i + 1)} for i in range(sold_out)]
    return {
        "symbol": symbol, "name": f"{symbol} Inc", "manager_count": len(holders), "avg_weight": 0.02,
        "new_count": new, "added_count": added, "trimmed_count": trimmed, "unchanged_count": unchanged,
        "sold_out_count": sold_out, "holders": holders, "sold_out": sold,
    }  # fmt: skip


def _event(symbol: str, filed_at: str, event, priority="HIGH", roster=True, holders13f=1, form="13D") -> dict:
    return {
        "filed_at": filed_at, "form": form, "event": event, "priority": priority, "investor_cik": "7",
        "investor_name": "Some Filer LP", "short": "M7" if roster else None, "is_roster": roster,
        "is_activist": False, "symbol": symbol, "issuer_name": f"{symbol} Corp", "pct": 6.0, "change_pp": None,
        "holders13f": holders13f, "accession": f"{symbol}-{filed_at}", "url": "https://example.test/f",
        "purpose": "free text from the filer",
    }  # fmt: skip


def _trade(symbol: str, owner: str, code="P", filed_at="2026-10-05", value=1000.0, planned=False, disc=None, primary=True):
    return {
        "filed_at": filed_at, "code": code, "kind": "BUY" if code == "P" else "SELL", "owner_cik": owner,
        "filer_group": owner.rstrip("b"), "is_primary": primary, "symbol": symbol, "issuer_name": f"{symbol} Corp",
        "value": value, "is_planned": planned, "is_discretionary_sale": code == "S" and disc is True,
        "holders13f": 1,
    }  # fmt: skip


def _inputs(cfg=CFG, summary=None) -> dict:
    summary = summary or [
        _c("B51", new=3, added=2, trimmed=1),  # buyers 5, sellers 1: bought, not contested
        _c("B73", new=4, added=3, trimmed=2, sold_out=1),  # 7 / 3, net 4: bought, contested
        _c("S55", added=5, trimmed=5),  # a tie: split only
        _c("S53", added=5, trimmed=3),  # net 2 < 3: split
        _c("N20", new=2),  # too few buyers: in no list
        _c("L15", added=1, trimmed=3, sold_out=2),  # sold
        _c("_X", new=5),  # no ticker: dropped
    ]
    events = [
        _event("B51", "2026-07-01", "UPDATED", priority="MEDIUM"),  # roster UPDATED: dropped
        _event("OUT0", "2026-08-01", "NEW", roster=False, holders13f=0),  # nobody holds it: dropped
        _event("B51", "2026-07-01", "NEW", roster=False, holders13f=2),  # first day of the quarter: kept
        _event("NUL", "2026-08-01", None),  # unknown event: dropped
        _event("G13", "2026-11-17", "NEW", priority="MEDIUM", form="13G"),  # last day of since: kept
        _event("_E", "2026-08-01", "NEW"),  # no ticker: dropped
        _event("OLD", "2026-06-30", "NEW"),  # before both windows
    ]
    trades = [
        _trade("B51", "1", filed_at="2026-08-01"),
        _trade("B51", "2", filed_at="2026-10-02"),
        _trade("INS", "1"),
        _trade("INS", "1"),  # the same buyer twice counts once
        _trade("INS", "1b", primary=False),  # a joint filer's copy: neither a buyer nor value
        _trade("INS", "2"),
        _trade("INS", "3"),
        _trade("SAL", "5", code="S", value=100.0, planned=True),
        _trade("SAL", "6", code="S", value=200.0, disc=True),
        _trade("SAL", "7", code="S", value=400.0),  # 10b5-1 not stated: neither planned nor discretionary
        _trade("PLN", "8", code="S", planned=True),  # planned only: dropped
        _trade("_ISSUER9", "9"),
    ]
    tables = {
        "stock_quarter_summary": pd.DataFrame(summary),
        "biggest_new": pd.DataFrame(
            [
                {"cik": "1", "short": "M1", "symbol": "B51", "name": "B51 Inc", "weight": 0.05, "value": 1e6},
                {"cik": "2", "short": "M2", "symbol": "_Y", "name": "Y", "weight": 0.09, "value": 2e6},
            ]
        ),
        "high_conviction": pd.DataFrame(
            [
                {"symbol": "AAA", "name": "A", "managers": 4, "avg_weight": 0.05, "max_weight": 0.08},
                {"symbol": "BBB", "name": "B", "managers": 3, "avg_weight": 0.04, "max_weight": 0.06},
            ]
        ),
        "high_conviction_prev": pd.DataFrame(
            [
                {"symbol": "BBB", "name": "B", "managers": 5, "avg_weight": 0.06, "max_weight": 0.07},
                {"symbol": "CCC", "name": "C", "managers": 3, "avg_weight": 0.03, "max_weight": 0.04},
            ]
        ),
        "sector_rotation": pd.DataFrame(
            [
                {"sector": s, "avg_weight": w, "avg_prev_weight": w - ch, "avg_change": ch, "increasing": 1, "decreasing": 1}
                for s, w, ch in (("Energy", 0.1, -0.01), ("Tech", 0.3, 0.02))
            ]
        ),
    }  # fmt: skip
    meta = {
        "managers": [{"short": "M1"}, {"short": "M2"}, {"short": "M3"}],
        "coverage": [{"period": P, "filed": ["M1", "M2"], "missing": ["M3"]}],
        "datasetId": "ds1",
    }
    return facts(tables, pd.DataFrame(events), pd.DataFrame(trades), meta, P, PREV, TODAY, cfg)


def _section(issue: dict, id_: str) -> dict:
    return next(s for s in issue["sections"] if s["id"] == id_)


def _symbols(issue: dict, id_: str) -> list[str]:
    return [r["symbol"] for r in _section(issue, id_)["rows"]]


def test_windows_cover_the_quarter_and_what_was_filed_after_it():
    assert windows(P, PREV, TODAY) == {
        "quarter": {"start": "2026-07-01", "end": "2026-09-30"},
        "since": {"start": "2026-10-01", "end": "2026-11-17"},
    }
    assert windows(P, PREV, "2027-02-16")["since"]["end"] == "2026-12-31"


def test_issue_period_skips_a_thinly_filed_quarter_and_never_picks_the_oldest():
    periods = ["2026-03-31", "2026-06-30", "2026-09-30"]
    coverage = [{"period": p, "filed": ["x"] * n} for p, n in zip(periods, [40, 40, 30])]
    assert issue_period(periods, coverage, 40, 0.8) == ("2026-06-30", "2026-03-31")
    assert issue_period(periods[:1], coverage, 40, 0.8) is None
    assert issue_period(periods, [{"period": p, "filed": []} for p in periods], 40, 0.8) is None


def test_stale_tables_names_missing_and_old_tables():
    published = datetime(2026, 11, 17, 3, 14, tzinfo=timezone.utc)
    updated = {"fresh": published - timedelta(minutes=5), "old": published - timedelta(hours=7), "gone": None}
    assert stale_tables(updated, published) == ["gone", "old"]


def test_label_matches_the_web_quarter_label():
    assert (label("2026-09-30"), label("2026-12-31")) == ("2026 Q3", "2026 Q4")


def test_net_lists_are_disjoint_and_ordered():
    issue = _inputs()
    assert _symbols(issue, "bought") == ["B73", "B51"]  # same net 4: more buyers first
    assert _symbols(issue, "sold") == ["L15"]
    assert _symbols(issue, "split") == ["S55", "S53"]
    contested = {r["symbol"]: r["contested"] for r in _section(issue, "bought")["rows"]}
    assert contested == {"B73": True, "B51": False}


def test_net_rows_name_the_managers_on_each_side():
    issue = _inputs()
    b51 = _section(issue, "bought")["rows"][1]
    assert [m["short"] for m in b51["buyerManagers"]] == ["M0", "M1", "M2", "M3", "M4"]
    assert b51["newCount"] == 3 and b51["managerCount"] == 6
    l15 = _section(issue, "sold")["rows"][0]
    assert [m["short"] for m in l15["sellerManagers"]] == ["M1", "M2", "M3", "X1", "X0"]


def test_rows_are_capped_but_total_counts_every_row():
    issue = _inputs({**CFG, "quarterly": {**CFG["quarterly"], "rows_per_section": 1}})
    bought = _section(issue, "bought")
    assert (bought["total"], len(bought["rows"])) == (2, 1)


def test_symbols_without_a_ticker_appear_nowhere():
    text = json.dumps(_inputs())
    assert '"_X"' not in text and '"_Y"' not in text and '"_E"' not in text and "_ISSUER9" not in text


def test_conviction_entered_stayed_left():
    rows = _section(_inputs(), "conviction")["rows"]
    assert [(r["symbol"], r["change"]) for r in rows] == [("AAA", "ENTERED"), ("BBB", "STAYED"), ("CCC", "LEFT")]
    assert rows[2]["managers"] == 3  # LEFT carries prev's values


def test_stakes_keep_roster_moves_and_held_high_events_inside_the_windows():
    stakes = _section(_inputs(), "stakes")
    assert [(r["symbol"], r["window"]) for r in stakes["rows"]] == [("B51", "quarter"), ("G13", "since")]
    assert all("purpose" not in r for r in stakes["rows"])
    assert (stakes["total"], stakes["windowTotals"]) == (2, {"quarter": 1, "since": 1})


def test_a_window_before_the_log_starts_is_no_data():
    issue = _inputs({**CFG, "insider": {**CFG["insider"], "start_date": "2026-08-01"}})
    for id_ in ("insider_buys", "insider_sales"):
        section = _section(issue, id_)
        assert section["noData"] == ["quarter"]
        assert {r["window"] for r in section["rows"]} == {"since"}
        assert list(section["windowTotals"]) == ["since"]
    assert _section(issue, "stakes")["noData"] == []


def test_insider_sales_keep_planned_and_discretionary_apart():
    rows = _section(_inputs(), "insider_sales")["rows"]
    assert [r["symbol"] for r in rows] == ["SAL"]
    sal = rows[0]
    assert (sal["discretionarySellers"], sal["discretionaryValue"]) == (1, 200.0)
    assert (sal["plannedSellers"], sal["plannedValue"]) == (1, 100.0)


def test_insider_buys_count_each_buyer_once_and_flag_clusters():
    rows = {(r["symbol"], r["window"]): r for r in _section(_inputs(), "insider_buys")["rows"]}
    ins = rows[("INS", "since")]
    assert (ins["buyers"], ins["value"], ins["isCluster"]) == (3, 4000.0, True)
    assert rows[("B51", "quarter")]["isCluster"] is False


def test_cross_needs_two_of_three_filing_kinds():
    rows = _section(_inputs(), "cross")["rows"]
    assert [(r["symbol"], r["signals"]) for r in rows] == [("B51", ["13F", "13D", "INSIDER"])]
    assert (rows[0]["investor"], rows[0]["isRoster"], rows[0]["insiderBuyers"]) == ("Some Filer LP", False, 2)


def test_cross_counts_bought_rows_past_the_cap():
    issue = _inputs({**CFG, "quarterly": {**CFG["quarterly"], "rows_per_section": 1}})
    assert _symbols(issue, "bought") == ["B73"]
    assert _symbols(issue, "cross") == ["B51"]


def test_totals_coverage_and_json_safety():
    issue = _inputs()
    assert issue["totals"] == {"opened": 14, "closed": 3, "added": 16, "trimmed": 14, "unchanged": 0}
    assert issue["coverage"] == {"filed": 2, "total": 3, "missing": ["M3"]}
    assert [s["id"] for s in issue["sections"]] == [
        "bought", "sold", "split", "new_positions", "conviction", "sectors", "stakes", "insider_buys",
        "insider_sales", "cross",
    ]  # fmt: skip
    json.dumps(issue, allow_nan=False)
