from pathlib import Path

import pandas as pd
import pytest

from derive import derive_all
from store import _build_manager_quarter_docs, _build_meta, _build_stock_docs, _camel, _clean

FIXTURE = Path(__file__).parent / "fixtures" / "holdings_small.csv"
FUNDS = [
    {"cik": "1111111111", "short": "M1", "name": "M1 Capital", "cluster": "Beta"},
    {"cik": "2222222222", "short": "M2", "name": "M2 Capital", "cluster": "Beta"},
    {"cik": "3333333333", "short": "M3", "name": "M3 Capital", "cluster": "Beta"},
]
CFG = {
    "consensus_min_managers": 1,
    "high_conviction_min_weight": 0.2,
    "high_conviction_min_managers": 2,
    "sector_move_threshold": 0.005,
    "top_n": 25,
    "score": {"weight_scale": 0.05, "new_bonus": 0.5, "added_bonus": 0.25, "accumulation_scale": 0.02, "accumulation_cap": 3},
}


def test_camel_converts_snake_case():
    assert _camel("prev_weight") == "prevWeight"
    assert _camel("weight") == "weight"


def test_clean_converts_nested_keys_and_nan():
    assert _clean({"prev_weight": float("nan"), "nested": [{"sold_out": 1}]}) == {"prevWeight": None, "nested": [{"soldOut": 1}]}


@pytest.fixture
def tables():
    df = pd.read_csv(FIXTURE, dtype={"cik": str})
    df["put_call"] = df["put_call"].where(df["put_call"].notna(), None)
    df.loc[df["put_call"] == "", "put_call"] = None
    return derive_all(df, FUNDS, CFG)


def test_build_meta_shape(tables):
    meta = _build_meta(tables, FUNDS, tables["periods"])
    assert meta["latestPeriod"] == tables["periods"][-1]
    assert len(meta["managers"]) == 3
    assert {"symbol", "name", "sector"} <= meta["symbols"][0].keys()
    assert meta["clusters"][0]["commonHoldings"]  # camelCase, non-empty at latest period


def test_manager_quarter_doc_has_camelcase_and_sold_out_position(tables):
    docs = _build_manager_quarter_docs(tables, FUNDS)
    doc = docs["1111111111_2026-06-30"]
    assert doc["totalValue"] == 35000
    assert doc["counts"]["soldOut"] == 1
    sold_out_positions = [p for p in doc["positions"] if p["status"] == "SOLD_OUT"]
    assert len(sold_out_positions) == 1
    assert "prevWeight" in sold_out_positions[0]


def test_stock_doc_has_options_and_trend(tables):
    docs = _build_stock_docs(tables, FUNDS)
    aaa = docs["AAA"]
    assert aaa["latest"]["options"]["calls"] == [{"cik": "1111111111", "short": "M1"}]
    assert len(aaa["trend"]) == 2
