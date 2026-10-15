"""
Eval runner for Stock Autopsy: real runs of the whole pipeline on the frozen
golden packs (tests/fixtures/golden), no network apart from the Claude API.

    python -m eval.run_eval --reps 2                      # all cases, 2 reps each
    python -m eval.run_eval --cases KHC --reps 1          # one case
    python -m eval.run_eval --reps 2 --batch              # Message Batches: half price, minutes per stage
    python -m eval.run_eval --variant baseline --summary-only

Output (git-ignored), one folder per variant:

    .claude/hillclimb/stock/<variant>/results.jsonl   one row per (case, rep)
    .claude/hillclimb/stock/<variant>/errors.jsonl    attempts without a committee verdict
    .claude/hillclimb/stock/<variant>/traces/<id>_rep<k>.json

Rows are written as each attempt finishes, and a rerun skips (case, rep) pairs that
already have a row, so an interrupted run can simply be restarted. With --batch all
attempts start at once so their requests share batches.

Graded by code: committee verdict against the labels (primary hit, acceptable range,
error cost), Forensic verdict against forbidden ones, all answers valid, number check
(matched, bad paths, invented numbers), cache read share, tokens and cost. Graded by
the judge (eval/judge.py): must_find and must_not statements, with verbatim evidence.
"""

import argparse
import json
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.runner import AutopsyRun, run_autopsy  # noqa: E402
from config import ANALYSIS_EFFORT, MODEL, PROMPT_CACHING, THINKING  # noqa: E402
from core.claude_client import use_batches  # noqa: E402
from core.token_summary import total_input  # noqa: E402
from eval import grading as g  # noqa: E402
from eval.judge import JUDGE_EFFORT, JUDGE_MODEL, judge_report  # noqa: E402
from scripts.check_private_tickers import private_tickers  # noqa: E402
from scripts.freeze_golden import raw_from_fixture  # noqa: E402

CASES_FILE = ROOT / "eval" / "cases.json"
OUTPUT = ROOT / ".claude" / "hillclimb" / "stock"
BINARY_METRICS = (
    ("primary_hit", "primary hit"),
    ("in_range", "acceptable"),
    ("flaw_found", "must_find found"),
    ("must_not_ok", "no must_not"),
    ("forensic_ok", "forensic ok"),
    ("all_valid", "all answers valid"),
    ("no_invented", "no invented number"),
)
RUN_SETTINGS = {
    "model": MODEL,
    "effort": ANALYSIS_EFFORT,
    "thinking": THINKING,
    "prompt_caching": PROMPT_CACHING,
    "judge_model": JUDGE_MODEL,
    "judge_effort": JUDGE_EFFORT,
    "batch": False,
}
write_lock = threading.Lock()


class CaseError(Exception):
    """An attempt without a committee verdict; its cost is still recorded."""

    def __init__(self, failure_class: str, message: str, cost: float = 0.0):
        super().__init__(message)
        self.failure_class = failure_class
        self.cost = cost


def load_cases(only: set[str] | None = None, path: Path = CASES_FILE) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    private = {c["id"] for c in cases} & private_tickers()
    if private:
        raise SystemExit("eval/cases.json lists a private research ticker; remove it")
    if only:
        unknown = only - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"Unknown case ids: {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in only]
    return cases


def usage_totals(calls: list[dict]) -> dict:
    billed = [c for c in calls if "input_tokens" in c]
    return {
        "input_tokens": sum(total_input(c) for c in billed),
        "uncached_input_tokens": sum(c["input_tokens"] for c in billed),
        "cache_write_tokens": sum(c.get("cache_creation_input_tokens", 0) for c in billed),
        "cache_read_tokens": sum(c.get("cache_read_input_tokens", 0) for c in billed),
        "output_tokens": sum(c["output_tokens"] for c in billed),
    }


