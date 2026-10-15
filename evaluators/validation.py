"""
Validators: a schema-valid answer can still be unusable. Each returns a list of
problems; request_structured retries once with any problem, then reports the
call as failed instead of letting the answer reach a report.

The claim check is the first line against invented numbers: a DATA claim must
name pack paths that exist. A few bad paths do not reject an answer (the number
check reports them); many mean the evaluator ignored the rules, and it retries.
"""

from collections.abc import Callable

from evaluators.paths import resolve_basis
from evaluators.schemas import (
    BusinessModelResult,
    Claim,
    ForensicResult,
    PreMortemResult,
    ScenarioAssumptions,
    ValuationAssumptions,
    ValuationResult,
    VerdictBlock,
)

MIN_CLAIMS, MAX_CLAIMS = 3, 40
# Share of DATA claims with a basis that names no existing pack path, above which
# the answer is rejected.
MAX_BAD_BASIS_SHARE = 0.25


def text_problems(name: str, text: str, min_chars: int, max_chars: int) -> list[str]:
    length = len(text.strip())
    if length < min_chars:
        return [f"{name} too short ({text.strip()!r})"]
    if length > max_chars:
        return [f"{name} too long ({length} chars, starts {text.strip()[:60]!r})"]
    return []


def count_problems(name: str, items: list, low: int, high: int) -> list[str]:
    if not low <= len(items) <= high:
        return [f"{name} needs {low}-{high} items, got {len(items)}"]
    return []


def verdict_problems(result: VerdictBlock) -> list[str]:
    return (
        text_problems("confidence_reason", result.confidence_reason, 10, 400)
        + text_problems("key_finding", result.key_finding, 15, 400)
        + text_problems("biggest_unknown", result.biggest_unknown, 15, 400)
        + text_problems("summary", result.summary, 40, 1500)
    )


def claim_problems(claims: list[Claim], pack: dict) -> list[str]:
    problems = count_problems("claims", claims, MIN_CLAIMS, MAX_CLAIMS)
    data_claims = 0
    bad: list[str] = []
    for n, claim in enumerate(claims, start=1):
        problems += text_problems(f"claim {n} statement", claim.statement, 10, 600)
        if not claim.basis.strip():
            problems.append(f"claim {n} has no basis")
        elif claim.tag == "DATA":
            data_claims += 1
            _, unknown = resolve_basis(pack, claim.basis)
            if unknown:
                bad.append(f"claim {n} ({', '.join(unknown)})")
    if data_claims and len(bad) / data_claims > MAX_BAD_BASIS_SHARE:
        problems.append(
            f"{len(bad)} of {data_claims} DATA claims name no existing pack path: {'; '.join(bad)}. "
            "A DATA basis lists only pack paths separated by '; ', e.g. "
            "'financials_annual.FY2025.revenue; derived.annual.FY2025.gross_margin'"
        )
    return problems


def business_model_validator(pack: dict) -> Callable[[BusinessModelResult], list[str]]:
    def validate(result: BusinessModelResult) -> list[str]:
        return (
            verdict_problems(result)
            + text_problems("business_summary", result.business_summary, 40, 2000)
            + text_problems("unit_economics", result.unit_economics, 30, 2000)
            + count_problems("key_dependencies", result.key_dependencies, 2, 4)
            + claim_problems(result.claims, pack)
        )

    return validate


def forensic_validator(pack: dict) -> Callable[[ForensicResult], list[str]]:
    def validate(result: ForensicResult) -> list[str]:
        problems = verdict_problems(result) + claim_problems(result.claims, pack)
        problems += text_problems("red_flag_score_reason", result.red_flag_score_reason, 20, 1500)
        if not 1 <= result.red_flag_score <= 10:
            problems.append(f"red_flag_score must be 1-10, got {result.red_flag_score}")
        for n, flag in enumerate(result.red_flags, start=1):
            if not 1 <= flag.severity <= 5:
                problems.append(f"red flag {n} severity must be 1-5, got {flag.severity}")
            problems += text_problems(
                f"red flag {n} innocent_explanation", flag.innocent_explanation, 10, 1000
            )
            problems += text_problems(f"red flag {n} evidence", flag.evidence, 10, 1500)
        severe = any(flag.severity == 5 for flag in result.red_flags)
        if severe and result.verdict != "RED_FLAG":
            problems.append("a severity-5 flag requires the verdict RED_FLAG")
        if result.verdict == "RED_FLAG" and not severe:
            problems.append("verdict RED_FLAG requires at least one severity-5 flag")
        return problems

    return validate


