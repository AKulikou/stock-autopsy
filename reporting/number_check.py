"""
The number check: every number in a DATA claim must match the pack value at the
claim's basis path. This is how a run proves its figures came from the pack
and not from the model's memory.

A number matches when it equals the value within what its displayed precision
allows ("$47.9 billion" covers 47.85-47.95 billion) or within 1%, whichever is
wider. A percentage also matches the decimal ratio (28.8% = 0.288). Years, form
names, item numbers and dates are not quantities and are skipped.

Signs count only where the wording states a direction: "a loss of $1.3 billion"
must match a negative value and "a profit of" a positive one, "fell 5%" a
negative change and "grew 5%" a positive one; an explicit minus sign counts
too. Without such wording the sign is ignored ("net income of $1.3 billion" is
read as a size).

A basis that names a whole table or block (financials_annual, data_quality.restated)
lets a number match any of hundreds of values by coincidence, so a claim whose
numbers match only inside such a group gets the weaker status group_match.
"""

import re
from typing import NamedTuple

from evaluators.paths import resolve_basis

RELATIVE_TOLERANCE = 0.01
SCALES = {
    "trillion": 1e12,
    "tn": 1e12,
    "billion": 1e9,
    "bn": 1e9,
    "b": 1e9,
    "million": 1e6,
    "mn": 1e6,
    "m": 1e6,
    "thousand": 1e3,
    "k": 1e3,
}
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
NOT_QUANTITIES = re.compile(
    r"\b(?:NT\s+)?(?:10-K|10-Q|8-K|10-KT|20-F|S-1|S-4|DEF\s*14A)(?:/A)?s?\b"  # form names, 8-Ks
    r"|\bItem\s+\d+(?:\.\d+)?"  # 8-K items
    r"|\b\d{4}-\d{2}-\d{2}\b"  # ISO dates
    rf"|\b{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b"  # June 30
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}\b"  # 30 June
    r"|\bSIC\s+(?:code\s+)?\d{3,4}\b"  # industry codes
    r"|\b(?:FY|Q)\d{1,4}(?:Q\d)?\b"  # FY2025, Q2, FY2026Q2
    r"|\b(?:years?|quarters?)(?:\s+|-)\d{1,2}(?:\s*(?:-|to|through)\s*\d{1,2})?\b"  # year-1, years 1-5
    r"|\b\d{1,2}(?:-|\s+)(?:years?|quarters?|months?|weeks?)\b",  # over 3 years, 5-year, 2 quarters
    re.IGNORECASE,
)
NUMBER = re.compile(
    r"(?<![\w.])-?\$?-?(\d[\d,]*(?:\.\d+)?)\s*"
    r"(%|percent\b|trillion\b|tn\b|billion\b|bn\b|b\b|million\b|mn\b|m\b|thousand\b|k\b|x\b|times\b)?",
    re.IGNORECASE,
)

# Wording right before a number that states its direction. Hedges such as "about"
# may sit between the cue and the number; "fell to" states a level, not a change.
_HEDGE = r"(?:\s+(?:about|approximately|roughly|around|nearly|almost|over|some|just|only|another|a))*"
_NEGATIVE = re.compile(
    r"(?:\b(\w+)[\s-]+)?\b(?:loss(?:es)?\s+(?:of|was|were|at|totaled|totalling|totaling|reached)"
    r"|lost|negative|minus"
    r"|(?:fell|declined|decreased|dropped|shrank|contracted|down)(?:\s+by)?)" + _HEDGE + r"\s*\$?$",
    re.IGNORECASE,
)
_POSITIVE = re.compile(
    r"\b(?:(?:profits?|earnings|income|surplus)\s+(?:of|was|were|at|totaled|totalling|totaling|reached)"
    r"|(?:grew|rose|increased|climbed|gained|expanded|up)(?:\s+by)?)" + _HEDGE + r"\s*\$?$",
    re.IGNORECASE,
)
# A loss of one of these is a positive amount in the pack (an impairment is stored as a
# charge), so "an impairment loss of $1 billion" states no sign.
_UNSIGNED_LOSSES = {
    "impairment", "down", "writedown", "exchange", "currency", "actuarial", "hedging", "credit",
}
_CLAUSE_END = re.compile(r"[;:()]|\.\s|,\s")
_DIRECTION_WINDOW = 60


class Quantity(NamedTuple):
    candidates: list[float]  # the values the text can mean (a percentage: ratio and number)
    half_unit: float         # half a unit of the last displayed digit
    sign: int | None         # +1 / -1 when the wording states a direction, else None
    unit: str = ""           # "%", "billion", "x", ... as written; "" for a bare number
    money: bool = False      # written with a dollar sign
    start: int = 0           # position in the statement

    @property
    def shown(self) -> str:
        """The quantity as the text wrote it: 37%, $1.2 billion, 14.4x."""
        value = self.candidates[-1] if self.unit in ("%", "percent") else self.candidates[0]
        if self.unit in ("%", "percent"):
            return f"{value:g}%"
        suffix = "x" if self.unit in ("x", "times") else ""
        return ("$" if self.money else "") + number_words(value) + suffix

    @property
    def is_count(self) -> bool:
        """A bare small integer: a count ("3 scenarios"), not a figure."""
        whole = self.candidates[0] == int(self.candidates[0])
        return not self.unit and not self.money and whole and abs(self.candidates[0]) <= 12


