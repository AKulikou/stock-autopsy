"""
Pure grading and summary functions of the eval, free of API calls so they are
unit-tested (tests/test_eval_grading.py).

Verdict "sides" and order are a convention for measuring instability, not a
claim that the scale is ordinal: RED_FLAGGED and WEAK_CASE are the negative
side, CONDITIONAL_CASE and STRONG_CASE the positive side, INSUFFICIENT_DATA
the middle.
"""

import math
from collections import Counter
from itertools import combinations

from evaluators.paths import resolve_basis
from reporting.number_check import matches, numbers_in, quantities

VERDICTS = ("RED_FLAGGED", "WEAK_CASE", "INSUFFICIENT_DATA", "CONDITIONAL_CASE", "STRONG_CASE")
VERDICT_ORDER = {v: i for i, v in enumerate(VERDICTS)}
SIDE = {
    "RED_FLAGGED": "negative",
    "WEAK_CASE": "negative",
    "INSUFFICIENT_DATA": "middle",
    "CONDITIONAL_CASE": "positive",
    "STRONG_CASE": "positive",
}

# Cost of answering `answer` when the case's primary verdict is `truth`: the matrix of
# Startup Autopsy with its verdicts mapped one to one (NOT_VIABLE -> RED_FLAGGED,
# RISKY -> WEAK_CASE, NEEDS_VALIDATION -> INSUFFICIENT_DATA, VIABLE_IF ->
# CONDITIONAL_CASE, VIABLE -> STRONG_CASE). Asymmetric on purpose: missing severe red
# flags (a positive answer when the truth is RED_FLAGGED) costs far more than erring on
# the cautious side. A convention to revisit, not a measured loss.
ERROR_COST = {
    "RED_FLAGGED": {
        "RED_FLAGGED": 0,
        "WEAK_CASE": 2,
        "INSUFFICIENT_DATA": 2,
        "CONDITIONAL_CASE": 5,
        "STRONG_CASE": 5,
    },
    "WEAK_CASE": {
        "RED_FLAGGED": 1,
        "WEAK_CASE": 0,
        "INSUFFICIENT_DATA": 1,
        "CONDITIONAL_CASE": 2,
        "STRONG_CASE": 3,
    },
    "INSUFFICIENT_DATA": {
        "RED_FLAGGED": 2,
        "WEAK_CASE": 1,
        "INSUFFICIENT_DATA": 0,
        "CONDITIONAL_CASE": 1,
        "STRONG_CASE": 2,
    },
    "CONDITIONAL_CASE": {
        "RED_FLAGGED": 3,
        "WEAK_CASE": 1,
        "INSUFFICIENT_DATA": 1,
        "CONDITIONAL_CASE": 0,
        "STRONG_CASE": 1,
    },
    "STRONG_CASE": {
        "RED_FLAGGED": 4,
        "WEAK_CASE": 2,
        "INSUFFICIENT_DATA": 1,
        "CONDITIONAL_CASE": 1,
        "STRONG_CASE": 0,
    },
}


def labelled(case: dict) -> bool:
    return bool(case.get("primary"))


def allowed_verdicts(case: dict) -> list[str]:
    """The primary verdict plus its acceptable neighbours."""
    return [case["primary"], *case.get("acceptable", [])] if labelled(case) else []


def grade_verdict(verdict: str, case: dict) -> dict:
    """
    primary_hit: the committee gave the case's primary verdict (the headline metric)
    in_range: the primary verdict or an acceptable neighbour
    error_cost: ERROR_COST of this verdict against the primary one (lower is better)
    """
    if not labelled(case):
        return {}
    return {
        "primary_hit": int(verdict == case["primary"]),
        "in_range": int(verdict in allowed_verdicts(case)),
        "error_cost": ERROR_COST[case["primary"]][verdict],
    }


def grade_forensic(forensic: dict | None, case: dict) -> dict:
    """forensic_ok: the Forensic verdict is not one the case forbids (checked by code, not the judge)."""
    forbidden = case.get("forensic_not", [])
    if not forbidden or not forensic or forensic.get("status") != "success":
        return {}
    return {"forensic_ok": int(forensic["verdict"] not in forbidden)}


# --- numbers -------------------------------------------------------------------------


MAX_CITED_FOR_PAIRS = 40  # pairs of cited values tried for a number computed in the sentence


