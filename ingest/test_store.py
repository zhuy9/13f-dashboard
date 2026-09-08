from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pandas as pd
import pytest

from derive import derive_all
from store import (
    _build_manager_quarter_docs,
    _build_meta,
    _build_stock_docs,
    _camel,
    _clean,
    _commit_in_batches,
    read_holder_counts,
    write_firestore,
)

FIXTURE = Path(__file__).parent / "fixtures" / "holdings_small.csv"
FUNDS = [
    {"cik": "1111111111", "short": "M1", "name": "M1 Capital", "cluster": "Beta"},
    {"cik": "2222222222", "short": "M2", "name": "M2 Capital", "cluster": "Beta"},
    {"cik": "3333333333", "short": "M3", "name": "M3 Capital", "cluster": "Beta"},
]
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
    assert "symbols" not in meta  # its own doc: every page reads meta/latest, only search needs symbols
    assert meta["clusters"][0]["commonHoldings"]  # camelCase, non-empty at latest period


def test_symbols_get_their_own_doc(tables):
    db = _FakeDb({})

    write_firestore(db, tables, FUNDS, tables["periods"])

    assert {"symbol", "name", "sector"} <= db.written["meta/symbols"]["symbols"][0].keys()


def test_manager_quarter_doc_has_camelcase_and_sold_out_position(tables):
    docs = _build_manager_quarter_docs(tables, FUNDS)
    doc = docs["1111111111_2026-06-30"]
    assert doc["positions"][0]["sector"]  # the treemap reads it here, not from meta/latest
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


class _FakeDb:
    """Just enough Firestore for write_firestore: batched set/delete and id-only collection reads."""

    def __init__(self, existing: dict[str, list[str]]):
        self.existing, self.written, self.deleted, self.read = existing, {}, [], []

    def document(self, path):
        return path

    def batch(self):
        return SimpleNamespace(set=self.written.__setitem__, delete=self.deleted.append, commit=lambda: None)

    def collection(self, name):
        self.read.append(name)
        snaps = [SimpleNamespace(id=i, reference=i) for i in self.existing.get(name, [])]
        return SimpleNamespace(select=lambda _fields: SimpleNamespace(stream=lambda: snaps))


def test_write_firestore_prunes_stale_docs_in_the_collections_it_owns(tables):
    db = _FakeDb(
        {
            "managers": ["1111111111", "938582"],  # 938582 left the roster
            "manager_quarters": ["1111111111_2026-06-30", "1111111111_2024-12-31"],  # period fell out
            "stocks": ["AAA", "GONE"],
            "signals": ["2026-06-30", "2024-12-31"],
            "securities": ["037833100"],  # an accumulating cache, not ours to prune
            "ownership_issuers": ["AAA"],  # the other pipeline's
        }
    )

    deleted = write_firestore(db, tables, FUNDS, tables["periods"])

    assert set(db.deleted) == {"938582", "1111111111_2024-12-31", "GONE", "2024-12-31"}
    assert deleted == 4
    assert "securities" not in db.read and "ownership_issuers" not in db.read


def test_write_firestore_skips_pruning_when_a_manager_failed(tables):
    """A failed fetch leaves that manager with no rows -- pruning would delete quarters it has."""
    db = _FakeDb({"managers": ["938582"], "stocks": ["GONE"]})

    assert write_firestore(db, tables, FUNDS, tables["periods"], prune=False) == 0
    assert db.deleted == []


class _CountingDb:
    """Records how many documents went into each commit."""

    def __init__(self):
        self.commits: list[int] = []

    def document(self, path):
        return path

    def batch(self):
        docs: list[str] = []
        return SimpleNamespace(set=lambda ref, data: docs.append(ref), commit=lambda: self.commits.append(len(docs)))


def test_commit_in_batches_splits_on_size_not_only_on_count():
    """A Firestore commit is capped on total size as well as operation count, and at 12 quarters
    the size ceiling is the one hit first -- 400 manager_quarters docs is tens of MB and the
    server answers "400 Transaction too big"."""
    db = _CountingDb()
    one_mb = {"blob": "x" * 1_000_000}

    _commit_in_batches(db, [(f"stocks/{i}", one_mb) for i in range(10)])

    assert sum(db.commits) == 10, "every document is written exactly once"
    assert len(db.commits) > 1, "10 MB cannot go in a single commit"
    assert max(db.commits) <= 4, "a commit must stay under the 4 MB ceiling"


def test_stock_doc_id_encodes_slash_matching_web_encodeuricomponent():
    # write_firestore() keys stocks/{doc_id} with quote(symbol, safe=""). A SPAC
    # unit/warrant ticker like "ABC/U" would otherwise split into a bad nested path.
    assert quote("ABC/U", safe="") == "ABC%2FU"
    assert quote("BRK.B", safe="") == "BRK.B"  # ordinary tickers are untouched


class _OneDocDb:
    """Just enough Firestore for read_holder_counts: a single document get()."""

    def __init__(self, doc):
        self.doc = doc

    def document(self, path):
        snap = SimpleNamespace(exists=self.doc is not None, to_dict=lambda: self.doc)
        return SimpleNamespace(get=lambda: snap)


def test_holder_counts_doc_round_trips_to_the_map_ownership_reads(tables):
    db = _FakeDb({})

    write_firestore(db, tables, FUNDS, tables["periods"])

    doc = db.written["meta/holder_counts"]
    assert doc["period"] == tables["periods"][-1]
    assert all(row["n"] >= 1 for row in doc["counts"]), "a symbol nobody holds is left out, not stored as 0"
    assert read_holder_counts(_OneDocDb(doc)) == {row["symbol"]: row["n"] for row in doc["counts"]}


def test_read_holder_counts_is_none_not_empty_when_ingest_has_never_run():
    """{} would read as "held by nobody" downstream; the absent doc means "no answer yet"."""
    assert read_holder_counts(_OneDocDb(None)) is None