def number_words(value: float) -> str:
    """A number for a person: 75000000000 -> 75 billion, -447000000 -> -447 million, 0.37 -> 0.37."""
    for scale, word in ((1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
        if abs(value) >= scale:
            return f"{value / scale:,.3g} {word}"
    return f"{value:,.6g}"


def _direction(before: str, matched: str) -> int | None:
    if matched.lstrip("$").startswith("-"):
        return -1
    clause = _CLAUSE_END.split(before[-_DIRECTION_WINDOW:])[-1]
    negative = _NEGATIVE.search(clause)
    if negative and (negative.group(1) or "").lower() not in _UNSIGNED_LOSSES:
        return -1
    if _POSITIVE.search(clause):
        return 1
    return None


def quantities(statement: str) -> list[Quantity]:
    """Each quantity in the text, with what it can mean and the direction its wording states."""
    # Blank out non-quantities with spaces of the same length, so positions stay valid.
    text = NOT_QUANTITIES.sub(lambda m: " " * len(m.group(0)), statement)
    found = []
    for match in NUMBER.finditer(text):
        digits, unit = match.group(1), (match.group(2) or "").lower()
        number = float(digits.replace(",", ""))
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        is_year = not unit and "$" not in match.group(0) and decimals == 0 and 1900 <= number <= 2100
        if is_year:
            continue
        half_unit = 0.5 * 10**-decimals
        sign = _direction(text[: match.start()], match.group(0))
        where = {"unit": unit, "money": "$" in match.group(0), "start": match.start()}
        if unit in ("%", "percent"):
            found.append(Quantity([number / 100, number], half_unit / 100, sign, **where))
        elif unit in SCALES:
            found.append(Quantity([number * SCALES[unit]], half_unit * SCALES[unit], sign, **where))
        else:
            found.append(Quantity([number], half_unit, sign, **where))
    return found


def matches(target: float, candidates: list[float], half_unit: float, sign: int | None = None) -> bool:
    """Size within precision; and, when the wording states a direction, the right sign."""
    if sign is not None and target and (target > 0) != (sign > 0):
        return False
    goal = abs(target)
    tolerance = max(RELATIVE_TOLERANCE * goal, half_unit)
    return any(abs(abs(c) - goal) <= tolerance for c in candidates)


def found_in(quantity: Quantity, values: list[float]) -> bool:
    return any(matches(value, quantity.candidates, quantity.half_unit, quantity.sign) for value in values)


def numbers_in(value, limit: int = 5000) -> list[float]:
    """Every number inside a value (a scalar, or a group of the pack), up to a limit."""
    found: list[float] = []
    stack = [value]
    while stack and len(found) < limit:
        item = stack.pop()
        if isinstance(item, bool) or item is None:
            continue
        if isinstance(item, int | float):
            found.append(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def check_claim(claim: dict, pack: dict) -> dict:
    """
    match: every number in the statement is one of the cited values; group_match: every
    number is in the cited data, but some only inside a cited table or block; partial:
    some are; mismatch: none are; no_number: nothing to check; bad_path: no cited path exists.
    """
    outcome = {"statement": claim["statement"], "basis": claim["basis"]}
    values, bad = resolve_basis(pack, claim["basis"])
    if bad:
        outcome["bad_paths"] = bad
    if not values:
        return {**outcome, "status": "bad_path"}
    leaves = numbers_in([v for v in values if not isinstance(v, dict | list)])
    groups = numbers_in([v for v in values if isinstance(v, dict | list)])
    outcome["cites_group"] = any(isinstance(v, dict | list) for v in values)
    found = quantities(claim["statement"])
    if not found:
        return {**outcome, "status": "no_number"}
    unmatched, in_group = [], False
    for quantity in found:
        if found_in(quantity, leaves):
            continue
        if found_in(quantity, groups):
            in_group = True
            continue
        unmatched.append(quantity.candidates[0] * (quantity.sign or 1))
    if not unmatched:
        return {**outcome, "status": "group_match" if in_group else "match"}
    status = "mismatch" if len(unmatched) == len(found) else "partial"
    return {**outcome, "status": status, "unmatched": unmatched}


def check_results(results: list[dict], pack: dict) -> dict:
    """The number check over every DATA claim of the successful evaluator results."""
    checked = []
    for result in results:
        if result.get("status") != "success":
            continue
        for claim in result.get("claims", []):
            if claim["tag"] == "DATA":
                checked.append({"evaluator": result["key"], **check_claim(claim, pack)})
    counts: dict[str, int] = {}
    for item in checked:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    problems = [item for item in checked if item["status"] in ("mismatch", "partial", "bad_path")]
    return {"data_claims": len(checked), "counts": counts, "problems": problems, "checked": checked}