def scenario_problems(name: str, s: ScenarioAssumptions) -> list[str]:
    problems = []
    for field in ("revenue_growth", "operating_margin"):
        values = getattr(s, field)
        if len(values) != 5:
            problems.append(f"{name}.{field} needs 5 values, got {len(values)}")
    checks = [
        ("revenue_growth", all(-0.5 <= g <= 1.0 for g in s.revenue_growth), "each between -0.5 and 1.0"),
        ("operating_margin", all(-1.0 <= m <= 0.8 for m in s.operating_margin), "each between -1.0 and 0.8"),
        ("tax_rate", 0 <= s.tax_rate <= 0.4, "between 0 and 0.4"),
        ("capex_pct_revenue", 0 <= s.capex_pct_revenue <= 0.5, "between 0 and 0.5"),
        ("da_pct_revenue", 0 <= s.da_pct_revenue <= 0.5, "between 0 and 0.5"),
        ("nwc_pct_revenue_change", -0.5 <= s.nwc_pct_revenue_change <= 0.5, "between -0.5 and 0.5"),
        ("discount_rate", 0.04 <= s.discount_rate <= 0.20, "between 0.04 and 0.20"),
        ("terminal_growth", -0.02 <= s.terminal_growth <= 0.04, "between -0.02 and 0.04"),
    ]
    problems += [
        f"{name}.{field} must be {rule} (decimals, 0.05 = 5%)" for field, ok, rule in checks if not ok
    ]
    if s.terminal_growth >= s.discount_rate - 0.01:
        problems.append(f"{name}: terminal_growth must be at least 1 point below discount_rate")
    return problems


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def valuation_assumptions_validator(pack: dict) -> Callable[[ValuationAssumptions], list[str]]:
    def validate(result: ValuationAssumptions) -> list[str]:
        problems = []
        for name in ("bear", "base", "bull"):
            problems += scenario_problems(name, getattr(result, name))
        for field in ("revenue_growth", "operating_margin"):
            bear, base, bull = (_mean(getattr(getattr(result, n), field)) for n in ("bear", "base", "bull"))
            if not bear <= base <= bull:
                problems.append(f"average {field} must satisfy bear <= base <= bull")
        problems += count_problems("notes", result.notes, 3, 20)
        problems += claim_problems(result.claims, pack)
        return problems

    return validate


def valuation_validator(pack: dict) -> Callable[[ValuationResult], list[str]]:
    def validate(result: ValuationResult) -> list[str]:
        return (
            verdict_problems(result)
            + text_problems("relative_valuation", result.relative_valuation, 30, 2000)
            + text_problems("implied_expectations", result.implied_expectations, 30, 2000)
            + text_problems("achievability", result.achievability, 20, 2000)
            + claim_problems(result.claims, pack)
        )

    return validate


def pre_mortem_validator(pack: dict) -> Callable[[PreMortemResult], list[str]]:
    def validate(result: PreMortemResult) -> list[str]:
        problems = verdict_problems(result) + claim_problems(result.claims, pack)
        problems += count_problems("failure_scenarios", result.failure_scenarios, 3, 3)
        problems += count_problems("invalidation_criteria", result.invalidation_criteria, 3, 5)
        problems += count_problems("verification_checklist", result.verification_checklist, 3, 12)
        for n, s in enumerate(result.failure_scenarios, start=1):
            problems += text_problems(f"failure scenario {n} causal_chain", s.causal_chain, 40, 2000)
        return problems

    return validate
