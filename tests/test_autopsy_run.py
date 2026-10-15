"""A whole run on a golden ticker with the fake client: order, prompts, reports, failures."""

import json
import re

import pytest
from conftest import response
from sample_outputs import claims, forensic, handler_for, synthesis

from analysis.runner import run_autopsy
from core.shared_context import context_block
from datalayer.pack import build_pack
from evaluators.schemas import ForensicResult, PreMortemResult, ValuationAssumptions
from reporting.json_export import build_json
from reporting.markdown import DISCLAIMER, build_report
from scripts.freeze_golden import FIXTURES, raw_from_fixture
from synthesis.committee import SynthesisResult


@pytest.fixture
def raw_ko():
    return raw_from_fixture(FIXTURES / "KO")


@pytest.fixture
def ko_pack(raw_ko):
    return build_pack(raw_ko)[0]


def run_with(fake_claude, raw, pack, overrides=None, simulate_cache=False):
    fake = fake_claude(handler_for(pack, overrides), simulate_cache=simulate_cache)
    return run_autopsy(raw), fake


def cached_text(request: dict) -> str | None:
    system = request["system"]
    return system[0]["text"] if isinstance(system, list) else None


def test_every_evaluator_gets_the_identical_prefix(fake_claude, raw_ko, ko_pack):
    _, fake = run_with(fake_claude, raw_ko, ko_pack)
    prefixes = {cached_text(r) for r in fake.requests if r["output_format"] is not SynthesisResult}
    assert len(prefixes) == 1 and None not in prefixes
    assert len(fake.requests) == 6  # step A, four in parallel, the committee


def test_the_prompt_carries_the_pack_exactly_with_nulls_not_zeros(fake_claude, raw_ko, ko_pack):
    _, fake = run_with(fake_claude, raw_ko, ko_pack)
    text = cached_text(fake.requests[0])
    body = re.search(r"<data_pack>\n(.*)\n</data_pack>", text, re.S).group(1)
    assert json.loads(body) == ko_pack


def test_a_missing_value_reaches_the_prompt_as_null_and_a_zero_only_when_filed():
    raw = raw_from_fixture(FIXTURES / "SNOW")
    pack, provenance = build_pack(raw)
    block = context_block("data_pack", pack)
    rows = {
        r["fiscal_year"]: r
        for r in json.loads(re.search(r"<data_pack>\n(.*)\n</data_pack>", block, re.S).group(1))[
            "financials_annual"
        ]
    }
    assert rows[2019]["total_debt"] is None  # no debt concept reported: unknown
    # SNOW's 10-K reports convertible debt of 0 at 2024-01-31 explicitly (before its 2024 notes).
    assert rows[2024]["total_debt"] == 0
    assert provenance["FY2024.total_debt"]["formula"] == "ConvertibleDebtNoncurrent"


def test_valuation_step_a_runs_first_and_warms_the_cache(fake_claude, raw_ko, ko_pack):
    run, fake = run_with(fake_claude, raw_ko, ko_pack, simulate_cache=True)
    assert fake.requests[0]["output_format"] is ValuationAssumptions
    first, *others = [c for c in run.results]
    assert first["cache_creation_input_tokens"] > 0
    assert all(r["cache_read_input_tokens"] > 0 for r in others)


def test_step_b_receives_the_python_dcf(fake_claude, raw_ko, ko_pack):
    run, fake = run_with(fake_claude, raw_ko, ko_pack)
    step_b = next(r for r in fake.requests if "<valuation_math>" in r["messages"][0]["content"])
    assert str(run.valuation_math["value_per_share"]["base"]) in step_b["messages"][0]["content"]
    assert run.valuation_math["computed"] is True


def test_report_states_data_date_sources_hash_and_disclaimer(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack)
    report = build_report(run)
    assert DISCLAIMER in report
    assert run.pack_hash in report and ko_pack["as_of"] in report
    assert "SEC EDGAR company facts" in report
    assert "Verdict: Conditional case" in report
    data = build_json(run)
    assert data["meta"]["pack_sha256"] == run.pack_hash
    assert data["synthesis"]["verdict"] == "CONDITIONAL_CASE"
    json.dumps(data, allow_nan=False)