def computed_from(values: list[float]) -> list[float]:
    """
    What a sentence may compute from two cited values: a difference, a ratio, a change
    (a / b - 1), and a difference of two ratios in percentage points.
    """
    results = []
    for a in values[:MAX_CITED_FOR_PAIRS]:
        for b in values[:MAX_CITED_FOR_PAIRS]:
            if a is b:
                continue
            results += [a - b, (a - b) * 100]
            if b:
                results += [a / b, a / b - 1]
    return results


def invented_numbers(number_check: dict, roots: dict) -> list[dict]:
    """
    Numbers in DATA claims found nowhere: not in the pack or the valuation math, and
    not computed in the sentence from the values the claim cites (a change of 38%
    between two cited figures is arithmetic, wrongly tagged DATA, not an invention).
    A correct number under a wrong path is a bad_path, not an invention.
    """
    everywhere = numbers_in(roots)
    invented = []
    for item in number_check.get("checked", []):
        if item["status"] not in ("mismatch", "partial", "bad_path"):
            continue
        cited_values, _ = resolve_basis(roots, item["basis"])
        derivable = computed_from(numbers_in(cited_values))
        for candidates, half_unit in quantities(item["statement"]):
            if any(matches(value, candidates, half_unit) for value in everywhere):
                continue
            if any(matches(value, candidates, half_unit) for value in derivable):
                continue
            invented.append(
                {"evaluator": item["evaluator"], "statement": item["statement"], "number": candidates[0]}
            )
    return invented


def number_summary(number_check: dict, invented: list[dict]) -> dict:
    counts = number_check.get("counts", {})
    return {
        "data_claims": number_check.get("data_claims", 0),
        "matched": counts.get("match", 0),
        "partial": counts.get("partial", 0),
        "mismatch": counts.get("mismatch", 0),
        "bad_path": counts.get("bad_path", 0),
        "no_number": counts.get("no_number", 0),
        "invented": len(invented),
    }


# --- confidence intervals and baselines ---------------------------------------------------


def wilson(passes: int, n: int) -> tuple[float, float]:
    """95% Wilson score interval for a pass rate."""
    if n == 0:
        return 0.0, 0.0
    z, p = 1.96, passes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def labelled_baselines(primaries: list[str], expected: list[list[str]]) -> dict:
    """
    What trivial answerers would score on the same attempts: always one verdict, and a
    uniformly random verdict (expected values). A metric that does not clearly beat
    these measures little.
    """
    n = len(primaries)
    if not n:
        return {"n": 0, "always": {}, "random": {}}
    always = {
        v: {
            "primary_hits": sum(p == v for p in primaries),
            "in_range": sum(v in e for e in expected),
            "mean_cost": sum(ERROR_COST[p][v] for p in primaries) / n,
        }
        for v in VERDICTS
    }
    random = {
        "primary_hits": n / len(VERDICTS),
        "in_range": sum(len(set(e)) / len(VERDICTS) for e in expected),
        "mean_cost": sum(sum(ERROR_COST[p].values()) / len(VERDICTS) for p in primaries) / n,
    }
    return {"n": n, "always": always, "random": random}


# --- stability across reps ------------------------------------------------------------


def by_case(rows: list[dict]) -> dict[str, list[dict]]:
    cases: dict[str, list[dict]] = {}
    for row in rows:
        cases.setdefault(row["case_id"], []).append(row)
    return cases


def stability(rows: list[dict], key: str = "verdict") -> dict:
    """
    How much a verdict (`key` in each row's meta) moves between reps of the same case.
    Only cases with at least two reps count.

    modal_agreement: share of attempts that gave their case's most common verdict
    changed_cases: cases with more than one distinct verdict
    pairwise_disagreement: share of pairs of reps with different verdicts, averaged over cases
    """
    cases = {k: v for k, v in by_case(rows).items() if len(v) > 1}
    attempts = modal = 0
    changed, cross_side, disagreements = [], [], []
    for case_id, case_rows in sorted(cases.items()):
        verdicts = [r["meta"][key] for r in case_rows]
        counts = Counter(verdicts)
        attempts += len(verdicts)
        modal += counts.most_common(1)[0][1]
        if len(counts) > 1:
            changed.append(case_id)
        if key == "verdict" and {"negative", "positive"} <= {SIDE.get(v) for v in verdicts}:
            cross_side.append(case_id)
        pairs = list(combinations(verdicts, 2))
        disagreements.append(sum(a != b for a, b in pairs) / len(pairs))
    return {
        "cases": len(cases),
        "attempts": attempts,
        "modal_agreement": modal / attempts if attempts else 0.0,
        "changed_cases": changed,
        "cross_side_cases": cross_side,
        "pairwise_disagreement": sum(disagreements) / len(disagreements) if disagreements else 0.0,
    }
