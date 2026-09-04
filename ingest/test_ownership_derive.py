import io
from pathlib import Path

import pandas as pd
import pytest

from ownership_derive import derive_all, events, recent, stakes

FIXTURE = Path(__file__).parent / "fixtures" / "ownership_small.csv"

FUNDS = [
    {
        "cik": "1791786",
        "name": "Elliott Investment Management L.P.",
        "short": "Elliott",
        "cluster": "Activist",
        "aliases": ["1048445"],
    },
]

# Small, fixture-scaled config -- not the production signals_config.json values.
CFG = {"exit_below_pct": 5.0, "min_change_pp": 0.1, "recent_events": 300}

STR_COLS = {"accession": str, "filer_cik": str, "reporting_ciks": str, "issuer_cik": str, "cusip": str, "prev_accession": str}


@pytest.fixture
def filings() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, dtype=STR_COLS)


def test_every_event_occurs(filings):
    ev = events(filings, FUNDS, CFG)
    kinds = set(ev["event"].dropna())
    assert kinds == {"NEW", "INCREASED", "DECREASED", "EXITED", "SWITCHED_TO_13D", "UPDATED"}
    assert ev["event"].isna().sum() >= 2


def test_amendment_with_no_prior_is_null_not_new(filings):
    ev = events(filings, FUNDS, CFG)
    row = ev[ev["accession"] == "0000000002-26-000001"].iloc[0]
    assert row["is_amendment"] and pd.isna(row["prev_pct"])
    assert row["event"] is None


def test_reentry_wins_over_still_below_threshold_rule4_vs_rule5():
    """Rule order 4 (prev < exit_below -> NEW) must win over rule 5 (cur < exit_below ->
    EXITED) when both hold -- i.e. a still-tiny stake after an exit reads NEW, not EXITED."""
    rows = pd.DataFrame(
        [
            {
                "accession": "acc1",
                "form": "13D",
                "is_amendment": False,
                "amendment_no": None,
                "filed_at": "2026-01-01",
                "filer_cik": "5555555555",
                "reporting_ciks": "5555555555",
                "investor_name": "Filer X",
                "cusip": "XXX000000",
                "pct": 3.0,
            },
            {
                "accession": "acc2",
                "form": "13D",
                "is_amendment": True,
                "amendment_no": 1,
                "filed_at": "2026-02-01",
                "filer_cik": "5555555555",
                "reporting_ciks": "5555555555",
                "investor_name": "Filer X",
                "cusip": "XXX000000",
                "pct": 2.0,
            },
        ]
    )
    ev = events(rows, FUNDS, CFG)
    assert ev.iloc[1]["event"] == "NEW"


def test_form_switch_wins_over_large_pct_change_rule6_vs_rule7(filings):
    """CCC000000 flips 13G -> 13D with a 1.0pp change (>= min_change_pp): rule 6 (form
    switch) must fire before rule 7 (magnitude change) is even considered."""
    ev = events(filings, FUNDS, CFG)
    row = ev[ev["accession"] == "0000000003-26-000002"].iloc[0]
    assert row["change_pp"] == 1.0  # magnitude alone would qualify as INCREASED
    assert row["event"] == "SWITCHED_TO_13D"


def test_alias_canonicalises_to_roster_cik(filings):
    ev = events(filings, FUNDS, CFG)
    row = ev[ev["accession"] == "0000000004-26-000001"].iloc[0]
    assert row["investor_cik"] == "1791786"
    assert row["short"] == "Elliott"
    assert row["is_roster"] and row["is_activist"]


def test_priority_table(filings):
    ev = events(filings, FUNDS, CFG).set_index("accession")
    assert ev.loc["0000000001-26-000001", "priority"] == "HIGH"  # 13D NEW
    assert ev.loc["0000000003-26-000001", "priority"] == "MEDIUM"  # 13G NEW
    assert ev.loc["0000000001-26-000003", "priority"] == "MEDIUM"  # 13D DECREASED
    assert ev.loc["0000000001-26-000004", "priority"] == "LOW"  # 13D UPDATED, non-roster
    assert ev.loc["0000000003-26-000002", "priority"] == "HIGH"  # SWITCHED_TO_13D
    assert ev.loc["0000000004-26-000001", "priority"] == "HIGH"  # activist NEW


def test_stakes_is_current(filings):
    ev = events(filings, FUNDS, CFG)
    st = stakes(ev, CFG).set_index("cusip")
    assert bool(st.loc["AAA000000", "is_current"]) is True  # last pct 6.5
    assert bool(st.loc["BBB000000", "is_current"]) is False  # last pct is null


def test_recent_orders_newest_first(filings):
    ev = events(filings, FUNDS, CFG)
    top = recent(ev, 3)
    assert list(top["filed_at"]) == sorted(top["filed_at"], reverse=True)
    assert top.iloc[0]["filed_at"] == ev["filed_at"].max()


def test_events_does_not_mutate_input(filings):
    before = filings.copy(deep=True)
    events(filings, FUNDS, CFG)
    pd.testing.assert_frame_equal(filings, before)


def test_derive_all_keys(filings):
    out = derive_all(filings, FUNDS, CFG)
    assert set(out) == {"filings", "events", "stakes", "recent"}


def test_reporting_ciks_survives_a_parquet_round_trip():
    """`reporting_ciks` is a real Python list on a fresh fetch but comes back as a
    numpy array after a parquet round-trip (production's actual GCS state format)."""
    rows = pd.DataFrame(
        [
            {
                "accession": "acc1",
                "form": "13D",
                "is_amendment": False,
                "amendment_no": None,
                "filed_at": "2026-01-01",
                "filer_cik": "0001048445",
                "reporting_ciks": ["0001048445"],
                "investor_name": "Elliott",
                "cusip": "XXX000000",
                "pct": 6.0,
            }
        ]
    )
    buf = io.BytesIO()
    rows.to_parquet(buf, index=False)
    buf.seek(0)
    round_tripped = pd.read_parquet(buf)
    assert not isinstance(round_tripped.iloc[0]["reporting_ciks"], list)  # confirms the regression case

    ev = events(round_tripped, FUNDS, CFG)
    assert ev.iloc[0]["investor_cik"] == "1791786"
    assert ev.iloc[0]["is_roster"]
