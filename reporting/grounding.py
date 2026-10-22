"""
Grounding checks beyond the DATA claims (reporting/number_check.py), so that a
run's numbers can be traced wherever they appear:

- Calculated claims (DERIVED): every number must be reproducible from the values
  the basis cites, directly or by one step of arithmetic (difference, sum, ratio,
  change, product, or a small constant such as "/ 2" written in the basis), or from
  a formula written in the basis: its result or any part of it (a numerator, a
  denominator). A constant the formula uses ("0.5 * pe") is explained when the
  statement states it ("a 50% fall"). A difference of two data terms has no sign of
  its own (a fall may be written old - new), so its size also matches "fell by".
- Numbers in prose: every number in the evaluators' and the committee's text
  must appear in the pack, the valuation math, or one of the run's claims.
  Thresholds and plans the model chose itself (invalidation signals, the
  monitoring plan, conditions, next steps) are not checked: they are proposals,
  not facts.
- Absent read as zero: where the pack says a value is unknown (not reported, not
  found, not collected), text such as "no debt" or "dividends of 0" turns the
  unknown into a fact. Each hit is a sentence for a person to check.

None of these changes what the model answers; they grade it. `check_run()`
bundles them with the DATA number check for the runner, the report and the eval.
"""

import ast
import math
import re
from typing import Any

from evaluators.paths import PathError, resolve
from reporting.number_check import check_results, found_in, numbers_in, quantities

MAX_CITED_FOR_PAIRS = 40  # cited values tried pairwise for one step of arithmetic
MAX_CONSTANT = 100  # a literal in a basis up to this size is an operand ("/ 2", "* 100")

# Fields that hold the model's own proposals or labels, not statements of fact.
NOT_PROSE = {
    "claims", "invalidation_criteria", "monitoring_plan", "conditions", "next_research_steps",
    "verification_checklist", "key", "label", "status", "model", "error", "verdict", "confidence",
    "model_confidence", "confidence_adjustments", "tag", "nature", "stronger_side", "between",
    "from_evaluator", "basis", "anchor", "rejected_answer", "warnings",
}

_PATH_TOKEN = re.compile(r"\b[a-z_][a-z0-9_]*(?:\.[A-Za-z0-9_]+)+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


# --- calculated claims ---------------------------------------------------------------


def computed_from(values: list[float], constants: list[float] = ()) -> list[float]:
    """
    What one step of arithmetic makes of the cited values: a difference, a sum, a
    ratio, a change (a / b - 1), a product, a difference in percentage points, and
    each value times or divided by a small constant from the basis.
    """
    values = values[:MAX_CITED_FOR_PAIRS]
    results = []
    for a in values:
        for c in constants:
            results.append(a * c)
            if c:
                results.append(a / c)
        for b in values:
            if a is b:
                continue
            results += [a - b, a + b, (a - b) * 100, a * b]
            if b:
                results += [a / b, a / b - 1]
    return results


_ARITHMETIC = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Add,
               ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
# A literal next to an arithmetic operator is an operand ("0.5 * pe", "x / 2"); one in
# brackets after a path is the model quoting the value ("pe (29.49)").
_OPERAND = re.compile(
    r"(?:(?<=[*/+\-])|(?<=[*/+\-]\s))(\d+(?:\.\d+)?)(?![\w.])"
    r"|(?<![\w.])(\d+(?:\.\d+)?)(?=\s?[*/+\-])"
)
# Constants of a formula's shape (a / b - 1, x * 100), not amounts a statement would state.
CONVENTION_CONSTANTS = (0, 1, 100)
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Models also multiply with a letter x or a times sign ("pe x 0.5 = 29.36 x 0.5", live run 2026-10-21).
_TIMES = re.compile(r"\s*×\s*|(?<=\S)\s+x\s+(?=\S)")


def _times_as_star(text: str) -> str:
    return _TIMES.sub(" * ", text)


def _formulas(basis: str, roots: dict) -> list[tuple[ast.AST, dict[str, float]]]:
    """
    Each formula written in the basis ("a - (b + c)", "x / y = 5.3 / 8.8") as a parse tree
    whose pack paths are names, with their values. Pure arithmetic only: anything else
    (a word, a group of values, a call) leaves that formula out. Never uses eval().
    """
    formulas = []
    for piece in re.split(r"[=;]", basis):
        text, names, ok = piece, {}, True
        for token in _PATH_TOKEN.findall(piece):
            try:
                value = resolve(roots, token.rstrip("."))
            except PathError:
                ok = False
                break
            if isinstance(value, bool) or not isinstance(value, int | float):
                ok = False
                break
            name = f"__p{len(names)}"
            names[name] = float(value)
            text = text.replace(token, f" {name} ", 1)
        text = _times_as_star(_THOUSANDS.sub("", text).replace("^", "**")).strip()
        if not ok or not text:
            continue
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError:
            continue
        nodes = list(ast.walk(tree))
        if all(isinstance(n, _ARITHMETIC) for n in nodes) and all(
            n.id in names for n in nodes if isinstance(n, ast.Name)
        ):
            formulas.append((tree.body, names))
    return formulas


def _value(node: ast.AST, names: dict[str, float]) -> float | None:
    try:
        result = _evaluate(node, names)
    except (ArithmeticError, ValueError, TypeError):
        return None
    return float(result) if isinstance(result, int | float) and math.isfinite(result) else None


def formula_values(basis: str, roots: dict) -> list[float]:
    """The value of each formula written in the basis, every pack path replaced by its value."""
    return [v for tree, names in _formulas(basis, roots) if (v := _value(tree, names)) is not None]


def _has_data(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Name) for n in ast.walk(node))


