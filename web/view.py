"""
The result of a web run as the page shows it: meanings in words, never codes.

Verdict and status codes stay only in the fields the page uses for logic and
colour (CODE_KEYS); every other string goes through reporting.wording.humanize(),
the same last pass as report.md, so model text cannot bring codes onto the screen.
"""

import re
from pathlib import Path

from analysis.runner import VERDICT_KEYS, AutopsyRun
from reporting.data_quality import quality_lines, statements_to
from reporting.markdown import money, number, pct
from reporting.wording import (
    CLAIM_TAGS,
    COMMITTEE_VERDICTS,
    CONFIDENCE,
    EVALUATOR_VERDICTS,
    EVALUATORS,
    company_display,
    company_heading,
    field,
    humanize,
    path_words,
)
from translate.languages import CODES, NATIVE_NAMES
from translate.translator import kept_sections
from web.runs import Run

CODE_KEYS = {"verdict", "status", "kind", "key", "check"}
# Fields of an evaluator result the cards show as text, in this order.
DETAIL_FIELDS = (
    "business_summary", "segments", "revenue_quality", "unit_economics", "common_misunderstanding",
    "relative_valuation", "implied_expectations", "achievability", "most_sensitive_assumption",
    "multiple_drivers", "poor_fit",
)
# How a checked number is shown: (check code for colour, words).
CHECKS = {
    "match": ("match", "matches the data pack built from the filings"),
    "group_match": ("weak", "found only somewhere in a cited table"),
    "partial": ("wrong", "some numbers are not in the cited data"),
    "mismatch": ("wrong", "not in the cited data"),
    "bad_path": ("wrong", "cites data that does not exist"),
    "reproduced": ("computed", "reproduced by code from the cited data"),
    "not_reproduced": ("weak", "could not be reproduced from the cited data"),
}
# report.json is still written to the run folder for programs; the page does not offer it.
DOWNLOADS = {"report": "report.md"}
# The file is saved under the company's name (download_name), so the label names only its type.
DOWNLOAD_LABELS = {"report": "Save report (.md)"}


