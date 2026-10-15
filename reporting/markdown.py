"""
report.md: the committee's conclusion first, then the valuation math Python
computed, the evaluator reports as an appendix, data quality, the number check
and the cost. Nothing here depends on a fixed set of evaluators: sections come
from the results.
"""

from analysis.runner import AutopsyRun
from core.token_summary import format_cost

DISCLAIMER = (
    "Not investment advice. Stock Autopsy is a research-structuring and learning tool: it "
    "describes the strength of the evidence, never whether to buy, sell or hold."
)
VERDICT_WORDS = {
    "STRONG_CASE": "Strong case",
    "CONDITIONAL_CASE": "Conditional case",
    "INSUFFICIENT_DATA": "Insufficient data",
    "WEAK_CASE": "Weak case",
    "RED_FLAGGED": "Red-flagged",
}


def money(value) -> str:
    if value is None:
        return "unknown"
    sign = "-" if value < 0 else ""
    value = abs(value)
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if value >= limit:
            return f"{sign}${value / limit:,.2f}{suffix}"
    return f"{sign}${value:,.0f}"


def pct(value) -> str:
    return "unknown" if value is None else f"{value:.1%}"


def number(value, digits: int = 2) -> str:
    return "n/m" if value is None else f"{value:,.{digits}f}"


def bullets(items) -> list[str]:
    return [f"- {item}" for item in items] or ["- none"]


def table_row(*cells) -> str:
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def amount(field: str, value) -> str:
    """Restated values: share counts as numbers, everything else as money."""
    return f"{value:,}" if field == "shares_diluted" else money(value)


def header(run: AutopsyRun) -> list[str]:
    pack = run.pack
    price = pack["price"]
    price_text = f"{price['value']:,.2f} {price['currency']} (close {price['date']})" if price else "unknown"
    return [
        f"# Stock Autopsy: {pack['ticker']} — {pack['company_name']}",
        "",
        f"> {DISCLAIMER}",
        "",
        "| | |",
        "|---|---|",
        f"| Data as of | {pack['as_of']} |",
        f"| Price | {price_text} |",
        f"| Financial statements | {pack['sources']['financial_statements']} |",
        f"| Price source | {pack['sources']['price'] or 'not available'} |",
        f"| User context | horizon {pack['user_context']['horizon']}, "
        f"risk tolerance {pack['user_context']['risk_tolerance']} |",
        f"| Data pack SHA-256 | `{run.pack_hash}` |",
        f"| Model | {run.model} |",
        "",
    ]


def synthesis_section(run: AutopsyRun) -> list[str]:
    s = run.synthesis
    if s.get("status") != "success":
        return ["## Investment Committee", "", f"**No conclusion:** {s.get('error')}", ""]
    lines = [
        f"## Verdict: {VERDICT_WORDS[s['verdict']]} — confidence {s['confidence']}",
        "",
        s["confidence_reason"],
    ]
    if s["confidence_adjustments"]:
        lines += [
            "",
            f"Confidence lowered from {s['model_confidence']} by code: "
            + "; ".join(s["confidence_adjustments"])
            + ".",
        ]
    if s["conditions"]:
        lines += ["", "**Conditions:**", *bullets(s["conditions"])]
    lines += [
        "",
        "### Judge's summary",
        "",
        s["judge_summary"],
        "",
        f"Stronger side: **{s['stronger_side'].lower()}**.",
        "",
        "**Genuinely uncertain:**",
        *bullets(s["genuinely_uncertain"]),
        "",
        "**Rests on assumptions or unverified claims:**",
        *bullets(s["rests_on_assumptions"]),
        "",
        "### Committee debate",
        "",
        f"**Bull case.** {s['bull_case']}",
        "",
        f"**Bear case.** {s['bear_case']}",
        "",
        f"**Bull answers bear.** {s['bull_answers_bear']}",
        "",
        f"**Bear answers bull.** {s['bear_answers_bull']}",
        "",
        "### Conflict map",
        "",
    ]
    if s["conflicts"]:
        lines += ["| Between | Conflict | Nature | Explanation |", "|---|---|---|---|"]
        lines += [
            f"| {' vs '.join(c['between'])} | {c['description']} | {c['nature'].replace('_', ' ').lower()} "
            f"| {c['explanation']} |"
            for c in s["conflicts"]
        ]
    else:
        lines.append("No conflicts between the perspectives.")
    lines += ["", "### Monitoring plan", "", "| Watch | Threshold | From |", "|---|---|---|"]
    lines += [f"| {m['item']} | {m['threshold']} | {m['from_evaluator']} |" for m in s["monitoring_plan"]]
    lines += ["", "### Next research steps", ""]
    lines += [f"{n}. {step}" for n, step in enumerate(s["next_research_steps"], start=1)]
    lines += ["", "### In plain language", "", s["beginner_explanation"], ""]
    return lines


