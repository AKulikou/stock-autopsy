"""
The synthesis (Investment Committee): reads the evaluator results, the valuation
math and a summary of the pack, and decides. It looks for productive conflicts,
never averages verdicts, and adds no facts.

Code, not the model, applies two confidence rules after the call: a high share
of UNVERIFIED claims lowers the confidence one level (source of truth, usage
notes), and so does a missing evaluator.
"""

import json
from typing import Literal

from pydantic import BaseModel, Field

from evaluators.schemas import Confidence
from evaluators.validation import count_problems, text_problems

FinalVerdict = Literal["STRONG_CASE", "CONDITIONAL_CASE", "INSUFFICIENT_DATA", "WEAK_CASE", "RED_FLAGGED"]
CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")
UNVERIFIED_SHARE_LIMIT = 0.30
# Keys of evaluator results that are bookkeeping, not analysis.
BOOKKEEPING = {
    "label",
    "model",
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "web_searches",
    "duration_s",
}

SYNTHESIS_PRINCIPLES = """\
You chair an investment committee. You receive independent analyst reports on one US public
company, the valuation math Python computed, and a summary of the DATA PACK. You add no new
facts: reason only over what the reports and the pack summary say. Facts from memory are not
allowed.

1. Committee debate. The strongest bull case and the strongest bear case, each built only from
   evidence in the reports. Each side answers the other's best point.
2. Conflict map. Where analysts disagree, say whether the conflict is real or the result of
   different angles. Never average verdicts. Look for these productive conflicts: a strong
   business with a weak valuation ("great company, priced for perfection"); good numbers with a
   forensic red flag ("numbers look good, quality questionable"); a good business with a
   high-risk pre-mortem.
3. Judge's summary. Which side has the stronger evidence and why; what remains genuinely
   uncertain; which findings rest on ASSUMPTION or UNVERIFIED claims.
4. Final research verdict, not a trade recommendation:
   STRONG_CASE - quality, price and risks all support further interest
   CONDITIONAL_CASE - attractive IF specific conditions hold (list them)
   INSUFFICIENT_DATA - key questions cannot be answered with the available data
   WEAK_CASE - the evidence does not support the investment thesis
   RED_FLAGGED - unresolved severe red flags dominate everything else
   Confidence LOW, MEDIUM or HIGH, with one sentence why.
5. Monitoring plan. Three to five metrics or events to watch, with thresholds, taken from the
   analysts' invalidation criteria and findings.
6. Next research steps. Exactly three specific things to verify next, ordered by how much they
   could change the verdict.
7. Beginner explanation. Plain language: what the company does, why it may or may not be
   interesting, and what the reader does not yet know.

A failed analyst report is missing evidence: name the missing perspective and lower your
confidence; never fill it in. Never recommend buying, selling or holding. Brutally honest,
plain language, no marketing words.
"""


class Conflict(BaseModel):
    between: list[str] = Field(
        description="The evaluator keys in conflict, e.g. ['business_model', 'valuation']."
    )
    description: str
    nature: Literal["REAL", "DIFFERENT_ANGLES"]
    explanation: str


class MonitoringItem(BaseModel):
    item: str = Field(description="The metric or event.")
    threshold: str = Field(description="The value or outcome that would change the view.")
    from_evaluator: str = Field(description="The evaluator key it comes from.")


class SynthesisResult(BaseModel):
    bull_case: str
    bear_case: str
    bull_answers_bear: str
    bear_answers_bull: str
    conflicts: list[Conflict]
    stronger_side: Literal["BULL", "BEAR", "BALANCED"]
    judge_summary: str
    genuinely_uncertain: list[str]
    rests_on_assumptions: list[str] = Field(
        description="Findings that rest on ASSUMPTION or UNVERIFIED claims."
    )
    verdict: FinalVerdict
    conditions: list[str] = Field(description="Required for CONDITIONAL_CASE; otherwise empty.")
    confidence: Confidence
    confidence_reason: str
    monitoring_plan: list[MonitoringItem]
    next_research_steps: list[str]
    beginner_explanation: str


def evaluator_view(result: dict) -> dict:
    """An evaluator result without bookkeeping fields: what the committee reads."""
    return {key: value for key, value in result.items() if key not in BOOKKEEPING}


def pack_summary(pack: dict) -> dict:
    return {
        "ticker": pack["ticker"],
        "company_name": pack["company_name"],
        "as_of": pack["as_of"],
        "price": pack["price"],
        "user_context": pack["user_context"],
        "valuation_multiples": pack["derived"]["valuation"],
        "data_quality": pack["data_quality"],
    }


def synthesis_user(pack: dict, results: list[dict], valuation_math: dict) -> str:
    material = {
        "pack_summary": pack_summary(pack),
        "valuation_math": valuation_math,
        "analyst_reports": [evaluator_view(r) for r in results],
    }
    return (
        "Reconcile these analyst reports into the committee's conclusion.\n\n"
        "<committee_material>\n"
        + json.dumps(material, ensure_ascii=False, indent=1)
        + "\n</committee_material>"
    )


def synthesis_validator(results: list[dict]):
    keys = {r["key"] for r in results}
    forensic = next((r for r in results if r["key"] == "forensic" and r.get("status") == "success"), None)
    severe = forensic is not None and (
        forensic.get("verdict") == "RED_FLAG"
        or any(f["severity"] >= 4 for f in forensic.get("red_flags", []))
    )

    def validate(result: SynthesisResult) -> list[str]:
        problems = []
        for name in ("bull_case", "bear_case", "judge_summary", "beginner_explanation"):
            problems += text_problems(name, getattr(result, name), 80, 4000)
        problems += text_problems("confidence_reason", result.confidence_reason, 10, 500)
        problems += count_problems("monitoring_plan", result.monitoring_plan, 3, 5)
        problems += count_problems("next_research_steps", result.next_research_steps, 3, 3)
        if result.verdict == "CONDITIONAL_CASE" and not result.conditions:
            problems.append("CONDITIONAL_CASE needs at least one condition")
        if result.verdict == "RED_FLAGGED" and not severe:
            problems.append("RED_FLAGGED needs a forensic RED_FLAG verdict or a flag of severity 4 or more")
        for conflict in result.conflicts:
            unknown = [k for k in conflict.between if k not in keys]
            if unknown:
                problems.append(f"conflict names unknown evaluators {unknown}; use {sorted(keys)}")
        return problems

    return validate


def unverified_share(results: list[dict]) -> float | None:
    claims = [c for r in results if r.get("status") == "success" for c in r.get("claims", [])]
    if not claims:
        return None
    return sum(1 for c in claims if c["tag"] == "UNVERIFIED") / len(claims)


def adjust_confidence(confidence: str, results: list[dict]) -> tuple[str, list[str]]:
    """Lower the committee's confidence one level per rule that applies."""
    reasons = []
    share = unverified_share(results)
    if share is not None and share > UNVERIFIED_SHARE_LIMIT:
        reasons.append(
            f"{share:.0%} of the analysts' claims are UNVERIFIED (limit {UNVERIFIED_SHARE_LIMIT:.0%})"
        )
    failed = [r["key"] for r in results if r.get("status") != "success"]
    if failed:
        reasons.append(f"missing perspectives: {', '.join(failed)}")
    level = CONFIDENCE_LEVELS.index(confidence)
    return CONFIDENCE_LEVELS[max(0, level - len(reasons))], reasons
