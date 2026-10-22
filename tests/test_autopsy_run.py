"""A whole run on a golden ticker with the fake client: order, prompts, reports, failures."""

import copy
import json
import re

import pytest
from conftest import cached_prefix_of, response
from sample_outputs import forensic, handler_for, synthesis

from analysis.runner import dcf_event, pack_summary_text, run_autopsy
from core.shared_context import context_block
from datalayer.pack import build_pack
from evaluators.schemas import AnalystOutput, Claim, ForensicResult, PreMortemResult, ValuationAssumptions
from perspectives import perspective as perspective_module
from reporting.json_export import build_json
from reporting.markdown import DISCLAIMER, build_report
from scripts.freeze_golden import FIXTURES, raw_from_fixture
from synthesis.committee import SynthesisResult
from translate.glossary import load_glossary, split_glossary
from valuation.dcf import run_valuation


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


def test_a_schema_per_analyst_gives_each_its_own_cache_entry(fake_claude, raw_ko, ko_pack):
    # The NVDA run of 2026-10-22: five cache writes, no read. The API renders the output
    # schema ahead of the cached prefix, so five schemas are five prefixes.
    run, fake = run_with(fake_claude, raw_ko, ko_pack, simulate_cache=True)
    assert fake.requests[0]["output_format"] is ValuationAssumptions
    analysts = run.results
    assert all(r["cache_creation_input_tokens"] > 0 and r["cache_read_input_tokens"] == 0 for r in analysts)


@pytest.fixture
def shared_schema(monkeypatch):
    monkeypatch.setattr(perspective_module, "SHARED_OUTPUT_SCHEMA", True)


def test_with_the_shared_schema_step_a_warms_the_cache_for_the_others(
    shared_schema, fake_claude, raw_ko, ko_pack
):
    run, fake = run_with(fake_claude, raw_ko, ko_pack, simulate_cache=True)
    first, *others = run.results
    assert first["key"] == "valuation_assumptions" and first["cache_creation_input_tokens"] > 0
    assert len(others) == 4
    assert all(r["cache_read_input_tokens"] > 0 and r["cache_creation_input_tokens"] == 0 for r in others)
    assert [r["status"] for r in run.results] == ["success"] * 5


def test_every_analyst_request_has_the_identical_prefix(shared_schema, fake_claude, raw_ko, ko_pack):
    _, fake = run_with(fake_claude, raw_ko, ko_pack)
    analysts = [r for r in fake.requests if r["output_format"] is not SynthesisResult]
    assert len(analysts) == 5
    assert len({cached_prefix_of(r) for r in analysts}) == 1
    assert {r["output_format"] for r in analysts} == {AnalystOutput}
    # Each still answers in its own field, named after the breakpoint.
    fields = [re.search(r"output field (\w+) ", r["messages"][0]["content"]).group(1) for r in analysts]
    assert sorted(fields) == sorted(AnalystOutput.model_fields)


def test_the_shared_schema_unwraps_to_the_same_result_fields(
    shared_schema, monkeypatch, fake_claude, raw_ko, ko_pack
):
    shared, _ = run_with(fake_claude, raw_ko, ko_pack)
    monkeypatch.setattr(perspective_module, "SHARED_OUTPUT_SCHEMA", False)
    separate, _ = run_with(fake_claude, raw_ko, ko_pack)

    def content(result):
        return {k: v for k, v in result.items() if k != "duration_s"}

    assert [content(r) for r in shared.results] == [content(r) for r in separate.results]


def test_the_analysts_start_only_after_step_a_has_returned(shared_schema, fake_claude, raw_ko, ko_pack):
    # A cache entry is readable only once the first response has started (prompt caching docs).
    events = []
    handler = handler_for(ko_pack)

    def timed(request):
        field = re.search(r"output field (\w+) ", request["messages"][0]["content"])
        name = field.group(1) if field else "committee"
        events.append(("start", name))
        answer = handler(request)
        events.append(("end", name))
        return answer

    fake_claude(timed)
    run_autopsy(raw_ko)
    assert events[:2] == [("start", "valuation_assumptions"), ("end", "valuation_assumptions")]
    assert {name for kind, name in events[2:] if kind == "start"} >= {
        "business_model", "forensic", "valuation", "pre_mortem"}


def test_an_answer_in_the_wrong_field_is_rejected(shared_schema, fake_claude, raw_ko, ko_pack):
    handler = handler_for(ko_pack)

    def misplaced(request):
        answer = handler(request)
        envelope = answer.parsed_output
        if "output field forensic " in request["messages"][0]["content"]:
            answer.parsed_output = AnalystOutput(**{**dict(envelope), "forensic": None,
                                                    "pre_mortem": None})
        return answer

    fake_claude(misplaced)
    run = run_autopsy(raw_ko)
    forensic_result = next(r for r in run.results if r["key"] == "forensic")
    assert forensic_result["status"] == "error"
    assert "the field forensic is null" in forensic_result["error"]


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
    assert "SEC EDGAR financial data" in report and "Yahoo Finance" in report
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
    assert "the numbers are not in the cited data" in build_report(run)


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


def data_claims(pack: dict, bases: list[str]) -> list[Claim]:
    """DATA claims quoting last year's revenue, with the given bases."""
    year = pack["financials_annual"][-1]["fiscal_year"]
    revenue = pack["financials_annual"][-1]["revenue"]
    return [
        Claim(statement=f"Revenue was ${revenue / 1e9:.1f} billion in FY{year}.", tag="DATA", basis=basis)
        for basis in bases
    ]


