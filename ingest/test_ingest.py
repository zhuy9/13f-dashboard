import pandas as pd

from ingest import counts_line, step_summary


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
