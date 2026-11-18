"""Template sentences for the quarterly issue (docs/PLAN.md Milestone 20.3). Pure: an issue of
facts in, a new issue with text out. Every number in a sentence comes from the facts.
Rules: no advice words, never the word "short", planned and discretionary sales named apart,
a window in `noData` reads "no data", never 0."""

TITLES = {
    "bought": "Most net buyers",
    "sold": "Most net sellers",
    "split": "Where they disagree",
    "new_positions": "Biggest new positions",
    "conviction": "High-conviction list",
    "sectors": "Sector shifts",
    "stakes": "Large-holder filings (13D/13G)",
    "insider_buys": "Insider buying",
    "insider_sales": "Insider sales (discretionary)",
    "cross": "Across filings",
}


def pct1(x: float) -> str:
    return f"{x * 100:.1f}%"


def pp1(x: float) -> str:
    return f"{x * 100:+.1f} pts"


def names(items: list[str], n: int = 3, total: int = 0) -> str:
    """ "A", "A and B", "A, B and C", "A, B, C and 2 more". `total` counts items past a cap."""
    total = max(total, len(items))
    if total > n:
        return f"{', '.join(items[:n])} and {total - n} more"
    return " and ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else "".join(items)


def window_counts(section: dict) -> str:
    def one(name: str) -> str:
        return "no data" if name in section["noData"] else f"{section['windowTotals'].get(name, 0):,}"

    return f"{one('quarter')} during the quarter, {one('since')} since it ended"


def _stocks(n: int) -> str:
    return f"{n:,} stock" if n == 1 else f"{n:,} stocks"


def _symbols(rows: list[dict]) -> list[str]:
    return [r["symbol"] for r in rows]


def _summary(section: dict, cfg: dict) -> str:
    rows, n, top = section["rows"], section["total"], (section["rows"] or [None])[0]
    min_managers = cfg["consensus_min_managers"]
    match section["id"]:
        case "bought":
            if not top:
                return f"No stock had {min_managers} or more managers buying on net."
            return (
                f"{_stocks(n)} had more managers buying than selling. {top['symbol']} led: "
                f"{top['buyers']} bought or added, {top['sellers']} trimmed or sold."
            )
        case "sold":
            if not top:
                return f"No stock had {min_managers} or more managers selling on net."
            return (
                f"{_stocks(n)} had more managers selling than buying. {top['symbol']} led: "
                f"{top['sellers']} trimmed or sold, {top['buyers']} bought or added."
            )
        case "split":
            if not top:
                return "No stock split the managers."
            return (
                f"Managers were close to evenly split on {_stocks(n)}. The largest: {top['symbol']}, "
                f"{top['buyers']} buying and {top['sellers']} selling."
            )
        case "new_positions":
            if not top:
                return "No manager opened a new position."
            return f"The largest new position: {top['short']} opened {top['symbol']} at {pct1(top['weight'])} of its portfolio."
        case "conviction":
            listed = [r for r in rows if r["change"] != "LEFT"]
            if not listed:
                return "No stock met the high-conviction bar."
            text = (
                f"{_stocks(len(listed))} are held at {pct1(cfg['high_conviction_min_weight'])} or more of the "
                f"portfolio by at least {cfg['high_conviction_min_managers']} managers."
            )
            for word, change in (("Joined", "ENTERED"), ("Left", "LEFT")):
                moved = _symbols([r for r in rows if r["change"] == change])
                text += f" {word}: {names(moved)}." if moved else ""
            return text
        case "sectors":
            parts = []
            if rows and rows[0]["avgChange"] > 0:
                parts.append(f"{rows[0]['sector']} gained the most average weight ({pp1(rows[0]['avgChange'])}).")
            if rows and rows[-1]["avgChange"] < 0:
                parts.append(f"{rows[-1]['sector']} lost the most ({pp1(rows[-1]['avgChange'])}).")
            return " ".join(parts) or "No sector moved."
        case "stakes":
            return f"Notable 13D/13G filings: {window_counts(section)}."
        case "insider_buys":
            return f"Companies with open-market insider buying: {window_counts(section)}."
        case "insider_sales":
            return (
                f"Companies with discretionary insider sales: {window_counts(section)}. "
                "Planned (Rule 10b5-1) sales are counted apart."
            )
        case "cross":
            if not top:
                return "No stock showed up in more than one kind of filing."
            return f"{_stocks(n)} showed up in more than one kind of filing: {names(_symbols(rows), total=n)}."
    raise ValueError(f"unknown section {section['id']}")


def _headline(by_id: dict, min_managers: int) -> str:
    bought, sold = _symbols(by_id["bought"]["rows"][:3]), _symbols(by_id["sold"]["rows"][:3])
    if bought and sold:
        return f"Managers bought {names(bought)}; sold {names(sold)}"
    if bought or sold:
        return f"Managers {'bought' if bought else 'sold'} {names(bought or sold)}"
    return f"A quiet quarter: no stock had {min_managers} or more managers buying or selling on net"


def _lede(issue: dict) -> str:
    cov, t = issue["coverage"], issue["totals"]
    text = (
        f"{cov['filed']} of {cov['total']} tracked managers have filed for {issue['label']}. Together they "
        f"opened {t['opened']:,} positions, closed {t['closed']:,}, added to {t['added']:,} and trimmed {t['trimmed']:,}."
    )
    return text + (f" Not yet filed: {names(cov['missing'])}." if cov["missing"] else "")


def add_text(issue: dict, cfg: dict) -> dict:
    by_id = {s["id"]: s for s in issue["sections"]}
    return {
        **issue,
        "headline": _headline(by_id, cfg["consensus_min_managers"]),
        "lede": _lede(issue),
        "sections": [{**s, "title": TITLES[s["id"]], "summary": _summary(s, cfg)} for s in issue["sections"]],
    }
