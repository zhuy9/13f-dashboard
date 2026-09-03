from pathlib import Path

import pandas as pd
import pytest

from derive import conviction_score, derive_all, options_exposure

FIXTURE = Path(__file__).parent / "fixtures" / "holdings_small.csv"

FUNDS = [
    {"cik": "1111111111", "short": "M1", "cluster": "Beta"},
    {"cik": "2222222222", "short": "M2", "cluster": "Beta"},
    {"cik": "3333333333", "short": "M3", "cluster": "Beta"},
]

# Small, fixture-scaled thresholds -- not the production signals_config.json values.
CFG = {
    "consensus_min_managers": 1,
    "high_conviction_min_weight": 0.2,
    "high_conviction_min_managers": 2,
    "sector_move_threshold": 0.005,
    "top_n": 25,
    "score": {"weight_scale": 0.05, "new_bonus": 0.5, "added_bonus": 0.25, "accumulation_scale": 0.02, "accumulation_cap": 3},
}

P1, P2 = "2026-03-31", "2026-06-30"


@pytest.fixture
def h() -> pd.DataFrame:
    df = pd.read_csv(FIXTURE, dtype={"cik": str})
    df["put_call"] = df["put_call"].where(df["put_call"].notna(), None)
    df.loc[df["put_call"] == "", "put_call"] = None
    return df


@pytest.fixture
def out(h) -> dict:
    return derive_all(h, FUNDS, CFG)


def _mqs_row(mqs: pd.DataFrame, cik: str, period: str, symbol: str) -> pd.Series:
    match = mqs[(mqs["cik"] == cik) & (mqs["period"] == period) & (mqs["symbol"] == symbol)]
    assert len(match) == 1
    return match.iloc[0]


def test_weights_and_totals(out):
    totals = out["totals"].set_index(["cik", "period"])["total_value"]
    assert totals[("1111111111", P1)] == 44000
    assert totals[("1111111111", P2)] == 35000
    aaa_p1 = _mqs_row(out["manager_quarter_summary"], "1111111111", P1, "AAA")
    assert aaa_p1["weight"] == pytest.approx(10000 / 44000)


def test_every_status_occurs(out):
    mqs = out["manager_quarter_summary"]
    statuses = set(mqs["status"].dropna())
    assert statuses == {"NEW", "ADDED", "TRIMMED", "UNCHANGED", "SOLD_OUT"}
    assert mqs["status"].isna().any()  # M3, missing P1 entirely

    assert _mqs_row(mqs, "2222222222", P2, "FFF")["status"] == "NEW"
    assert _mqs_row(mqs, "1111111111", P2, "AAA")["status"] == "ADDED"
    assert _mqs_row(mqs, "1111111111", P2, "DDD")["status"] == "TRIMMED"
    assert _mqs_row(mqs, "1111111111", P2, "CCC")["status"] == "UNCHANGED"
    assert _mqs_row(mqs, "1111111111", P2, "FFF")["status"] == "SOLD_OUT"
    m3_rows = mqs[(mqs["cik"] == "3333333333") & (mqs["period"] == P2)]
    assert m3_rows["status"].isna().all()
    assert m3_rows["prev_weight"].isna().all()


def test_change_sign_and_null_rules(out):
    mqs = out["manager_quarter_summary"]
    # DDD: shares fell (TRIMMED) but weight rose slightly -- status is share-based, change is weight-based.
    ddd = _mqs_row(mqs, "1111111111", P2, "DDD")
    assert ddd["status"] == "TRIMMED"
    assert ddd["change"] > 0
    # BBB: shares rose (ADDED) but weight fell -- same principle, opposite direction.
    bbb = _mqs_row(mqs, "2222222222", P2, "BBB")
    assert bbb["status"] == "ADDED"
    assert bbb["change"] < 0
    # Period[0] rows and a manager with no prior filing both get null change.
    p1_rows = mqs[mqs["period"] == P1]
    assert p1_rows["change"].isna().all()
    m3_rows = mqs[(mqs["cik"] == "3333333333") & (mqs["period"] == P2)]
    assert m3_rows["change"].isna().all()


def test_sold_out_row_emitted_with_change_negative_prev_weight(out):
    fff = _mqs_row(out["manager_quarter_summary"], "1111111111", P2, "FFF")
    assert fff["value"] == 0
    assert fff["weight"] == 0
    assert fff["prev_weight"] == pytest.approx(4000 / 44000)
    assert fff["change"] == pytest.approx(-fff["prev_weight"])


def test_stock_quarter_summary_counts_and_pct_holding(out):
    sqs = out["stock_quarter_summary"]
    fff_p2 = sqs[(sqs["period"] == P2) & (sqs["symbol"] == "FFF")].iloc[0]
    assert fff_p2["manager_count"] == 2  # M2, M3 hold it; M1's SOLD_OUT row doesn't count
    assert fff_p2["managers_total"] == 3
    assert fff_p2["pct_holding"] == pytest.approx(2 / 3)
    assert fff_p2["new_count"] == 1
    assert fff_p2["sold_out_count"] == 1


def test_stock_trend_net_change(out):
    trend = out["stock_trend"]
    fff = trend[trend["symbol"] == "FFF"].set_index("period")
    assert fff.loc[P1, "manager_count"] == 1
    assert fff.loc[P2, "manager_count"] == 2
    assert fff.loc[P2, "new_managers"] == 2  # M2, M3
    assert fff.loc[P2, "exited_managers"] == 1  # M1
    assert fff.loc[P2, "net_change"] == 1