def test_mostly_invented_paths_reject_the_answer_and_keep_it(fake_claude, raw_ko, ko_pack):
    requests = []

    def bad_paths(pack):
        result = forensic(pack)
        result.claims = data_claims(pack, ["financials_annual.FY2031.revenue"] * 4)
        return result

    def record(request):
        requests.append(request)
        return handler_for(ko_pack, {ForensicResult: bad_paths})(request)

    fake_claude(record)
    run = run_autopsy(raw_ko)
    error = run.result("forensic")
    assert error["status"] == "error" and "name no existing pack path" in error["error"]
    assert error["rejected_output"]["verdict"] == "ADEQUATE"  # the paid answer is kept
    retry = [r for r in requests if r["output_format"] is ForensicResult][1]
    assert "previous answer was rejected" in retry["messages"][0]["content"]


def test_one_bad_path_among_many_is_reported_not_rejected(fake_claude, raw_ko, ko_pack):
    year = ko_pack["financials_annual"][-1]["fiscal_year"]
    good = f"financials_annual.FY{year}.revenue"

    def one_bad(pack):
        result = forensic(pack)
        result.claims = data_claims(pack, [good, good, good, "financials_annual.FY2031.revenue"])
        return result

    run, _ = run_with(fake_claude, raw_ko, ko_pack, {ForensicResult: one_bad})
    assert run.result("forensic")["status"] == "success"
    bad = [p for p in run.number_check["problems"] if p["status"] == "bad_path"]
    assert len(bad) == 1 and bad[0]["bad_paths"] == ["financials_annual.FY2031.revenue"]


def test_several_paths_and_notes_in_a_basis_are_understood(fake_claude, raw_ko, ko_pack):
    year = ko_pack["financials_annual"][-1]["fiscal_year"]
    basis = f"financials_annual.FY{year - 1}.revenue (prior year); financials_annual.FY{year}.revenue"

    def multi(pack):
        result = forensic(pack)
        result.claims = data_claims(pack, [basis] * 3)
        return result

    run, _ = run_with(fake_claude, raw_ko, ko_pack, {ForensicResult: multi})
    forensic_checks = [c for c in run.number_check["checked"] if c["evaluator"] == "forensic"]
    assert {c["status"] for c in forensic_checks} == {"match"}


def test_a_number_missing_from_the_cited_values_is_partial(fake_claude, raw_ko, ko_pack):
    year = ko_pack["financials_annual"][-1]["fiscal_year"]

    def extra_number(pack):
        result = forensic(pack)
        result.claims = data_claims(pack, [f"financials_annual.FY{year}.revenue"] * 3)
        result.claims[0].statement += " It grew 9.9% from the year before."
        return result

    run, _ = run_with(fake_claude, raw_ko, ko_pack, {ForensicResult: extra_number})
    partial = [p for p in run.number_check["problems"] if p["status"] == "partial"]
    assert len(partial) == 1 and partial[0]["unmatched"] == [0.099]


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


def test_a_dcf_the_data_cannot_carry_is_not_computed_not_failed(ko_pack):
    pack = copy.deepcopy(ko_pack)
    pack["ttm"]["revenue"] = None
    valuation_math = run_valuation({}, pack)
    assert valuation_math["computed"] is False
    event = dcf_event(valuation_math, assumptions_ok=True)
    assert event.status == "not_computed"
    assert event.text == "DCF not computed: revenue over the last twelve months is missing or not positive."
    failed = {"computed": False, "reasons": ["valuation assumptions failed: ConnectionError"]}
    assert dcf_event(failed, assumptions_ok=False).status == "failed"


def test_the_pack_summary_counts_in_words(ko_pack):
    pack = {**ko_pack, "filing_events": ko_pack["filing_events"][:1], "price": None}
    text = pack_summary_text(pack)
    assert "1 filing event," in text and text.endswith("no price")
    assert "quarters" in text


def test_the_implied_growth_names_the_return_it_is_needed_for(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack)
    rate = f"{run.valuation_math['reverse_dcf']['discount_rate']:.1%}"
    assert f"Reverse DCF: to earn the base-case discount rate of {rate} a year" in build_report(run)


def test_every_report_table_has_a_header_with_words(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack)
    lines = build_report(run).splitlines()
    headers = [lines[i - 1] for i, line in enumerate(lines) if re.fullmatch(r"\|(?:-+\|)+", line)]
    assert headers and all(re.search(r"\w", cell) for h in headers for cell in h.strip("|").split("|"))
    assert "| Detail | Value |" in lines


def test_report_md_ends_with_a_collapsed_glossary_of_the_terms_it_uses(fake_claude, raw_ko, ko_pack):
    run, _ = run_with(fake_claude, raw_ko, ko_pack)
    report = build_report(run)
    body, block = split_glossary(report)
    assert block.startswith("<details><summary>Glossary</summary>") and report.rstrip().endswith("</details>")
    english = load_glossary("English")
    listed = [e for e in english.entries if f"- **{e.term}**: " in block]
    assert listed and all(e.occurs_in(body) for e in listed)
    assert [e for e in english.entries if e.occurs_in(body)] == listed  # every used term, nothing else
    # The cost table says "done", a word the glossary defines, not the status code.
    assert "| done |" in body and "| success |" not in body
    assert any(e.term == "done / failed" for e in listed)
