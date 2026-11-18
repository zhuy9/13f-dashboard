from pathlib import Path

import pandas as pd
import pytest

from insider_derive import CODE_KINDS, clusters, derive_all, issuer_summary, people, trades, vs_13f

FIXTURE = Path(__file__).parent / "fixtures" / "insider_small.csv"

# Small, fixture-scaled config -- not the production signals_config.json values.
CFG = {
    "start_date": "2025-09-01",
    "min_open_market_value": 100000,
    "cluster_min_insiders": 3,
    "cluster_window_days": 90,
    "first_buy_lookback_days": 365,
    "recent_trades": 300,
}

STR_COLS = {"accession": str, "issuer_cik": str, "owner_cik": str}
HOLDER_COUNTS = {"TSTA": 2}


@pytest.fixture
def transactions() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, dtype=STR_COLS)


def test_every_kind_occurs(transactions):
    t = trades(transactions, CFG, HOLDER_COUNTS)
    assert set(t["kind"]) == {
        "BUY", "SELL", "AWARD", "EXERCISE", "TAX", "GIFT", "CONVERSION", "DISPOSITION_TO_ISSUER", "OTHER",
    }  # fmt: skip


def test_award_is_not_a_buy(transactions):
    t = trades(transactions, CFG, HOLDER_COUNTS)
    summary = issuer_summary(t, CFG).set_index("symbol").loc["TSTA"]
    award_shares = t[t["code"] == "A"]["shares"].sum()
    assert award_shares > 0
    # boughtShares only ever comes from code == "P" rows, so the award never leaks into it.
    assert summary["boughtShares"] == t[(t["symbol"] == "TSTA") & (t["code"] == "P")]["shares"].sum()


def test_withholding_is_not_a_sale(transactions):
    t = trades(transactions, CFG, HOLDER_COUNTS)
    summary = issuer_summary(t, CFG).set_index("symbol").loc["TSTA"]
    tax_shares = t[t["code"] == "F"]["shares"].sum()
    assert tax_shares > 0
    assert summary["soldShares"] == t[(t["symbol"] == "TSTA") & (t["code"] == "S")]["shares"].sum()


def test_planned_and_discretionary_sales_are_counted_apart(transactions):
    t = trades(transactions, CFG, HOLDER_COUNTS)
    summary = issuer_summary(t, CFG).set_index("symbol").loc["TSTA"]
    assert summary["plannedSellers"] == 1
    assert summary["discretionarySellers"] == 2
    assert summary["plannedSellers"] != summary["soldShares"]  # never summed into one number


def test_unstated_10b5_1_is_not_discretionary():
    """An `S` row with `aff10b5_one` blank (unstated) is neither planned nor discretionary."""
    row = pd.DataFrame(
        [
            {
                "accession": "X1", "form": "4", "filed_at": "2026-01-01", "transaction_date": "2026-01-01",
                "issuer_cik": "9", "issuer_name": "X", "symbol": "X", "owner_cik": "1", "owner_name": "A",
                "is_director": True, "is_officer": False, "is_ten_pct_owner": False, "officer_title": None,
                "code": "S", "shares": 100, "price": 10, "value": 1000, "aff10b5_one": None,
            }
        ]
    )  # fmt: skip
    t = trades(row, CFG, None)
    assert bool(t.iloc[0]["is_discretionary_sale"]) is False
    assert bool(t.iloc[0]["is_planned"]) is False


def test_priority_table(transactions):
    t = trades(transactions, CFG, HOLDER_COUNTS).set_index("accession")
    assert t.loc["ACC001", "priority"] == "HIGH"  # open-market buy above the value threshold
    assert t.loc["ACC003", "priority"] == "MEDIUM"  # open-market buy below the value threshold
    assert t.loc["ACC004", "priority"] == "LOW"  # planned (10b5-1) sale
    assert t.loc["ACC005", "priority"] == "MEDIUM"  # discretionary sale above the value threshold


def test_cluster_needs_min_insiders(transactions):
    c = clusters(trades(transactions, CFG, HOLDER_COUNTS), CFG)
    assert "CLUS1" in set(c["symbol"])  # 3 distinct buyers within the window
    assert "CLUS2" not in set(c["symbol"])  # only 2 distinct buyers