def valuation_section(run: AutopsyRun) -> list[str]:
    multiples = run.pack["derived"]["valuation"]
    lines = [
        "## Valuation math (computed by Python)",
        "",
        f"Multiples on {multiples['basis'] or 'no TTM basis'} (to {multiples['ttm_period_end']}), "
        f"price of {multiples['price_date']}.",
        "",
        "| Market cap | Enterprise value | P/E | EV/Revenue | EV/EBIT | EV/EBITDA | P/FCF | FCF yield |",
        "|---|---|---|---|---|---|---|---|",
        table_row(
            money(multiples["market_cap"]),
            money(multiples["enterprise_value"]),
            *(number(multiples[name]) for name in ("pe", "ev_revenue", "ev_ebit", "ev_ebitda", "p_fcf")),
            pct(multiples["fcf_yield"]),
        ),
    ]
    lines += ["", *bullets(multiples["notes"])] if multiples["notes"] else []
    math = run.valuation_math
    if not math.get("computed"):
        return [*lines, "", f"**DCF not computed:** {'; '.join(math.get('reasons', []))}", ""]
    values = math["value_per_share"]
    lines += [
        "",
        f"DCF value per share — bear {number(values['bear'])}, base {number(values['base'])}, "
        f"bull {number(values['bull'])}; price {number(math['price'])}. A range for testing assumptions, "
        "not a target price.",
        "",
        "| Scenario | Enterprise value | Equity value | Per share | Terminal value share of EV |",
        "|---|---|---|---|---|",
    ]
    for name, result in math["scenarios"].items():
        lines.append(
            table_row(
                name,
                money(result["enterprise_value"]),
                money(result["equity_value"]),
                number(result["value_per_share"]),
                pct(result["terminal_value_share_of_ev"]),
            )
        )
    reverse = math["reverse_dcf"]
    implied = reverse["implied_revenue_growth"]
    lines += [
        "",
        f"Reverse DCF: the price implies {pct(implied)} revenue growth a year for five years "
        f"(holding {reverse['holding']})."
        if implied is not None
        else f"Reverse DCF: {reverse['reason']}.",
        "",
        "| Assumption moved (base case) | Step | Value down | Value up |",
        "|---|---|---|---|",
    ]
    lines += [
        table_row(
            row["assumption"], f"±{row['step']:.1%}", number(row["value_down"]), number(row["value_up"])
        )
        for row in math["sensitivities"]
    ]
    lines += ["", *bullets(math["notes"])] if math["notes"] else []
    return [*lines, ""]


SECTION_FIELDS = {
    "business_summary": "Business",
    "segments": "Segments",
    "revenue_quality": "Revenue quality",
    "unit_economics": "Unit economics",
    "common_misunderstanding": "Common misunderstanding",
    "relative_valuation": "Relative valuation",
    "implied_expectations": "Implied expectations",
    "achievability": "Achievability",
    "most_sensitive_assumption": "Most sensitive assumption",
    "multiple_drivers": "Multiple drivers (12 months)",
    "poor_fit": "Poor fit",
    "red_flag_score_reason": "Red flag score",
}


