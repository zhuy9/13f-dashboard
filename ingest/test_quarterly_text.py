import json
import re

from quarterly_text import TITLES, add_text, names, pct1, pp1, window_counts

CFG = {"consensus_min_managers": 3, "high_conviction_min_weight": 0.03, "high_conviction_min_managers": 3}


def _issue(rows: dict | None = None, missing: list[str] | None = None, no_data: list[str] | None = None) -> dict:
    """Facts as quarterly_derive.facts returns them; `rows` fills sections by id."""
    rows = rows or {}
    events = {"stakes", "insider_buys", "insider_sales"}

    def section(id_: str) -> dict:
        found = rows.get(id_, [])
        s = {"id": id_, "total": len(found), "noData": [], "rows": found}
        if id_ in events:
            s["noData"] = no_data or []
            s["windowTotals"] = {w: sum(r["window"] == w for r in found) for w in ("quarter", "since") if w not in s["noData"]}
        return s

    return {
        "label": "2026 Q3",
        "coverage": {"filed": 40 - len(missing or []), "total": 40, "missing": missing or []},
        "totals": {"opened": 590, "closed": 620, "added": 949, "trimmed": 1869, "unchanged": 499},
        "sections": [section(id_) for id_ in TITLES],
    }


def _net(symbol: str, buyers: int, sellers: int) -> dict:
    return {"symbol": symbol, "buyers": buyers, "sellers": sellers}


def _summaries(issue: dict) -> dict:
    return {s["id"]: s["summary"] for s in add_text(issue, CFG)["sections"]}


def test_helpers():
    assert (pct1(0.0321), pp1(0.008), pp1(-0.012)) == ("3.2%", "+0.8 pts", "-1.2 pts")
    assert names(["A", "B", "C", "D"]) == "A, B, C and 1 more"
    assert names(["A", "B", "C", "D"], total=16) == "A, B, C and 13 more"  # rows past the cap
    assert (names(["A", "B", "C"]), names(["A", "B"]), names(["A"])) == ("A, B and C", "A and B", "A")
    section = {"noData": ["quarter"], "windowTotals": {"since": 5}}
    assert window_counts(section) == "no data during the quarter, 5 since it ended"


def test_headline_names_both_sides_or_falls_back():
    bought = [_net("META", 13, 7), _net("INTC", 6, 1), _net("MOD", 5, 0), _net("SKHY", 5, 0)]
    sold = [_net("GOOGL", 3, 16)]
    assert add_text(_issue({"bought": bought, "sold": sold}), CFG)["headline"] == (
        "Managers bought META, INTC and MOD; sold GOOGL"
    )
    assert add_text(_issue({"bought": bought[:1]}), CFG)["headline"] == "Managers bought META"
    assert add_text(_issue({"sold": sold}), CFG)["headline"] == "Managers sold GOOGL"
    assert add_text(_issue(), CFG)["headline"] == ("A quiet quarter: no stock had 3 or more managers buying or selling on net")


def test_lede_counts_and_names_who_has_not_filed():
    assert add_text(_issue(), CFG)["lede"] == (
        "40 of 40 tracked managers have filed for 2026 Q3. Together they opened 590 positions, "
        "closed 620, added to 949 and trimmed 1,869."
    )
    assert add_text(_issue(missing=["Corvex", "Egerton"]), CFG)["lede"].endswith(" Not yet filed: Corvex and Egerton.")


def test_every_empty_section_has_its_own_sentence():
    assert _summaries(_issue()) == {
        "bought": "No stock had 3 or more managers buying on net.",
        "sold": "No stock had 3 or more managers selling on net.",
        "split": "No stock split the managers.",
        "new_positions": "No manager opened a new position.",
        "conviction": "No stock met the high-conviction bar.",
        "sectors": "No sector moved.",
        "stakes": "Notable 13D/13G filings: 0 during the quarter, 0 since it ended.",
        "insider_buys": "Companies with open-market insider buying: 0 during the quarter, 0 since it ended.",
        "insider_sales": (
            "Companies with discretionary insider sales: 0 during the quarter, 0 since it ended. "
            "Planned (Rule 10b5-1) sales are counted apart."
        ),
        "cross": "No stock showed up in more than one kind of filing.",
    }


def test_filled_sections_lead_with_the_top_row():
    issue = _issue(
        {
            "bought": [_net("META", 13, 7)],
            "split": [_net("AMZN", 10, 11)],
            "new_positions": [{"short": "Baker Bros", "symbol": "KOD", "weight": 0.041}],
            "conviction": [
                {"symbol": "AVGO", "change": "ENTERED"},
                {"symbol": "NVDA", "change": "STAYED"},
                {"symbol": "MU", "change": "LEFT"},
            ],
            "sectors": [{"sector": "Technology", "avgChange": 0.008}, {"sector": "Energy", "avgChange": -0.012}],
            "cross": [{"symbol": "B51"}, {"symbol": "B73"}],
        }
    )
    s = _summaries(issue)
    assert s["bought"] == "1 stock had more managers buying than selling. META led: 13 bought or added, 7 trimmed or sold."
    assert s["split"] == "Managers were close to evenly split on 1 stock. The largest: AMZN, 10 buying and 11 selling."
    assert s["new_positions"] == "The largest new position: Baker Bros opened KOD at 4.1% of its portfolio."
    assert s["conviction"] == (
        "2 stocks are held at 3.0% or more of the portfolio by at least 3 managers. Joined: AVGO. Left: MU."
    )
    assert s["sectors"] == "Technology gained the most average weight (+0.8 pts). Energy lost the most (-1.2 pts)."
    assert s["cross"] == "2 stocks showed up in more than one kind of filing: B51 and B73."


def test_a_window_without_data_says_no_data_never_zero():
    s = _summaries(_issue({"stakes": [{"window": "since"}]}, no_data=["quarter"]))
    assert s["stakes"] == "Notable 13D/13G filings: no data during the quarter, 1 since it ended."


def test_titles_are_set_and_no_text_says_short():
    out = add_text(_issue({"bought": [_net("META", 13, 7)]}), CFG)
    assert [s["title"] for s in out["sections"]] == list(TITLES.values())
    assert not re.search(r"\bshort\b", json.dumps({k: out[k] for k in ("headline", "lede")}), re.IGNORECASE)
    assert not any(re.search(r"\bshort\b", s["summary"], re.IGNORECASE) for s in out["sections"])