def test_unlisted_issuers_filing_a_placeholder_symbol_stay_apart(transactions):
    """Private funds file "NONE" or "N/A" as their symbol; ten of them once merged into one stock."""
    unlisted = transactions.iloc[[0, 1]].assign(symbol=["NONE", "n/a"], issuer_cik=["0000000001", "0000000002"])
    t = trades(pd.concat([transactions, unlisted], ignore_index=True), CFG, HOLDER_COUNTS)
    assert t["symbol"].tail(2).tolist() == ["_ISSUER0000000001", "_ISSUER0000000002"]


def test_a_future_dated_trade_does_not_move_the_cluster_window(transactions):
    """ALV reported a 2029 trade in a 2026 filing; anchored on that date, the window held nothing."""
    typo = transactions.iloc[[0]].assign(accession="TYPO", transaction_date="2029-02-19")
    t = trades(pd.concat([transactions, typo], ignore_index=True), CFG, HOLDER_COUNTS)
    assert "CLUS1" in set(clusters(t, CFG)["symbol"])
    assert "TSTA" in set(vs_13f(t, clusters(t, CFG), CFG)["symbol"])


def test_first_buy_is_null_when_log_is_too_short(transactions):
    t = trades(transactions, CFG, HOLDER_COUNTS).set_index("accession")
    assert t.loc["ACC019", "first_buy_in_window"] is None


def test_vs_13f_requires_a_tracked_holder(transactions):
    t = trades(transactions, CFG, HOLDER_COUNTS)
    v = vs_13f(t, clusters(t, CFG), CFG)
    assert "TSTA" in set(v["symbol"])  # holders13f >= 1
    assert "OTHR1" not in set(v["symbol"])  # a real buy, but no tracked 13F holder


def test_trades_does_not_mutate_input(transactions):
    before = transactions.copy(deep=True)
    trades(transactions, CFG, HOLDER_COUNTS)
    pd.testing.assert_frame_equal(transactions, before)


def test_derive_all_has_every_table(transactions):
    tables = derive_all(transactions, CFG, HOLDER_COUNTS)
    assert set(tables) == {"transactions", "trades", "clusters", "issuer_summary", "vs_13f", "people", "recent"}
    assert len(people(tables["trades"])) > 0


def test_every_code_is_classified():
    assert set(CODE_KINDS) == {"P", "S", "A", "M", "X", "F", "G", "C", "D"}


def _buys(filings: list[tuple[str, list[str]]]) -> pd.DataFrame:
    """One 100-share, $10 open-market buy of JNT per filing, emitted once per owner the way
    parse_filing does for a joint Form 4."""
    return pd.DataFrame(
        [
            {
                "accession": acc, "form": "4", "filed_at": "2026-01-02", "transaction_date": "2026-01-01",
                "issuer_cik": "9", "issuer_name": "Joint", "symbol": "JNT", "owner_cik": owner,
                "owner_name": owner, "is_director": False, "is_officer": False, "is_ten_pct_owner": True,
                "officer_title": None, "code": "P", "shares": 100, "price": 10, "value": 1000, "aff10b5_one": False,
            }
            for acc, owners in filings
            for owner in owners
        ]
    )  # fmt: skip


def test_owners_on_one_joint_filing_are_one_buyer_and_one_copy_of_the_value():
    t = trades(_buys([("J1", ["1", "2", "3"])]), CFG, {"JNT": 1})
    summary = issuer_summary(t, CFG).set_index("symbol").loc["JNT"]
    assert (summary["buyers"], summary["boughtShares"], summary["boughtValue"]) == (1, 100, 1000)
    assert clusters(t, CFG).empty
    assert vs_13f(t, clusters(t, CFG), CFG).set_index("symbol").loc["JNT", "boughtValue"] == 1000
    assert len(derive_all(_buys([("J1", ["1", "2", "3"])]), CFG, {"JNT": 1})["recent"]) == 1


def test_owners_who_file_apart_are_separate_buyers():
    t = trades(_buys([("A1", ["1"]), ("A2", ["2"]), ("A3", ["3"])]), CFG, None)
    assert issuer_summary(t, CFG).set_index("symbol").loc["JNT", "buyers"] == 3
    assert clusters(t, CFG).set_index("symbol").loc["JNT", "buyer_count"] == 3


def test_a_filer_group_links_through_a_shared_owner():
    t = trades(_buys([("A1", ["1", "2"]), ("A2", ["2", "3"]), ("A3", ["4"])]), CFG, None)
    assert t.groupby("owner_cik")["filer_group"].first().to_dict() == {"1": "1", "2": "1", "3": "1", "4": "4"}
    assert issuer_summary(t, CFG).set_index("symbol").loc["JNT", "buyers"] == 2
    assert len(people(t)) == 4  # each owner keeps a person row