def test_number_check_passes_correct_data_claims(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack)
    assert run.number_check["counts"] == {"match": 5}
    assert run.number_check["problems"] == []


def test_number_check_catches_an_invented_number(fake_claude, raw_ko, ko_pack):
    def wrong(pack):
        result = forensic(pack)
        result.claims[0].statement = "Revenue was $52.0 billion in the last fiscal year."
        return result

    run, _ = run_with(fake_claude, raw_ko, ko_pack, {ForensicResult: wrong})
    problems = run.number_check["problems"]
    assert [(p["evaluator"], p["status"]) for p in problems] == [("forensic", "mismatch")]
    assert "mismatch" in build_report(run)


def test_one_failed_perspective_lowers_the_committee_confidence(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack, {PreMortemResult: lambda p: RuntimeError("boom")})
    assert run.result("pre_mortem")["status"] == "error"
    assert run.synthesis["status"] == "success"
    assert run.synthesis["model_confidence"] == "HIGH" and run.synthesis["confidence"] == "MEDIUM"
    assert "pre_mortem" in run.synthesis["confidence_adjustments"][0]
    assert "**Failed:**" in build_report(run)


def test_two_failed_perspectives_leave_no_committee_verdict(fake_claude, raw_ko, ko_pack):
    failing = {
        PreMortemResult: lambda p: RuntimeError("boom"),
        ForensicResult: lambda p: RuntimeError("boom"),
    }
    run, fake = run_with(fake_claude, raw_ko, ko_pack, failing)
    assert run.synthesis["status"] == "error"
    assert not [r for r in fake.requests if r["output_format"] is SynthesisResult]
    assert "No conclusion" in build_report(run)


def test_failed_step_a_still_runs_step_b_without_a_dcf(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack, {ValuationAssumptions: lambda p: RuntimeError("boom")})
    assert run.valuation_math["computed"] is False
    assert run.result("valuation")["status"] == "success"
    assert "DCF not computed" in build_report(run)


def test_invalid_answer_is_retried_once(fake_claude, raw_ko, ko_pack):
    attempts = []

    def flaky(pack):
        attempts.append(1)
        bad = forensic(pack, severity=5, verdict="ADEQUATE")  # severity 5 requires RED_FLAG
        return bad if len(attempts) == 1 else forensic(pack)

    run, _ = run_with(fake_claude, raw_ko, ko_pack, {ForensicResult: flaky})
    assert len(attempts) == 2
    assert run.result("forensic")["status"] == "success"


def test_data_claim_with_an_invented_path_is_rejected(fake_claude, raw_ko, ko_pack):
    def bad_path(pack):
        result = forensic(pack)
        result.claims = claims(pack)
        result.claims[0].basis = "financials_annual.FY2031.revenue"
        return result

    run, _ = run_with(fake_claude, raw_ko, ko_pack, {ForensicResult: bad_path})
    assert run.result("forensic")["status"] == "error"
    assert "not a pack path" in run.result("forensic")["error"]


def test_red_flagged_needs_a_severe_forensic_flag(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack, {SynthesisResult: lambda p: synthesis("RED_FLAGGED")})
    assert run.synthesis["status"] == "error"
    assert "RED_FLAGGED needs" in run.synthesis["error"]


def test_red_flagged_is_accepted_with_a_severity_5_flag(fake_claude, raw_ko, ko_pack):
    overrides = {
        SynthesisResult: lambda p: synthesis("RED_FLAGGED"),
        ForensicResult: lambda p: forensic(p, severity=5, verdict="RED_FLAG"),
    }
    run, _ = run_with(fake_claude, raw_ko, ko_pack, overrides)
    assert run.synthesis["verdict"] == "RED_FLAGGED"


def test_cost_is_summed_over_every_call(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack)
    assert run.total_cost == pytest.approx(6 * (1000 * 2 + 500 * 10) / 1e6)


def test_truncated_answer_becomes_an_error_result(fake_claude, raw_ko, ko_pack):
    def truncated(request):
        if request["output_format"] is PreMortemResult:
            return response(None, stop_reason="max_tokens")
        return handler_for(ko_pack)(request)

    fake_claude(truncated)
    run = run_autopsy(raw_ko)
    assert "max_tokens" in run.result("pre_mortem")["error"]