def grade_run(case: dict, run: AutopsyRun, judged: dict) -> tuple[dict, dict]:
    """(grade, meta) of one attempt; pure apart from reading the run."""
    synthesis = run.synthesis
    forensic = run.result("forensic")
    roots = {**run.pack, "valuation_math": run.valuation_math}
    invented = g.invented_numbers(run.number_check, roots)
    numbers = g.number_summary(run.number_check, invented)
    grade = {
        **g.grade_verdict(synthesis["verdict"], case),
        **g.grade_forensic(forensic, case),
        "all_valid": int(all(r["status"] == "success" for r in run.calls)),
        "no_invented": int(not invented),
    }
    for metric in ("flaw_found", "must_not_ok"):
        if metric in judged:
            grade[metric] = judged[metric]
    usage = usage_totals(run.calls)
    meta = {
        "verdict": synthesis["verdict"],
        "confidence": synthesis["confidence"],
        "model_confidence": synthesis.get("model_confidence"),
        "primary": case.get("primary"),
        "expected": g.allowed_verdicts(case),
        "statuses": {r["key"]: r["status"] for r in run.results},
        "evaluator_verdicts": {r["key"]: r.get("verdict") for r in run.results if r["status"] == "success"},
        "forensic_verdict": forensic.get("verdict") if forensic and forensic["status"] == "success" else None,
        "forensic_score": forensic.get("red_flag_score")
        if forensic and forensic["status"] == "success"
        else None,
        "forensic_max_severity": (
            max((f["severity"] for f in forensic["red_flags"]), default=0)
            if forensic and forensic["status"] == "success"
            else None
        ),
        "numbers": numbers,
        "invented": invented,
        "cache_read_share": round(usage["cache_read_tokens"] / usage["input_tokens"], 4)
        if usage["input_tokens"]
        else 0.0,
        "judge": {k: judged[k] for k in ("status", "checks", "error") if k in judged},
    }
    return grade, meta


def run_case(case: dict) -> tuple[dict, dict, dict]:
    """(grade, meta, trace) of one attempt. Raises CaseError without a committee verdict."""
    raw = raw_from_fixture(ROOT / case["fixture"])
    run = run_autopsy(raw, case.get("user_context"))
    trace = {
        "pack_sha256": run.pack_hash,
        "results": run.results,
        "valuation_math": run.valuation_math,
        "synthesis": run.synthesis,
        "number_check": run.number_check,
    }
    run_cost = run.total_cost or 0.0
    if run.synthesis.get("status") != "success":
        raise CaseError("synthesis_failed", run.synthesis.get("error", "no verdict"), run_cost)
    judged = judge_report(case, run.synthesis, run.result("forensic"))
    trace["judge"] = judged
    grade, meta = grade_run(case, run, judged)
    usage = usage_totals(run.calls)
    meta.update({"usage": usage, "run_cost_usd": run_cost, "judge_cost_usd": judged.get("cost_usd", 0.0)})
    return grade, meta, trace


def append_jsonl(path: Path, row: dict) -> None:
    with write_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run_one(case: dict, rep: int, out: Path) -> str:
    started = time.monotonic()
    try:
        grade, meta, trace = run_case(case)
    except CaseError as e:
        append_jsonl(
            out / "errors.jsonl",
            {
                "case_id": case["id"],
                "rep": rep,
                "failure_class": e.failure_class,
                "error": str(e),
                "cost_usd": e.cost,
                **RUN_SETTINGS,
            },
        )
        return f"ERROR {e.failure_class}: {e}"
    except Exception as e:  # anything else is a bug or an outage: record it, keep the other attempts
        append_jsonl(
            out / "errors.jsonl",
            {
                "case_id": case["id"],
                "rep": rep,
                "failure_class": "exception",
                "error": f"{type(e).__name__}: {e}",
                "cost_usd": 0.0,
                **RUN_SETTINGS,
            },
        )
        return f"ERROR exception: {type(e).__name__}: {e}"
    (out / "traces" / f"{case['id']}_rep{rep}.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    append_jsonl(
        out / "results.jsonl",
        {
            "case_id": case["id"],
            "rep": rep,
            "grade": grade,
            "meta": meta,
            **RUN_SETTINGS,
            "cost_usd": round(meta["run_cost_usd"] + meta["judge_cost_usd"], 4),
            "latency_s": round(time.monotonic() - started, 1),
        },
    )
    return f"{meta['verdict']} forensic={meta['forensic_verdict']} " + " ".join(
        f"{k}={v}" for k, v in grade.items()
    )


