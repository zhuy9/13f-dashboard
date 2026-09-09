import json
from pathlib import Path

import pandas as pd

from derive import derive_all
from store import _build_manager_quarter_docs, _build_signals_docs
from test_store import CFG, FIXTURE, FUNDS

OUTPUT = Path(__file__).parents[1] / "web/src/fixtures/subset.json"


def build_fixture() -> dict:
    holdings = pd.read_csv(FIXTURE, dtype={"cik": str})
    tables = derive_all(holdings, FUNDS, CFG)
    period = tables["periods"][-1]
    cases = []
    # The whole roster proves filtering is a no-op; dropping M1 proves it recomputes. Two more
    # subsets of the same three managers exercised the same branches at 25 KB each.
    for funds in [FUNDS, FUNDS[1:]]:
        ciks = [f["cik"] for f in funds]
        selected = derive_all(holdings[holdings["cik"].isin(ciks)], funds, CFG)
        cases.append({"ciks": ciks, "expected": _build_signals_docs(selected, selected["periods"])[period]})
    return {
        "period": period,
        "published": _build_signals_docs(tables, tables["periods"])[period],
        "quarters": _build_manager_quarter_docs(tables, FUNDS),
        "cases": cases,
    }


def test_browser_parity_fixture_matches_current_python():
    assert json.loads(OUTPUT.read_text()) == build_fixture()


if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(build_fixture(), indent=2) + "\n")