def formula_parts(basis: str, roots: dict) -> list[float]:
    """
    Every value inside the basis formulas: each formula and each of its parts (a
    numerator, a denominator, a bracket). A difference of two data terms counts with
    both signs, because its sign is the writer's convention (a fall written old - new);
    a change such as a / b - 1 keeps its sign.
    """
    values = []
    for tree, names in _formulas(basis, roots):
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp | ast.UnaryOp):
                continue
            value = _value(node, names)
            if value is None:
                continue
            values.append(value)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
                if _has_data(node.left) and _has_data(node.right):
                    values.append(-value)
    return values


def operand_constants(basis: str) -> list[float]:
    """Small literals the basis uses as operands ("0.5 * pe"), not values it quotes in brackets."""
    text = _times_as_star(_ISO_DATE.sub(" ", _PATH_TOKEN.sub(" P ", basis)))
    found = []
    for match in _OPERAND.finditer(text):
        number = float(match.group(1) or match.group(2))
        if number <= MAX_CONSTANT and number not in CONVENTION_CONSTANTS:
            found.append(number)
    return found


def _evaluate(node: ast.AST, names: dict[str, float] | None = None) -> float:
    if isinstance(node, ast.Name):
        return (names or {})[node.id]
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise TypeError("not a number")
        return node.value
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate(node.operand, names)
        return -operand if isinstance(node.op, ast.USub) else operand
    left, right = _evaluate(node.left, names), _evaluate(node.right, names)
    if isinstance(node.op, ast.Pow):
        if abs(right) > 50:
            raise ValueError("exponent too large")
        return left**right
    return {ast.Add: left + right, ast.Sub: left - right, ast.Mult: left * right}.get(
        type(node.op), left / right if right else math.nan
    )


def basis_values(basis: str, roots: dict) -> tuple[list[float], list[float]]:
    """(numbers under every pack path the basis mentions, small literal constants in it)."""
    cited: list[float] = []
    for token in _PATH_TOKEN.findall(basis):
        try:
            cited += numbers_in(resolve(roots, token.rstrip(".")))
        except PathError:
            continue
    rest = _PATH_TOKEN.sub(" ", basis)
    constants = [
        q.candidates[-1] for q in quantities(rest) if abs(q.candidates[-1]) <= MAX_CONSTANT
    ]
    return cited, constants


