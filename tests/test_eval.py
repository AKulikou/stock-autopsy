"""The eval harness offline: grading functions, the judge, and whole attempts with the fake client."""

import json
import re

import pytest
from conftest import response
from sample_outputs import handler_for

from eval import grading as g
from eval import run_eval
from eval.judge import JudgeResult, StatementCheck, judge_validator, quote_in_report
from scripts.freeze_golden import FIXTURES, raw_from_fixture

# ---- grading ---------------------------------------------------------------------

CASE = {"id": "KO", "primary": "CONDITIONAL_CASE", "acceptable": ["STRONG_CASE", "INSUFFICIENT_DATA"]}


def test_verdict_grades():
    assert g.grade_verdict("CONDITIONAL_CASE", CASE) == {"primary_hit": 1, "in_range": 1, "error_cost": 0}
    assert g.grade_verdict("STRONG_CASE", CASE) == {"primary_hit": 0, "in_range": 1, "error_cost": 1}
    assert g.grade_verdict("RED_FLAGGED", CASE) == {"primary_hit": 0, "in_range": 0, "error_cost": 3}


def test_unlabelled_case_gets_no_verdict_grade():
    assert g.grade_verdict("WEAK_CASE", {"id": "X"}) == {}


def test_error_cost_is_zero_on_the_diagonal_and_worst_for_a_missed_red_flag():
    assert all(g.ERROR_COST[v][v] == 0 for v in g.VERDICTS)
    assert (
        max(max(row.values()) for row in g.ERROR_COST.values()) == g.ERROR_COST["RED_FLAGGED"]["STRONG_CASE"]
    )


def test_forensic_grade_checks_forbidden_verdicts_by_code():
    case = {"forensic_not": ["RED_FLAG"]}
    assert g.grade_forensic({"status": "success", "verdict": "RED_FLAG"}, case) == {"forensic_ok": 0}
    assert g.grade_forensic({"status": "success", "verdict": "WEAK"}, case) == {"forensic_ok": 1}
    assert g.grade_forensic({"status": "error"}, case) == {}


def test_baselines_count_trivial_answers():
    base = g.labelled_baselines(["WEAK_CASE", "CONDITIONAL_CASE"], [["WEAK_CASE"], ["CONDITIONAL_CASE"]])
    assert base["always"]["WEAK_CASE"]["primary_hits"] == 1
    assert base["random"]["primary_hits"] == pytest.approx(2 / 5)


def test_stability_of_a_verdict_across_reps():
    rows = [
        {"case_id": "KO", "meta": {"verdict": "CONDITIONAL_CASE"}},
        {"case_id": "KO", "meta": {"verdict": "WEAK_CASE"}},
        {"case_id": "KHC", "meta": {"verdict": "WEAK_CASE"}},
        {"case_id": "KHC", "meta": {"verdict": "WEAK_CASE"}},
    ]
    stab = g.stability(rows)
    assert stab["changed_cases"] == ["KO"] and stab["cross_side_cases"] == ["KO"]
    assert stab["pairwise_disagreement"] == pytest.approx(0.5)


def test_a_wrong_path_to_a_true_number_is_not_an_invention():
    roots = {"ttm": {"revenue": 24_900_000_000}, "derived": {"ttm": {"free_cash_flow": 3_816_000_000}}}
    check = {
        "checked": [
            {"evaluator": "x", "status": "bad_path", "statement": "TTM free cash flow is $3.816 billion."},
            {"evaluator": "y", "status": "mismatch", "statement": "Revenue was $31.7 billion."},
            {"evaluator": "z", "status": "match", "statement": "Revenue was $24.9 billion."},
        ]
    }
    invented = g.invented_numbers(check, roots)
    assert [(i["evaluator"], i["number"]) for i in invented] == [("y", 31.7e9)]


# ---- judge -------------------------------------------------------------------------

REPORT = (
    "COMMITTEE\n\nVerdict: WEAK_CASE\n\n"
    "Bear case: Two  Item 4.02 non-reliance filings (2017, 2019) and a late 10-K."
)


@pytest.mark.parametrize(
    "quote, found",
    [
        ("two item 4.02 non-reliance filings", True),
        ("'Two Item 4.02 non-reliance filings (2017, 2019)'", True),
        ("Verdict: WEAK_CASE ... a late 10-K", True),
        ("three non-reliance filings", False),
        ("none", False),
    ],
)
def test_evidence_must_be_a_verbatim_quote(quote, found):
    assert quote_in_report(quote, REPORT) is found


def test_judge_answer_with_an_invented_quote_is_rejected():
    validate = judge_validator([("must_find", "the restatement")], REPORT)
    good = JudgeResult(
        checks=[
            StatementCheck(
                index=1, kind="must_find", present=True, evidence="non-reliance filings (2017, 2019)"
            )
        ]
    )
    bad = JudgeResult(
        checks=[
            StatementCheck(index=1, kind="must_find", present=True, evidence="restated 2016 and 2017 figures")
        ]
    )
    absent = JudgeResult(checks=[StatementCheck(index=1, kind="must_find", present=False, evidence="none")])
    assert validate(good) == [] and validate(absent) == []
    assert "not a verbatim quote" in validate(bad)[0]


# ---- whole attempts with the fake client -----------------------------------------------

