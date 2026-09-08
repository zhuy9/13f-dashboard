from pathlib import Path

import pandas as pd
import pytest

from derive import (
    _OPTIONS_EXPOSURE_COLUMNS,
    conviction_score,
    derive_all,
    manager_quarter_summary,
    options_exposure,
    security_kind,
    split_factor,
)

FIXTURE = Path(__file__).parent / "fixtures" / "holdings_small.csv"

FUNDS = [
    {"cik": "1111111111", "short": "M1", "cluster": "Beta"},
    {"cik": "2222222222", "short": "M2", "cluster": "Beta"},
    {"cik": "3333333333", "short": "M3", "cluster": "Beta"},
]

# Small, fixture-scaled thresholds -- not the production signals_config.json values.
CFG = {
    "methodology_version": 2,
    "quarters": 2,
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


@pytest.mark.parametrize(
    "cls, expected",
    [
        ("COM", "EQUITY"),
        ("COM CL A", "EQUITY"),
        ("ORD SHS", "EQUITY"),
        ("IBOXX HI YD ETF", "EQUITY"),  # a bond ETF is still an equity-style holding
        ("NOTE  0.500% 6/0", "NOTE"),  # truncated to 16 chars by the form
        ("SR NT 5% 2030", "NOTE"),
        ("*W EXP 01/01/202", "WARRANT"),
        ("WTS", "WARRANT"),
        ("TR UNIT", "EQUITY"),  # LP and trust units are equity: SPY is "TR UNIT"
        ("DEPOSITARY UNIT", "EQUITY"),  # Icahn Enterprises LP
        ("COM UNIT REP LTD", "EQUITY"),  # MPLX, an MLP
        (None, "EQUITY"),  # missing Class falls back to what the field means almost always
        ("", "EQUITY"),
    ],
)
def test_security_kind_reads_the_filers_own_class_field(cls, expected):
    assert security_kind(cls) == expected


def test_positions_carry_their_instrument_kind(h):
    kinds = derive_all(h, FUNDS, CFG)["manager_quarter_summary"]["kind"]
    assert set(kinds) == {"EQUITY"}, "the fixture is all COM"


def test_derive_all_keeps_only_the_newest_quarters_periods(h):
    """A manager who stopped filing drags older periods into the union; those render as
    near-empty quarters holding one stale filer. Only the newest `quarters` survive."""
    stale = h[h["cik"] == "1111111111"].copy()
    stale["period"] = "2025-12-31"
    out = derive_all(pd.concat([stale, h], ignore_index=True), FUNDS, CFG)

    assert out["periods"] == [P1, P2]
    assert "2025-12-31" not in set(out["manager_quarter_summary"]["period"])
    assert "2025-12-31" not in set(out["stock_quarter_summary"]["period"])


def _mqs_row(mqs: pd.DataFrame, cik: str, period: str, symbol: str) -> pd.Series:
    match = mqs[(mqs["cik"] == cik) & (mqs["period"] == period) & (mqs["symbol"] == symbol)]
    assert len(match) == 1
    return match.iloc[0]


def test_weights_and_totals(out):
    """M1 P1 files 29,000 of equity plus a 15,000 PUT, so the filing total is 44,000 and the
    weight denominator is 29,000. Both are kept: the total is what reconciles against the
    filing, the equity value is what a conviction weight is a share of."""
    totals = out["totals"].set_index(["cik", "period"])
    assert totals.loc[("1111111111", P1), "total_value"] == 44000
    assert totals.loc[("1111111111", P1), "equity_value"] == 29000
    assert totals.loc[("1111111111", P2), "total_value"] == 35000
    assert totals.loc[("1111111111", P2), "equity_value"] == 32000
    aaa_p1 = _mqs_row(out["manager_quarter_summary"], "1111111111", P1, "AAA")
    assert aaa_p1["weight"] == pytest.approx(10000 / 29000)


def test_eligible_equity_weights_sum_to_one_per_manager_quarter(out):
    mqs = out["manager_quarter_summary"]
    held = mqs[(mqs["kind"] == "EQUITY") & (mqs["value"] > 0)]
    for (cik, period), grp in held.groupby(["cik", "period"]):
        assert grp["weight"].sum() == pytest.approx(1.0), f"{cik} {period}"


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
    # CCC: shares did not move (UNCHANGED) but its weight rose -- status is share-based,
    # change is weight-based, and the rest of M1's book shrank around it.
    ccc = _mqs_row(mqs, "1111111111", P2, "CCC")
    assert ccc["status"] == "UNCHANGED"
    assert ccc["change"] > 0
    # BBB: shares rose (ADDED) but weight fell -- same principle, opposite direction.
    bbb = _mqs_row(mqs, "2222222222", P2, "BBB")
    assert bbb["status"] == "ADDED"
    assert bbb["change"] < 0
    # FFF: a new position's change is its full weight -- it came from zero.
    fff = _mqs_row(mqs, "2222222222", P2, "FFF")
    assert fff["status"] == "NEW"
    assert fff["change"] == pytest.approx(fff["weight"])
    # Period[0] rows and a manager with no prior filing both get null change.
    p1_rows = mqs[mqs["period"] == P1]
    assert p1_rows["change"].isna().all()
    m3_rows = mqs[(mqs["cik"] == "3333333333") & (mqs["period"] == P2)]
    assert m3_rows["change"].isna().all()


def test_sold_out_row_emitted_with_change_negative_prev_weight(out):
    fff = _mqs_row(out["manager_quarter_summary"], "1111111111", P2, "FFF")
    assert fff["value"] == 0
    assert fff["weight"] == 0
    assert fff["prev_weight"] == pytest.approx(4000 / 29000)
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
    assert energy["avg_change"] == pytest.approx((-4000 / 29000 + 0.3) / 2, abs=1e-4)


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
    assert list(result.columns) == _OPTIONS_EXPOSURE_COLUMNS
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


def _rows(period: str, *specs) -> pd.DataFrame:
    """A one-manager holdings frame. Each spec is (symbol, cls, value, shares, put_call)."""
    return pd.DataFrame(
        [
            {
                "cik": "9999999999",
                "short": "M9",
                "period": period,
                "filed_at": "2026-08-14",
                "cusip": f"{symbol}000000",
                "symbol": symbol,
                "ticker": symbol,
                "name": f"{symbol} Co",
                "sector": "Tech",
                "cls": cls,
                "value": value,
                "shares": shares,
                "put_call": put_call,
            }
            for symbol, cls, value, shares, put_call in specs
        ]
    )


def _weights(h: pd.DataFrame) -> dict[str, float]:
    mqs = derive_all(h, [{"cik": "9999999999", "short": "M9", "cluster": "Beta"}], CFG)["manager_quarter_summary"]
    return dict(zip(mqs["symbol"], mqs["weight"]))


def test_an_option_row_does_not_dilute_the_equity_weights():
    """F1: the denominator used to include option rows. An option's reported value is the value
    of the underlying shares, so a 900 CALL on a 100-dollar equity book used to push both real
    positions under 6% and make this manager look utterly unconcentrated."""
    weights = _weights(_rows(P2, ("AAA", "COM", 60, 6, None), ("BBB", "COM", 40, 4, None), ("AAA", "COM", 900, 90, "CALL")))

    assert weights["AAA"] == pytest.approx(0.60)
    assert weights["BBB"] == pytest.approx(0.40)


def test_notes_and_warrants_stay_inspectable_but_change_no_weight():
    """A convertible note is debt and a warrant is not the share. Both stay in the table so the
    manager page can badge them, and both stay out of the denominator."""
    equity_only = _weights(_rows(P2, ("AAA", "COM", 60, 6, None), ("BBB", "COM", 40, 4, None)))
    with_paper = _weights(
        _rows(
            P2,
            ("AAA", "COM", 60, 6, None),
            ("BBB", "COM", 40, 4, None),
            ("CCC", "NOTE  0.500% 6/0", 500, 500, None),
            ("DDD", "*W EXP 01/01/202", 300, 300, None),
        )
    )

    assert with_paper["AAA"] == pytest.approx(equity_only["AAA"])
    assert with_paper["BBB"] == pytest.approx(equity_only["BBB"])
    assert set(with_paper) == {"AAA", "BBB", "CCC", "DDD"}  # still there to look at


def test_a_manager_holding_no_eligible_equity_gets_no_weight_rather_than_zero():
    """Zero equity value is an unanswerable denominator, not zero conviction. It must not
    divide by zero and must not render as a real 0% position. Straight at
    manager_quarter_summary: a universe with no equity at all leaves every later table empty,
    which is a separate (and hypothetical) concern from the division itself."""
    h = _rows(P2, ("AAA", "COM", 900, 90, "CALL"), ("CCC", "NOTE  5% 2030", 500, 500, None))
    h = h.assign(kind=h["cls"].map(security_kind))

    mqs = manager_quarter_summary(h, [P2])

    assert mqs["weight"].isna().all()
    assert not (mqs["weight"] == 0).any()


def test_trimmed_can_still_gain_weight_because_the_two_axes_are_independent():
    """Status compares shares, change compares weights. Selling a third of AAA while the rest of
    the book halves leaves AAA both TRIMMED and a larger share of the portfolio. The UI shows
    both numbers side by side, so the fixture that proves they can disagree earns its keep."""
    h = pd.concat(
        [
            _rows(P1, ("AAA", "COM", 300, 300, None), ("BBB", "COM", 700, 700, None)),
            _rows(P2, ("AAA", "COM", 200, 200, None), ("BBB", "COM", 100, 100, None)),
        ],
        ignore_index=True,
    )
    mqs = derive_all(h, [{"cik": "9999999999", "short": "M9", "cluster": "Beta"}], CFG)["manager_quarter_summary"]
    aaa = _mqs_row(mqs, "9999999999", P2, "AAA")

    assert aaa["status"] == "TRIMMED"
    assert aaa["weight"] == pytest.approx(200 / 300)
    assert aaa["change"] == pytest.approx(200 / 300 - 300 / 1000)


def test_conviction_score_components_are_reproducible_by_hand():
    """F3: the score had no documented breakdown. Every factor here is checked against the
    formula in METHODOLOGY.md, and the raw numbers come out exact, not approximate.

    WIDE: 12 managers x (1 + 0.025/0.05) x 1 (no new) x 1 (no added) x 1 (no accumulation) = 18
    HOT:   4 managers x (1 + 0.09/0.05)  x (1 + 3*0.5) x 1 x min(0.09/0.02 + 1, 3) = 4*2.8*2.5*3 = 84

    And the 0-100 scale is per quarter: HOT is 100 because it is that quarter's highest raw
    score, not because it is a certainty. WIDE reads 21, meaning 18/84 of the quarter's top.
    """
    cfg = {
        "score": {"weight_scale": 0.05, "new_bonus": 0.5, "added_bonus": 0.25, "accumulation_scale": 0.02, "accumulation_cap": 3}
    }
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

    scored = conviction_score(sqs, cfg).set_index("symbol")

    assert scored.loc["WIDE", "avg_change"] == pytest.approx(0.0)
    assert scored.loc["HOT", "avg_change"] == pytest.approx(0.09)
    assert scored.loc["HOT", "score"] == 100
    assert scored.loc["WIDE", "score"] == round(100 * 18 / 84) == 21


SPLIT_2FOR1 = [{"symbol": "AAA", "effective_date": "2026-05-01", "ratio": 2, "source": "test"}]
REVERSE_1FOR10 = [{"symbol": "AAA", "effective_date": "2026-05-01", "ratio": 0.1, "source": "test"}]


def _two_quarters(p1_shares: int, p1_value: int, p2_shares: int, p2_value: int, actions=()) -> pd.Series:
    """One symbol held across both periods; returns its P2 mqs row."""
    h = pd.concat(
        [
            _rows(P1, ("AAA", "COM", p1_value, p1_shares, None)),
            _rows(P2, ("AAA", "COM", p2_value, p2_shares, None)),
        ],
        ignore_index=True,
    )
    h = h.assign(kind=h["cls"].map(security_kind))
    mqs = manager_quarter_summary(h, [P1, P2], actions)
    return _mqs_row(mqs, "9999999999", P2, "AAA")


def test_a_forward_split_is_not_buying():
    """F2: 100 shares becoming 200 across a 2-for-1 split is the same position. The value stays
    put because the price halved, and the old code called this ADDED."""
    row = _two_quarters(100, 10_000, 200, 10_000, SPLIT_2FOR1)

    assert row["status"] == "UNCHANGED"
    assert row["prev_shares"] == 100  # as filed
    assert row["adj_prev_shares"] == 200  # on the current share basis
    assert row["share_change"] == pytest.approx(0.0)


def test_a_reverse_split_is_not_selling():
    row = _two_quarters(1000, 10_000, 100, 10_000, REVERSE_1FOR10)

    assert row["status"] == "UNCHANGED"
    assert row["adj_prev_shares"] == 100


def test_a_split_plus_a_real_increase_keeps_the_increase():
    """2-for-1 on 100 shares is 200; holding 220 means they really bought 10% more."""
    row = _two_quarters(100, 10_000, 220, 11_000, SPLIT_2FOR1)

    assert row["status"] == "ADDED"
    assert row["share_change"] == pytest.approx(0.10)


def test_an_action_outside_the_two_report_dates_does_not_adjust():
    """Only an action effective inside the interval the two share counts straddle applies."""
    before = [{"symbol": "AAA", "effective_date": "2026-01-01", "ratio": 2, "source": "test"}]

    assert _two_quarters(100, 10_000, 200, 10_000, before)["adj_prev_shares"] == 100


def test_an_unexplained_clean_doubling_is_flagged_not_adjusted():
    """No entry in corporate_actions.json means no adjustment -- a share count that looks like
    a split is not evidence that one happened. It is surfaced as unverified instead."""
    row = _two_quarters(100, 10_000, 200, 10_000)

    assert row["adj_prev_shares"] == 100  # untouched
    assert row["status"] == "ADDED"  # still reads as buying, because we cannot prove otherwise
    assert row["split_unverified"] is True


def test_doubling_a_position_by_buying_is_not_flagged_as_a_suspected_split():
    """The discriminator is value: a real purchase doubles the value along with the shares, a
    split leaves it alone. Without this, every manager who doubled a round position would flag."""
    row = _two_quarters(100, 10_000, 200, 20_000)

    assert row["status"] == "ADDED"
    assert row["split_unverified"] is False


def test_split_factors_compound_and_ignore_other_symbols():
    actions = [
        {"symbol": "AAA", "effective_date": "2026-05-01", "ratio": 2, "source": "test"},
        {"symbol": "AAA", "effective_date": "2026-06-01", "ratio": 3, "source": "test"},
        {"symbol": "BBB", "effective_date": "2026-05-01", "ratio": 5, "source": "test"},
    ]

    assert split_factor("AAA", P1, P2, actions) == 6.0
    assert split_factor("BBB", P1, P2, actions) == 5.0
    assert split_factor("CCC", P1, P2, actions) == 1.0
