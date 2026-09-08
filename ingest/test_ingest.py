import pandas as pd
import pytest

from ingest import counts_line, stale_manager_lines, step_summary


def _one_manager(periods: list[str]) -> list[tuple[dict, pd.DataFrame]]:
    return [({"cik": "1336528", "short": "Pershing"}, pd.DataFrame({"period": periods}))]


def _edgar_is_down(cik, period):
    raise RuntimeError("EDGAR 503")


@pytest.mark.parametrize(
    "filed_notice, expected",
    [
        (lambda cik, period: True, "aliases13f"),  # fixable: another manager reported it
        (lambda cik, period: False, "$100M"),  # genuinely stopped filing
        (_edgar_is_down, "EDGAR 503"),  # the gap is still reported
    ],
)
def test_stale_manager_lines_names_which_kind_of_missing(monkeypatch, filed_notice, expected):
    monkeypatch.setattr("ingest.filed_notice", filed_notice)

    (line,) = stale_manager_lines(_one_manager(["2026-03-31"]), "2026-06-30")

    assert "Pershing" in line and expected in line


def test_stale_manager_lines_says_nothing_and_asks_edgar_nothing_when_the_filing_is_there(monkeypatch):
    monkeypatch.setattr("ingest.filed_notice", lambda cik, period: pytest.fail("must not query EDGAR"))

    assert stale_manager_lines(_one_manager(["2026-03-31", "2026-06-30"]), "2026-06-30") == []


def test_counts_line_lowercases_labels_and_names_the_null_bucket():
    line = counts_line(pd.Series(["ADDED", "ADDED", "SOLD_OUT", None]))
    assert "2 added" in line
    assert "1 sold out" in line
    assert "1 unclassified" in line


def test_counts_line_on_an_empty_series():
    assert counts_line(pd.Series([], dtype=object)) == "none"


def test_step_summary_writes_a_markdown_block_when_running_in_actions(tmp_path, monkeypatch):
    path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))

    step_summary("Ingest 2026-06-30", ["9 of 34 managers filed", "positions: 3 new"])

    assert path.read_text(encoding="utf-8").splitlines() == [
        "### Ingest 2026-06-30",
        "- 9 of 34 managers filed",
        "- positions: 3 new",
        "",
    ]


def test_step_summary_appends_so_two_runs_do_not_clobber_each_other(tmp_path, monkeypatch):
    path = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))

    step_summary("First", ["a"])
    step_summary("Second", ["b"])

    assert path.read_text(encoding="utf-8").count("###") == 2


def test_step_summary_is_a_no_op_outside_actions(monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    step_summary("Ingest", ["nothing to write to"])


def test_dry_run_mutates_no_remote_state_and_writes_no_keepalive_marker(monkeypatch):
    """F5: the README claimed a dry run wrote nothing, but it wrote securities/ cache entries
    and GCS archives. Every remote write is faked to fail here, so the run only passes if it
    calls none of them -- with a cache miss and GCS_BUCKET set, the case that used to write."""
    import ingest as m

    monkeypatch.setenv("EDGAR_IDENTITY", "a@b.com")
    monkeypatch.setenv("GCS_BUCKET", "some-bucket")
    monkeypatch.setattr(m.sys, "argv", ["ingest.py", "--dry-run"])
    monkeypatch.setattr(m, "load_dotenv", lambda path: None)
    monkeypatch.setattr("edgar.set_identity", lambda identity: None)
    monkeypatch.setattr(m, "load_funds", lambda: [{"cik": "1336528", "short": "Pershing"}])
    monkeypatch.setattr(m, "init_firestore", lambda: object())
    holdings = pd.DataFrame(
        {"period": ["2026-06-30"], "cusip": ["037833100"], "value": [100], "put_call": [None], "ticker": ["AAPL"]}
    )
    monkeypatch.setattr(m, "fetch_manager", lambda fund, quarters: (holdings, {}, {("1336528", "2026-06-30"): b"<x/>"}))
    monkeypatch.setattr(m, "attach", lambda base, securities: base)
    monkeypatch.setattr(
        m,
        "derive_all",
        lambda h, funds, cfg, actions: {
            "periods": ["2026-06-30"],
            "methodology_version": 2,
            "manager_quarter_summary": pd.DataFrame({"period": [], "status": []}),
        },
    )
    monkeypatch.setattr(m, "print_dry_run_summary", lambda short, enriched: None)
    monkeypatch.setattr(m, "print_dry_run_signals", lambda tables: None)
    monkeypatch.setattr(m, "stale_manager_lines", lambda base_by_fund, latest: [])

    persisted = []
    monkeypatch.setattr(m, "ensure_securities", lambda *a, persist=True, **kw: persisted.append(persist) or {})
    for name in ["write_gcs", "write_firestore", "write_last_ingest"]:
        monkeypatch.setattr(m, name, lambda *a, called=name, **kw: pytest.fail(f"dry run called {called}"))

    assert m.main() == 0
    assert persisted == [False]  # the securities/ cache is remote state too