LABELLED = {
    "id": "KO",
    "fixture": "tests/fixtures/golden/KO",
    "primary": "CONDITIONAL_CASE",
    "acceptable": ["STRONG_CASE"],
    "must_find": ["a finding the committee states"],
    "must_not": ["a thing it does not do"],
    "forensic_not": ["RED_FLAG"],
}


def judge_answer(request: dict):
    """Present for must_find with a quote from the report, absent for must_not."""
    prompt = request["messages"][0]["content"]
    report = re.search(r"<report>\n(.*)\n</report>", prompt, re.S).group(1)
    quote = re.search(r"Verdict: \w+", report).group(0)
    kinds = re.findall(r"^\d+\. \[(must_find|must_not)\]", prompt, re.M)
    return JudgeResult(
        checks=[
            StatementCheck(
                index=i, kind=k, present=k == "must_find", evidence=quote if k == "must_find" else "none"
            )
            for i, k in enumerate(kinds, start=1)
        ]
    )


@pytest.fixture
def ko_handler():
    pack = __import__("datalayer.pack", fromlist=["build_pack"]).build_pack(
        raw_from_fixture(FIXTURES / "KO")
    )[0]
    run_handler = handler_for(pack)

    def handle(request):
        if request["output_format"] is JudgeResult:
            return response(judge_answer(request))
        return run_handler(request)

    return handle


def test_one_attempt_is_graded_and_written(fake_claude, ko_handler, tmp_path):
    fake = fake_claude(ko_handler)
    run_eval.run([LABELLED], 1, tmp_path, batch=False, concurrency=1)
    rows = run_eval.read_jsonl(tmp_path / "results.jsonl")
    assert len(rows) == 1
    row = rows[0]
    assert row["grade"] == {
        "primary_hit": 1,
        "in_range": 1,
        "error_cost": 0,
        "forensic_ok": 1,
        "all_valid": 1,
        "no_invented": 1,
        "flaw_found": 1,
        "must_not_ok": 1,
    }
    assert row["meta"]["numbers"]["invented"] == 0 and row["meta"]["numbers"]["matched"] == 5
    assert row["cost_usd"] > 0 and row["meta"]["judge_cost_usd"] > 0
    judge_requests = [r for r in fake.requests if r["output_format"] is JudgeResult]
    assert judge_requests[0]["model"] == "claude-haiku-5-5"
    assert judge_requests[0]["output_config"] == {"effort": "low"}
    trace = json.loads((tmp_path / "traces" / "KO_rep0.json").read_text(encoding="utf-8"))
    assert trace["synthesis"]["verdict"] == "CONDITIONAL_CASE" and trace["judge"]["status"] == "success"


def test_rerun_skips_attempts_already_done(fake_claude, ko_handler, tmp_path):
    fake = fake_claude(ko_handler)
    run_eval.run([LABELLED], 1, tmp_path, batch=False, concurrency=1)
    calls = len(fake.requests)
    run_eval.run([LABELLED], 2, tmp_path, batch=False, concurrency=1)
    assert len(run_eval.read_jsonl(tmp_path / "results.jsonl")) == 2
    assert len(fake.requests) == 2 * calls  # only rep 1 ran the second time


def test_an_attempt_without_a_verdict_is_an_error_row(fake_claude, ko_handler, tmp_path):
    from synthesis.committee import SynthesisResult

    def failing(request):
        if request["output_format"] is SynthesisResult:
            raise RuntimeError("outage")
        return ko_handler(request)

    fake_claude(failing)
    run_eval.run([LABELLED], 1, tmp_path, batch=False, concurrency=1)
    errors = run_eval.read_jsonl(tmp_path / "errors.jsonl")
    assert errors[0]["failure_class"] == "synthesis_failed" and errors[0]["cost_usd"] > 0
    assert not (tmp_path / "results.jsonl").exists()


def test_summary_reports_metrics_baselines_and_numbers(fake_claude, ko_handler, tmp_path):
    fake_claude(ko_handler)
    run_eval.run([LABELLED], 2, tmp_path, batch=False, concurrency=2)
    text = "\n".join(run_eval.summarize(tmp_path))
    for expected in (
        "primary hit",
        "must_find found",
        "no invented number",
        "error cost",
        "always WEAK_CASE",
        "stability of committee verdict",
        "number check: data_claims 10",
        "KO    rep1",
    ):
        assert expected in text, expected


def test_unlabelled_cases_still_run_without_verdict_grades(fake_claude, ko_handler, tmp_path):
    fake_claude(ko_handler)
    run_eval.run(
        [{"id": "KO", "fixture": "tests/fixtures/golden/KO"}], 1, tmp_path, batch=False, concurrency=1
    )
    grade = run_eval.read_jsonl(tmp_path / "results.jsonl")[0]["grade"]
    assert "primary_hit" not in grade and grade["all_valid"] == 1


def test_cases_with_a_private_ticker_are_refused(tmp_path, monkeypatch):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"id": "ZZZQ", "fixture": "x"}]), encoding="utf-8")
    monkeypatch.setattr(run_eval, "private_tickers", lambda: {"ZZZQ"})
    with pytest.raises(SystemExit, match="private"):
        run_eval.load_cases(path=path)


def test_the_case_file_lists_the_golden_tickers():
    assert [c["id"] for c in run_eval.load_cases()] == ["KO", "SNOW", "KHC"]
