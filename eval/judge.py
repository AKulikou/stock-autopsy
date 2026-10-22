"""
Did the report find what it must, and avoid what it must not?

A verdict can be right for the wrong reason. Each case lists findings the report
must contain (`must_find`, e.g. KHC's 2019 restatement) and things it must not do
(`must_not`). One cheap call per report checks each statement against the
committee's text and the Forensic report, with a verbatim quote as evidence. Code
then checks that every quote of a statement judged present really occurs in the
report: a judge cannot invent its evidence.
"""

import re
import time
from typing import Literal

from pydantic import BaseModel, Field

from core.claude_client import get_client
from core.structured_call import billed_usage, request_structured
from core.token_summary import call_cost

JUDGE_MODEL = "claude-haiku-5-5"
JUDGE_EFFORT = "low"
JUDGE_LABEL = "Eval judge"
JUDGE_MAX_TOKENS = 8000
# The judge decides each statement by majority of this many independent answers: one
# answer flipped borderline statements between passes on identical text (first eval baseline).
JUDGE_VOTES = 3

JUDGE_PRINCIPLES = """\
You check a stock analysis report against a list of statements. For each statement,
decide whether the report contains it.

- kind must_find: present means the report states this finding or its clear substance
  (other wording, the same point). A vaguer or merely related remark does not count:
  'accounting history may be a concern' does not contain 'the 2019 restatement of
  2016-2017 figures'.
- kind must_not: present means the report does the thing described. Mentioning it only
  to reject it is not present.
- evidence: a verbatim quote from the report, copied exactly, that decides it; 'none'
  when the statement is not present.
- Judge only the report text given. Do not use your own knowledge of the company.
"""


class StatementCheck(BaseModel):
    index: int = Field(description="The statement's number as given in the input.")
    kind: Literal["must_find", "must_not"]
    present: bool
    evidence: str = Field(description="A verbatim quote from the report, or 'none'.")


class JudgeResult(BaseModel):
    checks: list[StatementCheck]


def statements(case: dict) -> list[tuple[str, str]]:
    return [("must_find", s) for s in case.get("must_find", [])] + [
        ("must_not", s) for s in case.get("must_not", [])
    ]


def report_text(synthesis: dict, forensic: dict | None) -> str:
    """What the judge reads: the committee's conclusion and the Forensic report."""
    parts = [
        "COMMITTEE",
        f"Verdict: {synthesis['verdict']} (confidence {synthesis['confidence']})",
        f"Judge's summary: {synthesis['judge_summary']}",
        f"Bull case: {synthesis['bull_case']}",
        f"Bear case: {synthesis['bear_case']}",
        "Conflicts:\n"
        + "\n".join(f"- {c['description']} {c['explanation']}" for c in synthesis["conflicts"]),
        "Genuinely uncertain:\n" + "\n".join(f"- {u}" for u in synthesis["genuinely_uncertain"]),
        "Next research steps:\n" + "\n".join(f"- {s}" for s in synthesis["next_research_steps"]),
    ]
    if forensic and forensic.get("status") == "success":
        flags = "\n".join(
            f"- [{f['severity']}] {f['flag']}: {f['evidence']} "
            f"Innocent explanation: {f['innocent_explanation']}"
            for f in forensic["red_flags"]
        )
        parts += [
            "FORENSIC ACCOUNTANT",
            f"Verdict: {forensic['verdict']}. Key finding: {forensic['key_finding']}",
            f"Summary: {forensic['summary']}",
            f"Red flags:\n{flags}",
            f"Red flag score {forensic['red_flag_score']}/10: {forensic['red_flag_score_reason']}",
        ]
    return "\n\n".join(parts)


def judge_user_prompt(case: dict, text: str) -> str:
    listed = "\n".join(f"{i}. [{kind}] {s}" for i, (kind, s) in enumerate(statements(case), start=1))
    return f"<report>\n{text}\n</report>\n\nStatements:\n{listed}"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


def quote_in_report(quote: str, text: str) -> bool:
    """Every part of the quote (split at '...') occurs verbatim in the report, ignoring case and spacing."""
    report = _normalize(text)
    parts = [_normalize(p).strip("'\"") for p in re.split(r"\.\.\.|…", quote)]
    parts = [p for p in parts if p]
    return bool(parts) and all(p in report for p in parts)


def judge_validator(expected: list[tuple[str, str]], text: str):
    def validate(result: JudgeResult) -> list[str]:
        problems = []
        answered = sorted(c.index for c in result.checks)
        if answered != list(range(1, len(expected) + 1)):
            problems.append(f"statements answered {answered}, expected 1..{len(expected)}")
        for check in result.checks:
            if 1 <= check.index <= len(expected) and check.kind != expected[check.index - 1][0]:
                problems.append(f"statement {check.index} has kind {check.kind}")
            if check.present and not quote_in_report(check.evidence, text):
                problems.append(
                    f"statement {check.index}: the evidence is not a verbatim quote of the report "
                    f"({check.evidence[:80]!r})"
                )
        return problems

    return validate


def judge_report(case: dict, synthesis: dict, forensic: dict | None) -> dict:
    """
    Check a run against the case's statements. Never raises. Returns {"status":
    "success", "flaw_found": 0/1, "must_not_ok": 0/1 (each only if the case has such
    statements), "checks": [...], tokens, "cost_usd"} or {"status": "error"|"skipped", ...}.
    """
    expected = statements(case)
    if not expected:
        return {"status": "skipped"}
    text = report_text(synthesis, forensic)
    started = time.monotonic()
    base = {"key": "judge", "label": JUDGE_LABEL, "model": JUDGE_MODEL}
    ballots, errors, usage = [], [], {}
    for _ in range(JUDGE_VOTES):
        try:
            response = request_structured(
                get_client(),
                label=JUDGE_LABEL,
                model=JUDGE_MODEL,
                max_tokens=JUDGE_MAX_TOKENS,
                system=JUDGE_PRINCIPLES,
                user=judge_user_prompt(case, text),
                output_format=JudgeResult,
                validate=judge_validator(expected, text),
                effort=JUDGE_EFFORT,
            )
        except Exception as e:
            spent = billed_usage(e)
            spent.pop("rejected_output", None)
            errors.append(f"{type(e).__name__}: {e}")
        else:
            spent = response.usage.as_dict()
            ballots.append({c.index: c for c in response.result.checks})
        for key, value in spent.items():
            usage[key] = usage.get(key, 0) + value
    cost = call_cost({**base, **usage}) if usage else 0.0
    if not ballots:
        return {
            **base,
            "status": "error",
            "error": "; ".join(errors),
            **usage,
            "cost_usd": cost,
            "duration_s": time.monotonic() - started,
        }
    checks = []
    for index, (kind, s) in enumerate(expected, start=1):
        votes = [b[index] for b in ballots]
        present = sum(v.present for v in votes) * 2 > len(votes)
        evidence = next((v.evidence for v in votes if v.present == present), "none")
        checks.append(
            {
                "kind": kind,
                "statement": s,
                "present": present,
                "evidence": evidence,
                "votes": f"{sum(v.present for v in votes)}/{len(votes)} present",
            }
        )
    result = {
        **base,
        "status": "success",
        "checks": checks,
        "ballots": len(ballots),
        **usage,
        "cost_usd": cost,
        "duration_s": time.monotonic() - started,
    }
    if case.get("must_find"):
        result["flaw_found"] = int(all(c["present"] for c in checks if c["kind"] == "must_find"))
    if case.get("must_not"):
        result["must_not_ok"] = int(not any(c["present"] for c in checks if c["kind"] == "must_not"))
    return result
