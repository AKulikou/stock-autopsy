"""Valid evaluator and committee outputs for fake-client tests, built from a real pack."""

from conftest import response

from evaluators.paths import resolve
from evaluators.schemas import (
    AssumptionNote,
    BusinessModelResult,
    Claim,
    FailureScenario,
    ForensicResult,
    InvalidationSignal,
    PreMortemResult,
    RedFlag,
    ScenarioAssumptions,
    ValuationAssumptions,
    ValuationResult,
    VerificationItem,
)
from synthesis.committee import Conflict, MonitoringItem, SynthesisResult

VERDICT = {
    "confidence": "MEDIUM",
    "confidence_reason": "Ten years of filings, but no segment data in the pack.",
    "key_finding": "Margins held steady across the ten fiscal years in the pack.",
    "biggest_unknown": "Segment revenue, which the Phase 1 pack does not contain.",
    "summary": "The numbers describe a stable business. The pack lacks segment detail, so the "
    "analysis stays at the consolidated level.",
}


def last_year(pack: dict) -> int:
    return pack["financials_annual"][-1]["fiscal_year"]


def claims(pack: dict) -> list[Claim]:
    year = last_year(pack)
    revenue = resolve(pack, f"financials_annual.FY{year}.revenue")
    return [
        Claim(
            statement=f"Revenue was ${revenue / 1e9:.1f} billion in FY{year}.",
            tag="DATA",
            basis=f"financials_annual.FY{year}.revenue",
        ),
        Claim(
            statement="Gross margin is the margin computed by Python.",
            tag="DERIVED",
            basis=f"derived.annual.FY{year}.gross_margin",
        ),
        Claim(
            statement="Pricing power persists over five years.",
            tag="ASSUMPTION",
            basis="Stable margins through input cost swings.",
        ),
        Claim(
            statement="Segment growth is led by emerging markets.",
            tag="UNVERIFIED",
            basis="10-K, Item 7, segment discussion.",
        ),
    ]


def business_model(pack: dict) -> BusinessModelResult:
    return BusinessModelResult(
        verdict="STRONG",
        **VERDICT,
        business_summary="Sells branded products through partners to consumers who pay for the brand.",
        segments="INSUFFICIENT DATA: the pack has no segment breakdown.",
        revenue_quality="Mostly repeat consumer purchases.",
        unit_economics="Gross margin stable around sixty percent with modest operating leverage.",
        key_dependencies=["consumer volumes", "input costs"],
        common_misunderstanding="That it is a growth company.",
        claims=claims(pack),
    )


def forensic(pack: dict, severity: int = 3, verdict: str = "ADEQUATE") -> ForensicResult:
    return ForensicResult(
        verdict=verdict,
        **VERDICT,
        red_flags=[
            RedFlag(
                flag="Recast revenue",
                evidence="[DATA] data_quality.restated lists FY2018 revenue.",
                severity=severity,
                why_it_matters="Trends across the recast are not comparable.",
                innocent_explanation="A presentation change disclosed in a later 10-K.",
            )
        ],
        red_flag_score=3,
        red_flag_score_reason="One explained recast and no late filings or non-reliance notices.",
        claims=claims(pack),
    )


def scenario(growth: float, margin: float) -> ScenarioAssumptions:
    return ScenarioAssumptions(
        revenue_growth=[growth] * 5,
        operating_margin=[margin] * 5,
        tax_rate=0.2,
        capex_pct_revenue=0.04,
        da_pct_revenue=0.03,
        nwc_pct_revenue_change=0.05,
        discount_rate=0.08,
        terminal_growth=0.025,
    )


def valuation_assumptions(pack: dict) -> ValuationAssumptions:
    return ValuationAssumptions(
        bear=scenario(0.01, 0.25),
        base=scenario(0.04, 0.29),
        bull=scenario(0.06, 0.31),
        notes=[
            AssumptionNote(assumption=a, reasoning="Anchored on history.", anchor="derived.revenue_cagr_5y")
            for a in ("growth", "margin", "discount rate")
        ],
        claims=claims(pack),
    )


def valuation(pack: dict) -> ValuationResult:
    return ValuationResult(
        verdict="WEAK",
        **VERDICT,
        relative_valuation="The TTM P/E is high for the growth in the pack.",
        implied_expectations="The price implies revenue growth above the five-year history.",
        achievability="Above anything in the ten years of data.",
        most_sensitive_assumption="Discount rate.",
        multiple_drivers="Volume trends and input costs.",
        claims=claims(pack),
    )


def pre_mortem(pack: dict) -> PreMortemResult:
    return PreMortemResult(
        verdict="ADEQUATE",
        **VERDICT,
        failure_scenarios=[
            FailureScenario(
                scenario=f"Scenario {n}", causal_chain="Volumes fall, fixed costs stay, margins compress."
            )
            for n in (1, 2, 3)
        ],
        poor_fit="Low growth for a long horizon.",
        invalidation_criteria=[
            InvalidationSignal(signal=f"Signal {n}", metric="derived.annual gross_margin") for n in (1, 2, 3)
        ],
        shaky_data=["TTM lags the latest 10-Q."],
        verification_checklist=[
            VerificationItem(fact=f"Fact {n}", where_to_find="10-K, Item 7") for n in (1, 2, 3)
        ],
        claims=claims(pack),
    )


def synthesis(verdict: str = "CONDITIONAL_CASE", confidence: str = "HIGH") -> SynthesisResult:
    long = "A long enough paragraph of committee reasoning that cites the analysts' reports only. " * 2
    return SynthesisResult(
        bull_case=long,
        bear_case=long,
        bull_answers_bear="Margins held.",
        bear_answers_bull="The price is high.",
        conflicts=[
            Conflict(
                between=["business_model", "valuation"],
                description="Strong business, weak price.",
                nature="REAL",
                explanation="Great company, priced for perfection.",
            )
        ],
        stronger_side="BALANCED",
        judge_summary=long,
        genuinely_uncertain=["Segment trends"],
        rests_on_assumptions=["Pricing power"],
        verdict=verdict,
        conditions=["Revenue growth above 4% a year"] if verdict == "CONDITIONAL_CASE" else [],
        confidence=confidence,
        confidence_reason="Consistent filings, but the price needs growth.",
        monitoring_plan=[
            MonitoringItem(item=f"Item {n}", threshold="below 55%", from_evaluator="pre_mortem")
            for n in (1, 2, 3)
        ],
        next_research_steps=["Step 1", "Step 2", "Step 3"],
        beginner_explanation=long,
        headline="A conditional case: a durable business whose price already assumes steady growth.",
        reasons_for=["Margins held for ten years.", "Cash flow covers the dividend.", "Debt is modest."],
        reasons_against=["The price assumes growth.", "Revenue growth is slow.", "Recasts need checking."],
    )


def handler_for(pack: dict, overrides: dict | None = None):
    """A FakeClaude handler answering each request by its output schema."""
    builders = {
        ValuationAssumptions: valuation_assumptions,
        BusinessModelResult: business_model,
        ForensicResult: forensic,
        ValuationResult: valuation,
        PreMortemResult: pre_mortem,
        SynthesisResult: lambda p: synthesis(),
    }
    builders.update(overrides or {})

    def handle(request: dict):
        builder = builders[request["output_format"]]
        result = builder(pack)
        if isinstance(result, Exception):
            raise result
        return response(result)

    return handle