def check_derived_claim(claim: dict, roots: dict) -> dict:
    """
    reproduced: every number follows from the cited values; partial: some do;
    not_reproduced: none do; no_number; no_data_cited: the basis names no pack value.
    """
    outcome = {"statement": claim["statement"], "basis": claim["basis"]}
    cited, constants = basis_values(claim["basis"], roots)
    found = quantities(claim["statement"])
    if not found:
        return {**outcome, "status": "no_number"}
    if not cited:
        return {**outcome, "status": "no_data_cited"}
    reachable = (
        cited
        + formula_parts(claim["basis"], roots)
        + computed_from(cited, constants)
        + operand_constants(claim["basis"])
    )
    unexplained = [q.candidates[0] * (q.sign or 1) for q in found if not found_in(q, reachable)]
    if not unexplained:
        return {**outcome, "status": "reproduced"}
    status = "not_reproduced" if len(unexplained) == len(found) else "partial"
    return {**outcome, "status": status, "unexplained": unexplained}


def check_derived(results: list[dict], roots: dict) -> dict:
    checked = [
        {"evaluator": r["key"], **check_derived_claim(c, roots)}
        for r in results
        if r.get("status") == "success"
        for c in r.get("claims", [])
        if c["tag"] == "DERIVED"
    ]
    counts: dict[str, int] = {}
    for item in checked:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    problems = [c for c in checked if c["status"] in ("not_reproduced", "partial")]
    return {"claims": len(checked), "counts": counts, "problems": problems, "checked": checked}


# --- numbers in prose ----------------------------------------------------------------


