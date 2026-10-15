"""
The prompt layout that makes prompt caching work: the shared prefix is the same
byte for byte in every request and comes first; everything perspective-specific
comes after it. Then the cache is written once and read by the others.
"""

from conftest import response

from core.fanout import run_parallel
from core.shared_context import context_block
from examples import minimal_run
from perspectives.perspective import Perspective, evaluate, shared_prefix

PERSPECTIVES = [
    Perspective("a", "Analyst A", "an analyst", "Question A?", ("Q1?", "Q2?")),
    Perspective("b", "Analyst B", "a skeptic", "Question B?", ("Q3?",)),
    Perspective("c", "Analyst C", "an accountant", "Question C?", ("Q4?",)),
]
PREFIX = shared_prefix("Rules for everyone.", context_block("data_pack", {"revenue": [1, 2, 3]}))


def run_all():
    return run_parallel([
        (p.name, lambda p=p: evaluate(p, PREFIX, minimal_run.Finding, minimal_run.validate_finding))
        for p in PERSPECTIVES
    ])


def good(kwargs):
    return response(minimal_run.Finding(summary="A sound, specific finding.", missing_data=[]))


def test_every_request_starts_with_the_identical_cached_prefix(fake_claude):
    fake = fake_claude(good)
    run_all()
    firsts = [r["system"][0] for r in fake.requests]
    assert all(block == {"type": "text", "text": PREFIX, "cache_control": {"type": "ephemeral"}}
               for block in firsts)


def test_perspective_specific_text_stays_after_the_breakpoint(fake_claude):
    fake = fake_claude(good)
    run_all()
    for request, perspective in zip(fake.requests, PERSPECTIVES, strict=True):
        assert perspective.role not in request["system"][0]["text"]
        assert perspective.role in request["system"][1]["text"]
        assert perspective.questions[0] in request["messages"][0]["content"]


def test_warm_up_writes_the_cache_once_and_the_others_read_it(fake_claude):
    fake_claude(good, simulate_cache=True)
    results = run_all()
    assert [r["status"] for r in results] == ["success"] * 3
    assert results[0]["cache_creation_input_tokens"] > 0
    assert all(r["cache_read_input_tokens"] > 0 and r["cache_creation_input_tokens"] == 0
               for r in results[1:])


def test_caching_off_sends_plain_system_text(fake_claude, monkeypatch):
    from perspectives import perspective as perspective_module
    monkeypatch.setattr(perspective_module, "PROMPT_CACHING", False)
    fake = fake_claude(good)
    evaluate(PERSPECTIVES[0], PREFIX, minimal_run.Finding, minimal_run.validate_finding)
    assert isinstance(fake.requests[0]["system"], str)


def test_a_failed_perspective_reports_its_error_and_billed_tokens(fake_claude):
    fake_claude(lambda kwargs: response(minimal_run.Finding(summary="x", missing_data=[]), input_tokens=7))
    result = evaluate(PERSPECTIVES[0], PREFIX, minimal_run.Finding, minimal_run.validate_finding)
    assert result["status"] == "error" and "summary too short" in result["error"]
    assert result["input_tokens"] == 14  # both rejected attempts are billed


def test_the_example_runs_end_to_end_with_the_fake_client(fake_claude):
    fake = fake_claude(good, simulate_cache=True)
    results = minimal_run.main()
    assert len(fake.requests) == 2
    assert {r["prefix_sha256"] for r in results} == {results[0]["prefix_sha256"]}
