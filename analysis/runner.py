"""
One run, in this order:

1. The DATA PACK and its hash; the shared prefix (rules + pack) for every evaluator.
2. Valuation step A alone: its assumptions feed the DCF, and the call warms the
   prompt cache for the others.
3. Python runs the DCF, the reverse DCF and the sensitivities.
4. Business Model, Forensic, Pre-Mortem and valuation step B in parallel (B gets
   the DCF results after its questions, outside the cached prefix).
5. The Investment Committee, if enough perspectives succeeded; code then applies
   the confidence rules.
6. The number check over every DATA claim.
"""

import json
import logging
import time
from dataclasses import dataclass, field

from config import ANALYSIS_EFFORT, MAX_TOKENS, MODEL, THINKING
from core.claude_client import get_client
from core.fanout import run_parallel
from core.shared_context import context_block, sha256_of
from core.structured_call import billed_usage, request_structured
from core.token_summary import call_cost
from datalayer.fetch import RawCompanyData
from datalayer.pack import build_pack, pack_hash
from evaluators import definitions as d
from evaluators import validation as v
from evaluators.schemas import (
    BusinessModelResult,
    ForensicResult,
    PreMortemResult,
    ScenarioAssumptions,
    ValuationAssumptions,
    ValuationResult,
)
from perspectives.perspective import evaluate, shared_prefix
from reporting.number_check import check_results
from synthesis.committee import SYNTHESIS_PRINCIPLES, SynthesisResult, adjust_confidence, synthesis_user
from synthesis.committee import synthesis_validator as committee_validator
from valuation.dcf import SCENARIOS, run_valuation

logger = logging.getLogger(__name__)

PACK_TAG = "data_pack"
# The committee runs only when at least this many of the verdict-giving
# perspectives succeeded; with fewer, a conclusion would rest on too little.
MIN_PERSPECTIVES_FOR_SYNTHESIS = 3
VERDICT_KEYS = ("business_model", "forensic", "valuation", "pre_mortem")


@dataclass
class AutopsyRun:
    pack: dict
    pack_hash: str
    prefix_hash: str
    provenance: dict
    results: list[dict]
    valuation_math: dict
    synthesis: dict
    number_check: dict
    model: str = MODEL
    duration_s: float = 0.0
    calls: list[dict] = field(default_factory=list)

    def result(self, key: str) -> dict | None:
        return next((r for r in self.results if r["key"] == key), None)

    @property
    def total_cost(self) -> float | None:
        costs = [call_cost(c) for c in self.calls if "input_tokens" in c]
        return None if None in costs else sum(costs)


def valuation_material(valuation_math: dict) -> str:
    return (
        "Valuation math computed by Python from your team's step-A assumptions and the pack "
        "(cite its values as DATA with paths such as 'valuation_math.value_per_share.base'):\n"
        "<valuation_math>\n" + json.dumps(valuation_math, indent=1) + "\n</valuation_math>"
    )


def scenarios_from(result: dict) -> dict[str, ScenarioAssumptions]:
    return {name: ScenarioAssumptions(**result[name]) for name in SCENARIOS}


def run_committee(pack: dict, results: list[dict], valuation_math: dict) -> dict:
    started = time.monotonic()
    succeeded = [r for r in results if r["key"] in VERDICT_KEYS and r["status"] == "success"]
    if len(succeeded) < MIN_PERSPECTIVES_FOR_SYNTHESIS:
        return {
            "key": "synthesis",
            "label": "Investment Committee",
            "status": "error",
            "error": f"only {len(succeeded)} of {len(VERDICT_KEYS)} perspectives succeeded; "
            f"the committee needs {MIN_PERSPECTIVES_FOR_SYNTHESIS}",
        }
    base = {"key": "synthesis", "label": "Investment Committee", "model": MODEL}
    try:
        response = request_structured(
            get_client(),
            label="Investment Committee",
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYNTHESIS_PRINCIPLES,
            user=synthesis_user(pack, results, valuation_math),
            output_format=SynthesisResult,
            validate=committee_validator(results),
            thinking=THINKING == "adaptive",
            effort=ANALYSIS_EFFORT,
        )
    except Exception as e:
        logger.error(f"Investment Committee failed: {type(e).__name__}: {e}")
        return {
            **base,
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
            "duration_s": time.monotonic() - started,
            **billed_usage(e),
        }
    synthesis = response.result.model_dump(mode="json")
    adjusted, reasons = adjust_confidence(synthesis["confidence"], results)
    return {
        **base,
        "status": "success",
        **synthesis,
        "model_confidence": synthesis["confidence"],
        "confidence": adjusted,
        "confidence_adjustments": reasons,
        **response.usage.as_dict(),
        "duration_s": time.monotonic() - started,
    }


def run_autopsy(raw: RawCompanyData, user_context: dict | None = None) -> AutopsyRun:
    started = time.monotonic()
    pack, provenance = build_pack(raw, user_context)
    prefix = shared_prefix(d.SHARED_RULES, context_block(PACK_TAG, pack))
    logger.info(f"{pack['ticker']}: pack {pack_hash(pack)[:12]}, prefix {len(prefix):,} chars")

    assumptions = evaluate(
        d.VALUATION_ASSUMPTIONS, prefix, ValuationAssumptions, v.valuation_assumptions_validator(pack)
    )
    logger.info(f"{assumptions['label']}: {assumptions['status']}")
    if assumptions["status"] == "success":
        valuation_math = run_valuation(scenarios_from(assumptions), pack)
    else:
        valuation_math = {
            "computed": False,
            "reasons": [f"valuation assumptions failed: {assumptions['error']}"],
        }

    # Step B may cite the Python valuation math it received, as valuation_math.<field>.
    with_math = {**pack, "valuation_math": valuation_math}
    tasks = [
        (
            d.BUSINESS_MODEL.name,
            lambda: evaluate(d.BUSINESS_MODEL, prefix, BusinessModelResult, v.business_model_validator(pack)),
        ),
        (d.FORENSIC.name, lambda: evaluate(d.FORENSIC, prefix, ForensicResult, v.forensic_validator(pack))),
        (
            d.VALUATION.name,
            lambda: evaluate(
                d.VALUATION,
                prefix,
                ValuationResult,
                v.valuation_validator(with_math),
                material=valuation_material(valuation_math),
            ),
        ),
        (
            d.PRE_MORTEM.name,
            lambda: evaluate(d.PRE_MORTEM, prefix, PreMortemResult, v.pre_mortem_validator(pack)),
        ),
    ]
    parallel = run_parallel(tasks, warm_up_first=False)
    results = [assumptions, *parallel]
    for result in parallel:
        logger.info(f"{result['label']}: {result['status']} {result.get('verdict', result.get('error', ''))}")

    synthesis = run_committee(pack, results, valuation_math)
    logger.info(
        f"Investment Committee: {synthesis['status']} {synthesis.get('verdict', synthesis.get('error'))}"
    )
    return AutopsyRun(
        pack=pack,
        pack_hash=pack_hash(pack),
        prefix_hash=sha256_of(prefix),
        provenance=provenance,
        results=results,
        valuation_math=valuation_math,
        synthesis=synthesis,
        number_check=check_results(results, with_math),
        duration_s=time.monotonic() - started,
        calls=[*results, synthesis],
    )
