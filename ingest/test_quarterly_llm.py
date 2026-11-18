import pytest

from quarterly_llm import ai_notes, facts_text
from quarterly_text import add_text
from test_quarterly_derive import _inputs

KEY = "sk-test-not-real"
CFG = {"ai_model": "test-model", "ai_max_tokens": 100}
ISSUE = add_text(_inputs(), {"consensus_min_managers": 3, "high_conviction_min_weight": 0.03, "high_conviction_min_managers": 3})
GOOD = {
    "headline": "Managers bought B73 and B51; sold L15",
    "lede": "2 of 3 tracked managers filed for 2026 Q3.",
    "notes": {"bought": "B73 led with 7 managers buying.", "not_a_section": "ignored"},
}


class _Resp:
    def __init__(self, status: int, data: dict):
        self.status_code, self._data, self.headers = status, data, {"content-type": "application/json"}

    def json(self) -> dict:
        return self._data


def _post(answer: dict, status: int = 200):
    def post(url, **kwargs):
        post.calls.append(kwargs)
        if status != 200:
            return _Resp(status, {"type": "error", "error": {"type": "overloaded_error"}})
        return _Resp(200, {"content": [{"type": "tool_use", "name": "write_notes", "input": answer}]})

    post.calls = []
    return post


def _never(url, **kwargs):
    raise AssertionError("no API call expected")


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)


def test_a_valid_answer_passes_and_the_request_forces_the_tool(key, capsys):
    post = _post(GOOD)
    ai = ai_notes(ISSUE, CFG, None, post=post)
    assert (ai["headline"], ai["lede"], ai["notes"]) == (GOOD["headline"], GOOD["lede"], {"bought": GOOD["notes"]["bought"]})
    sent = post.calls[0]
    assert sent["headers"]["x-api-key"] == KEY and sent["json"]["tool_choice"] == {"type": "tool", "name": "write_notes"}
    assert KEY not in capsys.readouterr().out


@pytest.mark.parametrize(
    "headline",
    [
        "Managers bought 99 stocks",  # a number not in the facts
        "ZZZZ led the quarter",  # a ticker not in the facts
        "<b>B73</b> led",  # markup
        "See https://example.test for B73",  # a URL
        "Investors should look at B73",  # advice
        "Managers went short L15",  # never "short"
        "B73 " * 30,  # too long
    ],
)
def test_a_failing_field_is_dropped_alone(key, headline):
    ai = ai_notes(ISSUE, CFG, None, post=_post({**GOOD, "headline": headline}))
    assert ai["headline"] is None and ai["lede"] == GOOD["lede"]


def test_an_http_error_means_no_ai_and_prints_no_key(key, capsys):
    assert ai_notes(ISSUE, CFG, None, post=_post(GOOD, status=529)) is None
    out = capsys.readouterr().out
    assert "HTTP 529 overloaded_error" in out and KEY not in out


def test_unchanged_facts_reuse_the_stored_notes_without_a_call(key):
    stored = ai_notes(ISSUE, CFG, None, post=_post(GOOD))
    assert ai_notes(ISSUE, CFG, stored, post=_never) is stored
    another_model = _post(GOOD)
    ai_notes(ISSUE, {**CFG, "ai_model": "other-model"}, stored, post=another_model)
    assert len(another_model.calls) == 1  # the model is part of the hash


def test_no_key_means_no_call(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ai_notes(ISSUE, CFG, None, post=_never) is None


def test_facts_text_leaves_out_free_text_and_outside_names():
    text = facts_text(ISSUE)
    assert "free text from the filer" not in text and "Some Filer LP" not in text
    assert "an outside filer" in text and "B73: 7 buying, 3 selling" in text