def summary_lines(rows: list[dict], errors: list[dict]) -> list[str]:
    lines = [f"{len(rows)} scored attempts, {len(errors)} without a verdict"]
    for metric, label in BINARY_METRICS:
        values = [r["grade"][metric] for r in rows if metric in r["grade"]]
        if values:
            lo, hi = g.wilson(sum(values), len(values))
            lines.append(f"  {label:<20} {sum(values)}/{len(values)}  (95% CI {lo:.0%}-{hi:.0%})")
    costs = [r["grade"]["error_cost"] for r in rows if "error_cost" in r["grade"]]
    if costs:
        lines.append(f"  {'error cost':<20} {sum(costs) / len(costs):.2f} mean (0 = primary verdict)")
        labelled_rows = [r for r in rows if r["meta"].get("primary")]
        base = g.labelled_baselines(
            [r["meta"]["primary"] for r in labelled_rows], [r["meta"]["expected"] for r in labelled_rows]
        )
        n = base["n"]
        lines.append(f"  reference (trivial answers on the same {n} attempts):")
        for verdict, b in base["always"].items():
            lines.append(
                f"    always {verdict:<18} primary {b['primary_hits']}/{n}, acceptable "
                f"{b['in_range']}/{n}, error cost {b['mean_cost']:.2f}"
            )
        r = base["random"]
        lines.append(
            f"    random verdict            primary {r['primary_hits']:.1f}/{n}, acceptable "
            f"{r['in_range']:.1f}/{n}, error cost {r['mean_cost']:.2f} (expected values)"
        )
    for key, label in (("verdict", "committee verdict"), ("forensic_verdict", "forensic verdict")):
        stab = g.stability(rows, key)
        if stab["cases"]:
            lines.append(
                f"  stability of {label}: changed in {len(stab['changed_cases'])}/{stab['cases']} cases "
                f"({', '.join(stab['changed_cases']) or '-'}), pair disagreement "
                f"{stab['pairwise_disagreement']:.2f}, cross-side {stab.get('cross_side_cases') or '-'}"
            )
    totals = {
        k: sum(r["meta"]["numbers"][k] for r in rows)
        for k in ("data_claims", "matched", "partial", "mismatch", "bad_path", "no_number", "invented")
    }
    lines.append("  number check: " + ", ".join(f"{k} {v}" for k, v in totals.items()))
    if rows:
        share = sum(r["meta"]["cache_read_share"] for r in rows) / len(rows)
        tokens_in = sum(r["meta"]["usage"]["input_tokens"] for r in rows)
        tokens_out = sum(r["meta"]["usage"]["output_tokens"] for r in rows)
        lines.append(
            f"  tokens: {tokens_in:,} in ({share:.0%} read from cache on average) / {tokens_out:,} out"
        )
    cost = sum(r["cost_usd"] for r in rows) + sum(e.get("cost_usd") or 0 for e in errors)
    lines.append(
        f"  cost ${cost:.2f} (judge ${sum(r['meta']['judge_cost_usd'] for r in rows):.3f}; "
        "failed attempts included)"
    )
    lines.append("  attempts:")
    for r in sorted(rows, key=lambda r: (r["case_id"], r["rep"])):
        m = r["meta"]
        lines.append(
            f"    {r['case_id']:<5} rep{r['rep']} {m['verdict']:<17} {m['confidence']:<6} forensic "
            f"{m['forensic_verdict']}/{m['forensic_score']} sev{m['forensic_max_severity']} numbers "
            f"{m['numbers']['matched']}/{m['numbers']['data_claims']} invented {m['numbers']['invented']} "
            f"cache {m['cache_read_share']:.0%} ${r['cost_usd']:.2f}"
        )
    return lines


