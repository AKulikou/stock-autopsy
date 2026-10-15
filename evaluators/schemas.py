"""
Structured outputs of the evaluators (decision D3: the VERDICT block of the
source of truth as schema fields; confidence as LOW / MEDIUM / HIGH with a
reason instead of 0-100, which a model cannot calibrate).

Every claim carries its tag and its basis, so code can check it: a DATA claim
names the pack path of the value it quotes, and the number check compares the
numbers in the statement with the value at that path.
"""

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["STRONG", "ADEQUATE", "WEAK", "RED_FLAG", "INSUFFICIENT_DATA"]
Confidence = Literal["LOW", "MEDIUM", "HIGH"]
Tag = Literal["DATA", "DERIVED", "ASSUMPTION", "UNVERIFIED"]


class Claim(BaseModel):
    statement: str = Field(
        description="One factual or judgmental statement, as it should appear in the report."
    )
    tag: Tag
    basis: str = Field(
        description=(
            "DATA: the pack path of the value, e.g. financials_annual.FY2025.revenue. "
            "DERIVED: the formula with pack paths. ASSUMPTION: why you assume it. "
            "UNVERIFIED: what the user must check and where (filing type and section)."
        )
    )


class VerdictBlock(BaseModel):
    verdict: Verdict = Field(
        description="The company from this perspective only, not a trade recommendation."
    )
    confidence: Confidence
    confidence_reason: str = Field(description="One sentence: why this confidence level.")
    key_finding: str = Field(description="One sentence.")
    biggest_unknown: str = Field(description="One sentence: what data would most change this verdict.")
    summary: str = Field(description="Two or three sentences.")


# ---- Evaluator 1: Business Model ------------------------------------------------


class BusinessModelResult(VerdictBlock):
    business_summary: str = Field(description="What the company sells, to whom, and why customers pay.")
    segments: str = Field(
        description="Revenue by segment or geography if the pack has it; otherwise INSUFFICIENT DATA and why."
    )
    revenue_quality: str = Field(
        description="Recurring vs one-time, contract vs transactional, cyclical exposure."
    )
    unit_economics: str = Field(
        description="Gross margin trend and operating leverage over the available years."
    )
    key_dependencies: list[str] = Field(
        description="The two or three variables the whole business depends on."
    )
    common_misunderstanding: str = Field(description="What a reasonable person would misunderstand about it.")
    claims: list[Claim]


# ---- Evaluator 3: Forensic ---------------------------------------------------------


class RedFlag(BaseModel):
    flag: str
    evidence: str = Field(
        description="The evidence, with tags inline, e.g. '[DATA] operating cash flow ...'."
    )
    severity: int = Field(description="1 (minor) to 5 (severe).")
    why_it_matters: str
    innocent_explanation: str = Field(description="Always required: a red flag is a question, not a verdict.")


class ForensicResult(VerdictBlock):
    red_flags: list[RedFlag] = Field(description="Every flag found, most severe first; empty if none.")
    red_flag_score: int = Field(description="Overall 1 (clean) to 10 (severe).")
    red_flag_score_reason: str
    claims: list[Claim]


# ---- Evaluator 5: Valuation, step A (assumptions) and step B (interpretation) ----------


class ScenarioAssumptions(BaseModel):
    revenue_growth: list[float] = Field(
        description="Five decimals: revenue growth in years 1 to 5 (0.05 = 5%)."
    )
    operating_margin: list[float] = Field(description="Five decimals: operating margin in years 1 to 5.")
    tax_rate: float = Field(description="Decimal, on operating income.")
    capex_pct_revenue: float = Field(description="Capital expenditure as a share of revenue.")
    da_pct_revenue: float = Field(description="Depreciation and amortization as a share of revenue.")
    nwc_pct_revenue_change: float = Field(
        description="Working capital needed per dollar of revenue growth (negative if growth releases cash)."
    )
    discount_rate: float = Field(description="Decimal, e.g. 0.09.")
    terminal_growth: float = Field(description="Decimal, below the discount rate, e.g. 0.025.")


class AssumptionNote(BaseModel):
    assumption: str = Field(description="Which assumption, e.g. 'base revenue growth years 1-5'.")
    reasoning: str
    anchor: str = Field(description="The historical data point it is anchored on (pack path), or why none.")


class ValuationAssumptions(BaseModel):
    bear: ScenarioAssumptions
    base: ScenarioAssumptions
    bull: ScenarioAssumptions
    notes: list[AssumptionNote] = Field(description="Reasoning and anchor for each key assumption.")
    claims: list[Claim]


class ValuationResult(VerdictBlock):
    relative_valuation: str = Field(
        description="What the TTM multiples say, and whether growth, margins or durability justify them."
    )
    implied_expectations: str = Field(description="What revenue growth and margin the current price implies.")
    achievability: str = Field(description="Whether that is historically achievable for this company.")
    most_sensitive_assumption: str
    multiple_drivers: str = Field(
        description="What could expand or contract the multiple in the next 12 months."
    )
    claims: list[Claim]


# ---- Evaluator 8: Pre-Mortem --------------------------------------------------------


class FailureScenario(BaseModel):
    scenario: str
    causal_chain: str = Field(description="The mechanism, step by step, specific to this company.")


class InvalidationSignal(BaseModel):
    signal: str = Field(
        description="A concrete, measurable signal, e.g. 'gross margin below 55% for 2 quarters'."
    )
    metric: str = Field(description="The pack field or filing line it is measured on.")


class VerificationItem(BaseModel):
    fact: str
    where_to_find: str = Field(description="Filing type and section, e.g. '10-K, Item 7 MD&A, liquidity'.")


class PreMortemResult(VerdictBlock):
    failure_scenarios: list[FailureScenario] = Field(description="Three, most likely first.")
    poor_fit: str = Field(
        description="What makes the company a poor fit for the user's horizon and risk tolerance."
    )
    invalidation_criteria: list[InvalidationSignal] = Field(description="Three to five.")
    shaky_data: list[str] = Field(
        description="Which conclusions any analysis of this pack would build on shaky data."
    )
    verification_checklist: list[VerificationItem]
    claims: list[Claim]