def _words(value, ticker: str, company: str, key: str | None = None):
    if isinstance(value, str):
        return value if key in CODE_KEYS else humanize(value, ticker, company)
    if isinstance(value, dict):
        return {k: _words(v, ticker, company, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_words(v, ticker, company, key) for v in value]
    return value


def download_paths(run: Run) -> dict:
    if run.out_dir is None:
        return {}
    return {kind: run.out_dir / name for kind, name in DOWNLOADS.items() if (run.out_dir / name).exists()}


def run_view(run: Run) -> dict:
    if run.autopsy is None:
        return {"analyzed": False, "error": run.error}
    autopsy = run.autopsy
    pack = autopsy.pack
    company = company_display(pack["company_name"])
    view = {
        "analyzed": True,
        "error": None,
        "company": company,
        "company_heading": company_heading(pack["company_name"], autopsy.related_to),
        "as_of": pack["as_of"],
        "price": _price(pack),
        "statements_to": statements_to(pack),
        "committee": _committee(autopsy),
        "valuation": _valuation(autopsy),
        "evaluators": [_evaluator(r, autopsy) for r in autopsy.results],
        "data_quality": _data_quality(pack),
        "number_check": _number_check(autopsy),
        "downloads": [{"kind": k, "label": DOWNLOAD_LABELS[k]} for k in download_paths(run)],
        "cost_usd": round(run.cost_usd(), 4),
        "duration_s": round(autopsy.duration_s),
    }
    return _words(view, pack["ticker"], company)


def _price(pack: dict) -> str | None:
    price = pack.get("price")
    return f"{price['value']:,.2f} {price['currency']} (close {price['date']})" if price else None


def _committee(autopsy: AutopsyRun) -> dict:
    s = autopsy.synthesis
    if s.get("status") != "success":
        return {"ok": False, "text": f"No conclusion: {s.get('error')}"}
    return {
        "ok": True,
        "verdict": s["verdict"],
        "verdict_text": COMMITTEE_VERDICTS[s["verdict"]],
        "confidence_text": CONFIDENCE[s["confidence"]],
        "confidence_reason": s["confidence_reason"],
        "confidence_adjustments": s.get("confidence_adjustments", []),
        "headline": s.get("headline") or s["judge_summary"],
        "reasons_for": s.get("reasons_for", []),
        "reasons_against": s.get("reasons_against", []),
        "price_assumes": autopsy.valuation_math.get("price_assumes"),
        "conditions": s["conditions"],
        "unknowns": s["genuinely_uncertain"],
        "watch": [{"item": m["item"], "threshold": m["threshold"]} for m in s["monitoring_plan"]],
        "next_steps": s["next_research_steps"],
        "judge_summary": s["judge_summary"],
        "bull_case": s["bull_case"],
        "bear_case": s["bear_case"],
        "beginner_explanation": s["beginner_explanation"],
    }


def _valuation(autopsy: AutopsyRun) -> dict:
    multiples = autopsy.pack["derived"]["valuation"]
    math = autopsy.valuation_math
    rows = [
        ("Market value", money(multiples["market_cap"])),
        ("Price to earnings", number(multiples["pe"])),
        ("Enterprise value to revenue", number(multiples["ev_revenue"])),
        ("Free cash flow yield", pct(multiples["fcf_yield"])),
    ]
    view = {"multiples": [{"label": label, "value": value} for label, value in rows], "computed": False}
    if not math.get("computed"):
        view["reason"] = "; ".join(math.get("reasons", []))
        return view
    values = math["value_per_share"]
    implied = (math.get("implied_return") or {}).get("implied_annual_return")
    view.update({
        "computed": True,
        "per_share": [{"label": name, "value": number(values[name])} for name in ("bear", "base", "bull")],
        "price": number(math["price"]),
        "implied_return": pct(implied) if implied is not None else None,
        "implied_growth": pct(math["reverse_dcf"].get("implied_revenue_growth")),
        "implied_growth_label": _implied_growth_label(math["reverse_dcf"]),
    })
    return view


def _implied_growth_label(reverse: dict) -> str:
    """The implied growth with its condition: the return it earns (the base-case discount rate)."""
    if reverse.get("discount_rate") is None:
        return "Revenue growth the price implies"
    return f"Revenue growth for five years needed to earn {pct(reverse['discount_rate'])} a year"


def _checks_by_statement(autopsy: AutopsyRun) -> dict[str, str]:
    check = autopsy.number_check
    statuses = {c["statement"]: c["status"] for c in check.get("checked", [])}
    statuses.update({c["statement"]: c["status"] for c in check.get("derived", {}).get("checked", [])})
    return statuses


def _evaluator(result: dict, autopsy: AutopsyRun) -> dict:
    card = {"key": result["key"], "name": EVALUATORS.get(result["key"], result["label"]),
            "ok": result["status"] == "success"}
    if not card["ok"]:
        return {**card, "text": f"This analysis failed ({result.get('error')})."}
    statuses = _checks_by_statement(autopsy)
    claims = []
    for claim in result.get("claims", []):
        check = CHECKS.get(statuses.get(claim["statement"], ""))
        claims.append({
            "statement": claim["statement"],
            "tag": CLAIM_TAGS[claim["tag"]],
            "basis": "; ".join(path_words(p.strip()) for p in claim["basis"].split(";"))
            if claim["tag"] == "DATA" else claim["basis"],
            "check": check[0] if check else "none",
            "check_text": check[1] if check else None,
        })
    details = [
        {"label": field(name).capitalize(), "text": result[name]}
        for name in DETAIL_FIELDS
        if result.get(name)
    ]
    if result.get("key_dependencies"):
        details.append({"label": "Key dependencies", "text": "; ".join(result["key_dependencies"])})
    if result.get("red_flags") is not None:
        details += [
            {"label": f"Red flag, severity {f['severity']} of 5",
             "text": f"{f['flag']} Evidence: {f['evidence']} "
                     f"Innocent explanation: {f['innocent_explanation']}"}
            for f in result["red_flags"]
        ]
    for s in result.get("failure_scenarios", []):
        details.append({"label": "Failure scenario", "text": f"{s['scenario']} {s['causal_chain']}"})
    has_verdict = result["key"] in VERDICT_KEYS
    return {
        **card,
        "verdict": result.get("verdict") if has_verdict else None,
        "verdict_text": EVALUATOR_VERDICTS.get(result.get("verdict")) if has_verdict else None,
        "confidence_text": CONFIDENCE.get(result.get("confidence")) if has_verdict else None,
        "headline": result.get("key_finding") or "Assumptions for the bear, base and bull cases.",
        "summary": result.get("summary"),
        "biggest_unknown": result.get("biggest_unknown"),
        "details": details,
        "claims": claims,
    }


def _data_quality(pack: dict) -> list[str]:
    return quality_lines(pack)


def _number_check(autopsy: AutopsyRun) -> dict:
    check = autopsy.number_check
    counts = check["counts"]
    derived = check.get("derived", {}).get("counts", {})
    return {
        "data_claims": check["data_claims"],
        "match": counts.get("match", 0),
        "weak": counts.get("group_match", 0),
        "wrong": sum(counts.get(k, 0) for k in ("partial", "mismatch", "bad_path")),
        "computed": derived.get("reproduced", 0),
        "computed_claims": check.get("derived", {}).get("claims", 0),
        "absent_as_zero": [a["text"] for a in check.get("absent_as_zero", [])],
        "prose_unsourced": len(check.get("prose", {}).get("unsourced", [])),
        "prose_numbers": check.get("prose", {}).get("numbers", 0),
    }


def translation_view(outcome: dict, language: str, cost: float | None) -> dict:
    """A finished translation for the page: the Markdown to show and what happened, in words."""
    path = outcome["path"]
    markdown = path.read_text(encoding="utf-8")
    # Read back from the copy itself, so a translation made earlier names them too.
    kept = kept_sections(markdown)
    if outcome["reused"]:
        note = "This translation was made earlier; nothing was paid for it now."
    else:
        note = f"Translated in {outcome['duration_s']:.0f} s, about ${(cost or 0):.2f}."
    if kept:
        sections = "; ".join(f"{k['heading']} ({k['reason']})" for k in kept)
        note += (f" {len(kept)} section{'s' if len(kept) > 1 else ''} stayed in English and "
                 f"{'are' if len(kept) > 1 else 'is'} marked in the text: {sections}.")
    return {
        "language": language,
        "label": NATIVE_NAMES[language],
        "code": CODES[language],
        "markdown": markdown,
        "note": note,
        "download_label": f"Save report in {language} (.md)",
        "kept_in_english": len(kept),
        "cost_usd": round(cost or 0.0, 4),
    }


def recent_view(run: Run) -> dict:
    """One finished run in the "Recent analyses" list, in words (no ticker)."""
    autopsy = run.autopsy
    company = company_display(autopsy.pack["company_name"]) if autopsy else None
    synthesis = autopsy.synthesis if autopsy else {}
    if synthesis.get("status") == "success":
        outcome = COMMITTEE_VERDICTS[synthesis["verdict"]].split(":")[0]
    elif autopsy:
        outcome = "no conclusion"
    else:
        outcome = "stopped before the analysis"
    return {
        "run_id": run.id,
        "company": company or "A company that could not be analyzed",
        "analyzed": autopsy is not None,
        "verdict": synthesis.get("verdict"),
        "outcome": outcome,
        "finished": run.finished_at.strftime("%H:%M") if run.finished_at else None,
    }


MAX_NAME_IN_FILE = 40


def file_name_part(company: str) -> str:
    """'COCA COLA CO' -> 'Coca_Cola_Co', 'Yum! Brands, Inc.' -> 'Yum_Brands_Inc', at most 40 characters."""
    slug = re.sub(r"[^A-Za-z0-9-]+", "_", company_display(company)).strip("_")
    return slug[:MAX_NAME_IN_FILE].rstrip("_")


def download_name(run: Run, path: Path) -> str:
    """
    The name a downloaded file gets: the company first (reports avoid tickers, and a name
    reads better in a Downloads folder), then the run folder, which keeps the ticker for
    uniqueness (GOOGL and GOOG are one company) and the time: Coca_Cola_Co_KO_2026-10-17_090436_report.md.
    The folder in results/ keeps its ticker-first name.
    """
    company = run.autopsy.pack["company_name"] if run.autopsy else run.company
    prefix = file_name_part(company) if company else ""
    return f"{prefix + '_' if prefix else ''}{path.parent.name}_{path.name}"