def prose_fields(value: Any, path: str = "") -> list[tuple[str, str]]:
    """(location, text) of every free-text field, skipping NOT_PROSE keys."""
    found = []
    if isinstance(value, str):
        found.append((path, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in NOT_PROSE:
                found += prose_fields(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += prose_fields(item, f"{path}.{index}")
    return found


def _sources(results: list[dict], synthesis: dict | None) -> list[tuple[str, dict]]:
    sources = [(r["key"], r) for r in results if r.get("status") == "success"]
    if synthesis and synthesis.get("status") == "success":
        sources.append(("synthesis", synthesis))
    return sources


def _excerpt(text: str, position: int) -> str:
    """The sentence of `text` around `position`, at most 240 characters."""
    start = 0
    for part in _SENTENCE.split(text):
        end = start + len(part)
        if start <= position <= end:
            return part.strip()[:240]
        start = end + 1
    return text[:240]


def prose_numbers(results: list[dict], synthesis: dict | None, roots: dict) -> dict:
    """Numbers in free text found neither in the pack, the valuation math, nor any claim."""
    known = numbers_in(roots)
    for _, source in _sources(results, synthesis):
        # The model's own structured numbers (DCF assumptions, scores), not usage counters.
        known += numbers_in(
            {k: v for k, v in source.items() if not k.endswith("_tokens") and k != "duration_s"}
        )
        for claim in source.get("claims", []):
            known += [q.candidates[-1] for q in quantities(claim["statement"])]
            known += [q.candidates[0] for q in quantities(claim["statement"])]
    checked, unsourced = 0, []
    for name, source in _sources(results, synthesis):
        for location, text in prose_fields(source):
            for q in quantities(text):
                if q.is_count:
                    continue
                checked += 1
                if found_in(q._replace(sign=None), known):
                    continue
                unsourced.append({
                    "source": name,
                    "field": location,
                    "number": q.candidates[0],
                    "shown": q.shown,
                    "text": _excerpt(text, q.start),
                })
    return {"numbers": checked, "unsourced": unsourced}


# --- absent read as zero -------------------------------------------------------------

# Values the filings did not provide. Blocks not fetched at all (peers, news) are left
# out: "the pack has no peer multiples" is a true statement about the pack.
ABSENT_REASONS = ("not_reported", "tag_not_found")
FIELD_NOUNS = {
    "total_debt": r"debt|borrowings?",
    "dividends_paid": r"dividends?",
    "share_repurchases": r"(?:share\s+)?(?:buybacks?|repurchases?)",
    "interest_expense": r"interest\s+expense|interest\s+costs?",
    "accounts_receivable": r"receivables?",
    "short_term_investments": r"short[- ]term\s+investments?",
}
# A sentence about the data itself ("the pack has no debt terms", "sat under another
# tag") states that the value is unknown, which is right. So does one about what cannot be
# computed without it ("enterprise value cannot be built without debt", "no equity bridge"):
# seven of the nine hits of v4_release (2026-10-22) were such sentences.
_ABOUT_THE_DATA = re.compile(
    r"\b(?:pack|fetched|not\s+reported|unreported|tags?|xbrl|unknown|missing|not\s+in\s+the\s+data"
    r"|null|partial|(?:is|are|was|were)\s+reported|figures?|bridge|cannot|could\s+not|nobody\s+can"
    r"|(?:do|does|did)\s+not\s+(?:yet\s+)?know|how\s+much)\b",
    re.IGNORECASE,
)
_PERIOD = re.compile(r"\b(?:FY\d{4}(?:Q[1-4])?|TTM)\b", re.IGNORECASE)
_NO = (
    r"\b(?:no|zero|nil|without(?:\s+any)?|(?:did|does|do)\s+not\s+(?:have|carry|pay|report|make)(?:\s+any)?"
    r"|(?:had|has|have|carried|carries|carry|paid|pays|pay|reported|reports|made|makes)\s+(?:no|zero)"
    r"|free\s+of)"
)
_NOT_AN_AMOUNT = r"(?!\s+(?:cuts?|increases?|growth|changes?|policy|policies|covenants?|ratings?|maturit))"


def _absent_patterns(noun: str) -> re.Pattern:
    return re.compile(
        rf"{_NO}\s+(?:(?!in\b|of\b|to\b|for\b|on\b)[\w-]+\s+){{0,2}}?(?:{noun})\b{_NOT_AN_AMOUNT}"
        rf"|\b(?:{noun})\s+(?:of|was|were|is|are|at|stood\s+at|totaled|totalled|equal(?:ed|s)?(?:\s+to)?)"
        rf"\s+(?:\$\s*)?(?:0(?:\.0+)?|zero|nil|none)\b(?![.,]?\d)"
        rf"|\b(?:{noun})-free\b",
        re.IGNORECASE,
    )


def absent_as_zero(results: list[dict], synthesis: dict | None, pack: dict) -> list[dict]:
    """
    Sentences that state a value is zero or none where the pack says it is unknown.
    A sentence that names periods is flagged only if one of them is unknown ("debt was
    0 in FY2024" is right when FY2024 reports 0); one without periods always is.
    """
    absent: dict[str, dict] = {}
    for entry in pack.get("data_quality", {}).get("missing", []):
        if entry["reason"] not in ABSENT_REASONS:
            continue
        noun = FIELD_NOUNS.get(entry["field"], re.escape(entry["field"].replace("_", " ")))
        item = absent.setdefault(
            entry["field"], {"pattern": _absent_patterns(noun), "periods": set(), "unknown": []}
        )
        item["periods"].update(p.upper() for p in entry["periods"])
        item["unknown"].append({"periods": entry["periods"], "reason": entry["reason"]})
    hits = []
    for name, source in _sources(results, synthesis):
        texts = prose_fields(source) + [
            (f"claims.{i}.statement", c["statement"]) for i, c in enumerate(source.get("claims", []))
        ]
        for location, text in texts:
            for sentence in _SENTENCE.split(text):
                if _ABOUT_THE_DATA.search(sentence):
                    continue
                named = {p.upper() for p in _PERIOD.findall(sentence)}
                for field, item in absent.items():
                    if not item["pattern"].search(sentence):
                        continue
                    if named and not named & item["periods"]:
                        continue
                    hits.append({
                        "source": name,
                        "field": location,
                        "missing_field": field,
                        "unknown": item["unknown"],
                        "text": sentence.strip()[:240],
                    })
    return hits


# --- everything ----------------------------------------------------------------------


def check_run(results: list[dict], synthesis: dict | None, roots: dict) -> dict:
    """The DATA number check plus the checks above; `roots` is the pack with valuation_math."""
    return {
        **check_results(results, roots),
        "derived": check_derived(results, roots),
        "prose": prose_numbers(results, synthesis, roots),
        "absent_as_zero": absent_as_zero(results, synthesis, roots),
    }
