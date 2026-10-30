"""Programmatic grounding checks for a drafted answer (no LLM needed, fully testable).

1. Every number in the answer must appear in the evidence (allowing rounding and ₹/quintal <-> ₹/kg).
2. Every [S#] citation must refer to real evidence, and sentences stating numbers must carry one.
"""
from __future__ import annotations

import json
import re
import unicodedata

from .prompts import KCC

CITE = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
NUM = re.compile(r"\d+(?:\.\d+)?")
FREE_SMALL = 10  # small counts like "2-3 days", "1 spray" are allowed without evidence


def ascii_digits(text: str) -> str:
    """Convert Devanagari/Bengali/Gurmukhi/Tamil/… digits to 0-9 and drop thousands separators."""
    out = "".join(str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch for ch in text)
    return re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", out)


def numbers_in(text: str) -> list[float]:
    t = ascii_digits(text)
    t = CITE.sub(" ", t).replace(KCC, " ")
    return [float(x) for x in NUM.findall(t)]


def evidence_numbers(pack: list[dict], extra_text: str = "") -> set[float]:
    blob = json.dumps([p.get("content") for p in pack], ensure_ascii=False, default=str) + " " + extra_text
    nums = set(numbers_in(blob))
    # dates like 2026-11-02 also allow "2" and "11"; NUM already splits on '-', so they're included.
    return nums


def _rounds_to(n: float, e: float) -> bool:
    """True if n is e, or e honestly rounded (4652 -> 4650 or 4700; 30.3 -> 30). No percentage slack:
    a % tolerance let '2020' pass for '2026' and '4460' for '4400'."""
    if abs(n - e) <= 0.51:
        return True
    if n != int(n) or 1900 <= n <= 2100:  # decimals must match to ±0.5; years must match exactly
        return False
    for unit in (1000, 100, 50, 10):
        if n % unit == 0 and abs(n - e) <= unit / 2 and e >= unit:
            return True
    return False


def _supported(n: float, ev: set[float]) -> bool:
    if n <= FREE_SMALL:
        return True
    return any(_rounds_to(n, cand) for e in ev for cand in (e, e / 100, e * 100))  # ₹/quintal <-> ₹/kg


def check(answer: str, pack: list[dict], question: str = "") -> list[str]:
    """Return a list of problems (empty list = passed)."""
    problems: list[str] = []
    ids = {p["id"] for p in pack}
    ev = evidence_numbers(pack, question)

    bad = [n for n in numbers_in(answer) if not _supported(n, ev)]
    if bad:
        problems.append("These numbers are not in the evidence: " + ", ".join(f"{b:g}" for b in sorted(set(bad))))

    cited = {c.strip() for grp in CITE.findall(answer) for c in grp.split(",")}
    unknown = cited - ids
    if unknown:
        problems.append("Citations that do not exist: " + ", ".join(sorted(unknown)))
    if pack and not cited:
        problems.append("The answer has no [S#] citations.")

    for sent in re.split(r"(?<=[.!?।])\s+", answer):
        if any(n > FREE_SMALL for n in numbers_in(sent)) and not CITE.search(sent) and KCC not in sent:
            problems.append(f"Sentence states a number without a citation: “{sent.strip()[:80]}”")
    return problems
