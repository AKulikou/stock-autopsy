"""
The number check: every number in a DATA claim must match the pack value at the
claim's basis path. This is how a run proves its figures came from the pack
and not from the model's memory.

A number matches when it equals the value within what its displayed precision
allows ("$47.9 billion" covers 47.85-47.95 billion) or within 1%, whichever is
wider. Signs are ignored: "a loss of $1.3 billion" quotes -1.3 billion. A
percentage also matches the decimal ratio (28.8% = 0.288). Years, form names,
item numbers and dates are not quantities and are skipped.
"""

import re

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
NOT_QUANTITIES = re.compile(
    r"\b(?:NT\s+)?(?:10-K|10-Q|8-K|10-KT|20-F|S-1|S-4|DEF\s*14A)(?:/A)?s?\b"  # form names, 8-Ks
    r"|\bItem\s+\d+(?:\.\d+)?"  # 8-K items
    r"|\b\d{4}-\d{2}-\d{2}\b"  # ISO dates
    r"|\b(?:FY|Q)\d{1,4}(?:Q\d)?\b"  # FY2025, Q2, FY2026Q2
    r"|\b(?:years?|quarters?)\s+\d{1,2}(?:\s*(?:-|to|through)\s*\d{1,2})?\b"  # year 1, years 1-5
    r"|\b\d{1,2}(?:-|\s+)(?:years?|quarters?|months?|weeks?)\b",  # over 3 years, 5-year, 2 quarters
    re.IGNORECASE,
)
NUMBER = re.compile(
    r"(?<![\w.])-?\$?-?(\d[\d,]*(?:\.\d+)?)\s*"
    r"(%|percent\b|trillion\b|tn\b|billion\b|bn\b|b\b|million\b|mn\b|m\b|thousand\b|k\b|x\b|times\b)?",
    re.IGNORECASE,
)


def quantities(statement: str) -> list[tuple[list[float], float]]:
    """(candidate values, half a unit of the last displayed digit) for each quantity in the text."""
    text = NOT_QUANTITIES.sub(" ", statement)
    found = []
    for match in NUMBER.finditer(text):
        digits, unit = match.group(1), (match.group(2) or "").lower()
        number = float(digits.replace(",", ""))
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        is_year = not unit and "$" not in match.group(0) and decimals == 0 and 1900 <= number <= 2100
        if is_year:
            continue
        half_unit = 0.5 * 10**-decimals
        if unit in ("%", "percent"):
            found.append(([number / 100, number], half_unit / 100))
        elif unit in SCALES:
            found.append(([number * SCALES[unit]], half_unit * SCALES[unit]))
        else:
            found.append(([number], half_unit))
    return found


def matches(target: float, candidates: list[float], half_unit: float) -> bool:
    goal = abs(target)
    tolerance = max(RELATIVE_TOLERANCE * goal, half_unit)
    return any(abs(abs(c) - goal) <= tolerance for c in candidates)


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
    match: every number in the statement is one of the cited values; partial: some
    are; mismatch: none are; no_number: nothing to check; bad_path: no cited path exists.
    """
    outcome = {"statement": claim["statement"], "basis": claim["basis"]}
    values, bad = resolve_basis(pack, claim["basis"])
    if bad:
        outcome["bad_paths"] = bad
    if not values:
        return {**outcome, "status": "bad_path"}
    cited = numbers_in(values)
    found = quantities(claim["statement"])
    if not found:
        return {**outcome, "status": "no_number"}
    unmatched = [
        candidates[0]
        for candidates, half_unit in found
        if not any(matches(value, candidates, half_unit) for value in cited)
    ]
    if not unmatched:
        return {**outcome, "status": "match"}
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