def summarize(out: Path) -> list[str]:
    lines = summary_lines(read_jsonl(out / "results.jsonl"), read_jsonl(out / "errors.jsonl"))
    print("\n".join(lines))
    return lines


def run(cases: list[dict], reps: int, out: Path, batch: bool, concurrency: int) -> None:
    (out / "traces").mkdir(parents=True, exist_ok=True)
    done = {(r["case_id"], r["rep"]) for r in read_jsonl(out / "results.jsonl")}
    jobs = [(c, rep) for c in cases for rep in range(reps) if (c["id"], rep) not in done]
    print(
        f"{out.name}: {len(jobs)} attempts to run "
        f"({len(cases)} cases x {reps} reps, {len(done)} already done)"
    )
    if batch:
        use_batches()
        RUN_SETTINGS["batch"] = True
        concurrency = max(len(jobs), 1)
        print("batch mode: all attempts at once, requests sent as Message Batches")
    print(", ".join(f"{k}={v}" for k, v in RUN_SETTINGS.items()))
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(concurrency, 1)) as pool:
        futures = {pool.submit(run_one, c, rep, out): (c, rep) for c, rep in jobs}
        for future, (case, rep) in futures.items():
            print(f"  {case['id']} rep{rep}: {future.result()}")
    print(f"wall time {time.monotonic() - started:.0f}s")


def rejudge(out: Path, cases: list[dict]) -> int:
    """
    Run the judge again on the stored traces with the current case statements, and
    update flaw_found / must_not_ok and the judge part of each row. No pipeline call:
    a statement reworded after a run is checked again for a fraction of a cent.
    Returns the number of rows rejudged.
    """
    by_id = {c["id"]: c for c in cases}
    rows = read_jsonl(out / "results.jsonl")
    updated = 0
    for row in rows:
        case = by_id.get(row["case_id"])
        trace_path = out / "traces" / f"{row['case_id']}_rep{row['rep']}.json"
        if case is None or not trace_path.exists():
            continue
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        forensic = next((r for r in trace["results"] if r["key"] == "forensic"), None)
        judged = judge_report(case, trace["synthesis"], forensic)
        for metric in ("flaw_found", "must_not_ok"):
            row["grade"].pop(metric, None)
            if metric in judged:
                row["grade"][metric] = judged[metric]
        row["meta"]["judge"] = {k: judged[k] for k in ("status", "checks", "error") if k in judged}
        row["meta"]["judge_cost_usd"] = round(
            row["meta"].get("judge_cost_usd", 0.0) + judged.get("cost_usd", 0.0), 6
        )
        row["cost_usd"] = round(row["meta"]["run_cost_usd"] + row["meta"]["judge_cost_usd"], 4)
        trace["judge"] = judged
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding="utf-8")
        updated += 1
    (out / "results.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    return updated


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--cases", help="comma-separated case ids (default: all)")
    parser.add_argument("--batch", action="store_true", help="Message Batches API (half price, slower)")
    parser.add_argument("--concurrency", type=int, default=1, help="attempts at once without --batch")
    parser.add_argument(
        "--summary-only", action="store_true", help="summarize an existing variant, run nothing"
    )
    parser.add_argument(
        "--rejudge",
        action="store_true",
        help="rerun only the judge on the stored traces (current statements)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="  %(name)s: %(message)s")
    out = OUTPUT / args.variant
    if args.rejudge:
        print(f"rejudged {rejudge(out, load_cases())} attempts of {out.name}")
    elif not args.summary_only:
        cases = load_cases(set(args.cases.split(",")) if args.cases else None)
        run(cases, args.reps, out, args.batch, args.concurrency)
    summarize(out)


if __name__ == "__main__":
    main()