def evaluator_section(result: dict) -> list[str]:
    title = f"### {result['label']}"
    if result["status"] != "success":
        return [title, "", f"**Failed:** {result['error']}", ""]
    lines = [title, ""]
    if "verdict" in result:
        lines += [
            f"**{result['verdict']}**, confidence {result['confidence']} — {result['confidence_reason']}",
            "",
            f"**Key finding.** {result['key_finding']}",
            "",
            f"**Biggest unknown.** {result['biggest_unknown']}",
            "",
            result["summary"],
            "",
        ]
    for name, heading in SECTION_FIELDS.items():
        if name in result:
            score = f" {result['red_flag_score']}/10." if name == "red_flag_score_reason" else ""
            lines += [f"**{heading}.**{score} {result[name]}", ""]
    if result.get("key_dependencies"):
        lines += ["**Key dependencies:**", *bullets(result["key_dependencies"]), ""]
    if "red_flags" in result:
        lines += [
            "| Flag | Evidence | Severity | Why it matters | Innocent explanation |",
            "|---|---|---|---|---|",
        ]
        fields = ("flag", "evidence", "severity", "why_it_matters", "innocent_explanation")
        lines += [table_row(*(f[name] for name in fields)) for f in result["red_flags"]] or [
            table_row("none", "", "", "", "")
        ]
        lines.append("")
    if result.get("failure_scenarios"):
        lines += ["**Failure scenarios:**", ""]
        lines += [
            f"{n}. **{s['scenario']}** {s['causal_chain']}"
            for n, s in enumerate(result["failure_scenarios"], start=1)
        ]
        lines += [
            "",
            "**Thesis invalidation criteria:**",
            *bullets(f"{c['signal']} ({c['metric']})" for c in result["invalidation_criteria"]),
            "",
            "**Shaky data:**",
            *bullets(result["shaky_data"]),
            "",
            "**Verify personally:**",
            *bullets(f"{c['fact']} — {c['where_to_find']}" for c in result["verification_checklist"]),
            "",
        ]
    if result.get("notes"):  # valuation step A
        lines += ["| Assumption | Reasoning | Anchor |", "|---|---|---|"]
        lines += [f"| {n['assumption']} | {n['reasoning']} | {n['anchor']} |" for n in result["notes"]]
        lines.append("")
    if result.get("claims"):
        lines += ["<details><summary>Claims</summary>", ""]
        lines += [f"- [{c['tag']}] {c['statement']} — *{c['basis']}*" for c in result["claims"]]
        lines += ["", "</details>", ""]
    return lines


def data_quality_section(run: AutopsyRun) -> list[str]:
    q = run.pack["data_quality"]
    lines = [
        "## Data quality",
        "",
        "Fetch status: " + ", ".join(f"{k} {v}" for k, v in q["fetch_status"].items()),
        "",
    ]
    if q["restated"]:
        lines += [
            "| Restated | Period | Original | Restated | Original filed | Restating filing |",
            "|---|---|---|---|---|---|",
        ]
        lines += [
            table_row(
                r["field"],
                r["period"],
                amount(r["field"], r["original"]),
                amount(r["field"], r["restated"]),
                r["original_filed"],
                f"{r['form']} {r['filed']}",
            )
            for r in q["restated"]
        ]
        lines.append("")
    lines += [
        "**Missing (unknown, not zero):**",
        *bullets(f"{m['field']}: {', '.join(m['periods'])} ({m['reason']})" for m in q["missing"]),
        "",
    ]
    if q["partial"]:
        lines += ["**Partial:**", *bullets(f"{p['field']}: {p['covers']}" for p in q["partial"]), ""]
    if q["source_conflicts"]:
        lines += [
            "**Source conflicts:**",
            *bullets(f"{c['field']}: {c['values']} (used {c['used']})" for c in q["source_conflicts"]),
            "",
        ]
    if q["period_notes"]:
        lines += ["**Notes:**", *bullets(q["period_notes"]), ""]
    return lines


def number_check_section(run: AutopsyRun) -> list[str]:
    check = run.number_check
    counts = ", ".join(f"{k} {v}" for k, v in sorted(check["counts"].items())) or "none"
    lines = [
        "## Number check",
        "",
        f"{check['data_claims']} DATA claims checked against the pack: {counts}.",
        "",
    ]
    if check["problems"]:
        lines += ["| Evaluator | Statement | Basis | Problem |", "|---|---|---|---|"]
        for p in check["problems"]:
            detail = p["status"]
            if p.get("unmatched"):
                detail += ": not in the cited values: " + ", ".join(f"{n:,g}" for n in p["unmatched"])
            if p.get("bad_paths"):
                detail += "; unknown paths: " + ", ".join(p["bad_paths"])
            lines.append(table_row(p["evaluator"], p["statement"], p["basis"], detail))
        lines.append("")
    return lines


def cost_section(run: AutopsyRun) -> list[str]:
    lines = [
        "## Cost",
        "",
        "| Call | Status | Input | Cache write | Cache read | Output |",
        "|---|---|---|---|---|---|",
    ]
    for call in run.calls:
        if "input_tokens" not in call:
            continue
        tokens = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
        lines.append(table_row(call["label"], call["status"], *(f"{call[name]:,}" for name in tokens)))
    lines += ["", f"Total: {format_cost(run.total_cost)}, {run.duration_s:.0f} s.", ""]
    return lines


def build_report(run: AutopsyRun) -> str:
    lines = header(run) + synthesis_section(run) + valuation_section(run)
    lines += ["## Analyst reports", ""]
    for result in run.results:
        lines += evaluator_section(result)
    lines += data_quality_section(run) + number_check_section(run) + cost_section(run)
    lines += ["---", "", DISCLAIMER, ""]
    return "\n".join(lines)
