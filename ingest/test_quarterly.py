from quarterly import merge_index


def _issue(period: str, headline: str = "h") -> dict:
    return {"period": period, "label": period[:4], "headline": headline, "builtAt": "2026-11-17T12:00:00+00:00"}


def test_merge_index_adds_replaces_and_keeps_newest_first():
    index = merge_index(None, _issue("2026-06-30"))
    index = merge_index(index, _issue("2026-09-30"))
    index = merge_index(index, _issue("2026-06-30", headline="rebuilt"))
    assert [(e["period"], e["headline"]) for e in index["issues"]] == [("2026-09-30", "h"), ("2026-06-30", "rebuilt")]
    assert index["updatedAt"] == "2026-11-17T12:00:00+00:00"
