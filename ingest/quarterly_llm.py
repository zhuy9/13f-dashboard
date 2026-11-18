"""Optional AI notes for the quarterly issue (docs/PLAN.md Milestone 20.5). The model only rewords
facts we hand it. Each field it returns is checked against those facts and dropped, never repaired,
on any failure. A missing key or a failed call means template text only, never a failed run."""

import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

from enrich import _HTTP
from quarterly_text import pct1, pp1

API_URL = "https://api.anthropic.com/v1/messages"
PROMPT_VERSION = "1"
MAX_CHARS = {"headline": 90, "lede": 400, "note": 240}
SYSTEM = (
    "You write short, neutral summaries of SEC filing statistics for a public dashboard. Use only the "
    "facts given. Do not add numbers, companies, causes, opinions, predictions, or advice. Do not say "
    "why anyone traded. Do not use the word 'short'. Plain text only."
)
TOOL = {
    "name": "write_notes",
    "description": "Return a headline, a lede, and at most one note per section id, from the facts only.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "lede": {"type": "string"},
            "notes": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "required": ["headline", "lede", "notes"],
    },
}
ALLOWED_CAPS = {"SEC", "ETF", "CEO", "CFO", "US", "AI", "Q1", "Q2", "Q3", "Q4"}
BANNED = re.compile(
    r"\b(should|recommend\w*|advice|advis\w*|price target|guarantee\w*|will rise|will fall|undervalued"
    r"|overvalued|bullish|bearish|short|because|due to)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?!\w)")
CAPS = re.compile(r"\b[A-Z][A-Z0-9.\-]{1,6}\b")
MARKUP = re.compile(r"[<>`]|https?://|www\.|\]\(")
_WINDOW = {"quarter": "during the quarter", "since": "since it ended"}


def _row_line(id_: str, r: dict) -> str:
    """Symbols, roster names, sector names, counts and percents only. Never a 13D purpose, a
    footnote, a person, an issuer name or an outside investor's name."""
    when = _WINDOW.get(r.get("window"), "")
    match id_:
        case "bought" | "sold" | "split":
            return f"{r['symbol']}: {r['buyers']} buying, {r['sellers']} selling"
        case "new_positions":
            return f"{r['short']} opened {r['symbol']} at {pct1(r['weight'])}"
        case "conviction":
            return f"{r['symbol']}: {r['change'].lower()}, {r['managers']} managers"
        case "sectors":
            return f"{r['sector']}: {pp1(r['avgChange'])}"
        case "stakes":
            who = r["short"] if r["isRoster"] else "an outside filer"
            return f"{r['symbol']}: {r['form']} {r['event'].lower().replace('_', ' ')} by {who}, {when}"
        case "insider_buys":
            return f"{r['symbol']}: {r['buyers']} insider buyers, {when}"
        case "insider_sales":
            sellers = f"{r['discretionarySellers']} discretionary and {r['plannedSellers']} planned sellers"
            return f"{r['symbol']}: {sellers}, {when}"
        case "cross":
            return f"{r['symbol']}: {', '.join(r['signals'])}"
    return r.get("symbol", "")


def facts_text(issue: dict) -> str:
    """The model's only input, the hash input, and the validator's reference, all in one."""
    lines = [f"Issue: {issue['label']}", f"Headline: {issue['headline']}", f"Lede: {issue['lede']}"]
    for s in issue["sections"]:
        lines.append(f"\n[{s['id']}] {s['title']}: {s['summary']}")
        lines += [f"- {_row_line(s['id'], r)}" for r in s["rows"]]
    return "\n".join(lines)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER.findall(text)}


def _check(value, reference: str, limit: int) -> Optional[str]:
    """The field as given when it passes every check, else None."""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        return None
    if MARKUP.search(value) or BANNED.search(value):
        return None
    if not _numbers(value) <= _numbers(reference):
        return None
    if not set(CAPS.findall(value)) <= set(CAPS.findall(reference)) | ALLOWED_CAPS:
        return None
    return value.strip()


def _ask(post: Callable, key: str, cfg: dict, text: str) -> Optional[dict]:
    body = {
        "model": cfg["ai_model"],
        "max_tokens": cfg["ai_max_tokens"],
        "system": SYSTEM,
        "messages": [{"role": "user", "content": text}],
        "tools": [TOOL],
        "tool_choice": {"type": "tool", "name": TOOL["name"]},
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    try:
        resp = post(API_URL, headers=headers, json=body, timeout=60)
        data = resp.json() if "json" in resp.headers.get("content-type", "") else {}
        if resp.status_code != 200:
            print(f"WARNING: AI notes skipped: HTTP {resp.status_code} {(data.get('error') or {}).get('type', '')}".rstrip())
            return None
        block = next((b for b in data.get("content", []) if b.get("type") == "tool_use"), None)
        return block["input"] if block and isinstance(block.get("input"), dict) else None
    except (requests.RequestException, ValueError) as e:
        print(f"WARNING: AI notes skipped: {type(e).__name__}")  # the type only: never the request
        return None


def ai_notes(issue: dict, cfg: dict, stored: Optional[dict], post: Callable = _HTTP.post) -> Optional[dict]:
    """The issue's `ai` field. Reuses `stored` when the facts, model and prompt version have not
    changed; None when there is no key, the call fails, or no field passes the checks."""
    text = facts_text(issue)
    digest = hashlib.sha256(f"{PROMPT_VERSION}\n{cfg['ai_model']}\n{text}".encode()).hexdigest()
    if stored and stored.get("factsHash") == digest:
        return stored
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("AI notes: ANTHROPIC_API_KEY is not set; template text only.")
        return None
    answer = _ask(post, key, cfg, text)
    if answer is None:
        return None

    ids = {s["id"] for s in issue["sections"]}
    notes = answer["notes"] if isinstance(answer.get("notes"), dict) else {}
    checked = {k: _check(v, text, MAX_CHARS["note"]) for k, v in notes.items() if k in ids}
    ai = {
        "model": cfg["ai_model"],
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "factsHash": digest,
        "headline": _check(answer.get("headline"), text, MAX_CHARS["headline"]),
        "lede": _check(answer.get("lede"), text, MAX_CHARS["lede"]),
        "notes": {k: v for k, v in checked.items() if v},
    }
    kept = len(ai["notes"]) + bool(ai["headline"]) + bool(ai["lede"])
    print(f"AI notes: {kept} of {len(notes) + 2} fields passed the checks")
    return ai if kept else None