def test_consensus_buys_membership_and_order(out):
    buys = out["consensus_buys"]
    buys_p2 = buys[buys["period"] == P2]
    assert set(buys_p2["symbol"]) == {"AAA", "BBB", "EEE", "FFF"}
    assert list(buys_p2["score"]) == sorted(buys_p2["score"], reverse=True)
    assert buys_p2.iloc[0]["symbol"] == "FFF"  # NEW + only holder -> highest score


def test_consensus_exits_membership_and_order(out):
    exits = out["consensus_exits"]
    assert set(exits["symbol"]) == {"FFF", "DDD"}
    row = exits.set_index("symbol")
    assert row.loc["FFF", "sold_out"] == 1
    assert row.loc["DDD", "trimmed"] == 1
    assert list(exits["sold_out"]) == sorted(exits["sold_out"], reverse=True)


def test_high_conviction_filter(out):
    hc = out["high_conviction"].set_index("symbol")
    assert set(hc.index) == {"BBB", "EEE", "FFF"}  # AAA has only 1 qualifying holder, excluded
    assert hc.loc["BBB", "managers"] == 2
    assert hc.loc["BBB", "avg_weight"] == pytest.approx(0.5)


def test_sector_rotation_counts(out):
    rotation = out["sector_rotation"].set_index("sector")
    energy = rotation.loc["Energy"]
    assert energy["increasing"] == 1  # M2 rose
    assert energy["decreasing"] == 1  # M1 fell (sold FFF out)
    assert energy["avg_change"] == pytest.approx((-0.090909 + 0.3) / 2, abs=1e-4)


def test_similarity_identical_and_orthogonal(out):
    sim = out["manager_similarity"][P2]
    ciks = sim["ciks"]
    matrix = sim["matrix"]

    def score(a, b):
        return matrix[ciks.index(a)][ciks.index(b)]

    assert score("2222222222", "3333333333") == pytest.approx(1.0)  # M2, M3: identical proportions
    assert score("1111111111", "2222222222") == pytest.approx(0.0)  # M1: disjoint symbol set
    assert score("1111111111", "3333333333") == pytest.approx(0.0)


def test_options_exposure_lists(out):
    opts = out["options_exposure"].set_index(["period", "symbol"])
    eee_p1 = opts.loc[(P1, "EEE")]
    assert eee_p1["equity_holders"] == ["2222222222"]
    assert eee_p1["put_holders"] == ["1111111111"]
    assert eee_p1["call_holders"] == []

    aaa_p2 = opts.loc[(P2, "AAA")]
    assert aaa_p2["equity_holders"] == ["1111111111"]
    assert aaa_p2["call_holders"] == ["1111111111"]


def test_options_exposure_has_columns_with_zero_option_rows(h):
    """Regression: a fund/window with no PUT/CALL rows must not produce a columnless
    DataFrame -- store.py indexes options_exposure by period/symbol unconditionally."""
    no_options = h[h["put_call"].isna()]
    result = options_exposure(no_options)
    assert list(result.columns) == ["period", "symbol", "equity_holders", "call_holders", "put_holders"]
    assert len(result) == 0


def test_cluster_common_holdings(out):
    beta_p2 = out["clusters"][P2]["Beta"]
    assert beta_p2["members"] == ["1111111111", "2222222222", "3333333333"]
    assert set(beta_p2["common_holdings"]) == {"BBB", "EEE", "FFF"}  # held by 2 of 3 members
    assert beta_p2["top_sector"] == "Tech"

    beta_p1 = out["clusters"][P1]["Beta"]
    assert beta_p1["common_holdings"] == []  # M1 and M2 hold disjoint symbols at P1


def test_conviction_score_rewards_concentrated_recent_over_widely_held_stale():
    """Sanity check from the plan: 12 managers @ 2.5% with no activity (raw 18)
    should score lower than 4 managers @ 9% with 3 new (raw ~84)."""
    sqs = pd.DataFrame(
        [
            {
                "period": "P",
                "symbol": "WIDE",
                "manager_count": 12,
                "avg_weight": 0.025,
                "new_count": 0,
                "added_count": 0,
                "holders": [{"status": "UNCHANGED", "change": 0.0, "weight": 0.025} for _ in range(12)],
            },
            {
                "period": "P",
                "symbol": "HOT",
                "manager_count": 4,
                "avg_weight": 0.09,
                "new_count": 3,
                "added_count": 0,
                "holders": [{"status": "NEW", "change": None, "weight": 0.09} for _ in range(3)]
                + [{"status": "UNCHANGED", "change": 0.09, "weight": 0.09}],
            },
        ]
    )
    cfg = {
        "score": {"weight_scale": 0.05, "new_bonus": 0.5, "added_bonus": 0.25, "accumulation_scale": 0.02, "accumulation_cap": 3}
    }
    scored = conviction_score(sqs, cfg).set_index("symbol")
    assert scored.loc["HOT", "score"] > scored.loc["WIDE", "score"]
    assert scored.loc["HOT", "score"] == 100  # highest raw in its period -> normalized to 100
    assert scored.loc["WIDE", "score"] == pytest.approx(round(100 * 18 / 84))
