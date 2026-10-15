"""
report.md: the committee's conclusion first, then the valuation math Python
computed, the evaluator reports as an appendix, data quality, the number check
and the cost. Nothing here depends on a fixed set of evaluators: sections come
from the results.
"""

from analysis.runner import AutopsyRun
from core.token_summary import format_cost
from reporting.number_check import number_words
from reporting.wording import (
    CLAIM_TAGS,
    COMMITTEE_VERDICTS,
    CONFIDENCE,
    CONFLICT_NATURE,
    EVALUATOR_VERDICTS,
    EVALUATORS,
    FETCH_STATUS,
    MISSING_REASONS,
    NUMBER_STATUS,
    SOURCES,
    STRONGER_SIDE,
    company_display,
    field,
    humanize,
)

DISCLAIMER = (
    "Not investment advice. Stock Autopsy is a research-structuring and learning tool: it "
    "describes the strength of the evidence, never whether to buy, sell or hold."
)
PRICE_SOURCE = "Yahoo Finance, close of the last trading day before the data date"


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


def evaluator_name(key: str) -> str:
    return EVALUATORS.get(key, field(key))


def header(run: AutopsyRun) -> list[str]:
    pack = run.pack
    price = pack["price"]
    price_text = f"{price['value']:,.2f} {price['currency']} (close {price['date']})" if price else "unknown"
    return [
        f"# Stock Autopsy: {company_display(pack['company_name'])}",
        "",
        f"> {DISCLAIMER}",
        "",
        "| | |",
        "|---|---|",
        f"| Data as of | {pack['as_of']} |",
        f"| Price | {price_text} |",
        f"| Financial statements | SEC EDGAR financial data (XBRL) from filings made by {pack['as_of']} |",
        f"| Price source | {PRICE_SOURCE if price else 'not available'} |",
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
        f"## Verdict: {COMMITTEE_VERDICTS[s['verdict']]}",
        "",
        f"Confidence: {CONFIDENCE[s['confidence']]}.",
        "",
        s["confidence_reason"],
    ]
    if s["confidence_adjustments"]:
        lines += [
            "",
            f"Confidence lowered from {CONFIDENCE[s['model_confidence']]} by a fixed rule: "
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
        f"Stronger evidence: **{STRONGER_SIDE[s['stronger_side']]}**.",
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
            table_row(
                " vs ".join(evaluator_name(k) for k in c["between"]),
                c["description"],
                CONFLICT_NATURE[c["nature"]],
                c["explanation"],
            )
            for c in s["conflicts"]
        ]
    else:
        lines.append("No conflicts between the perspectives.")
    lines += ["", "### Monitoring plan", "", "| Watch | Threshold | From |", "|---|---|---|"]
    lines += [
        table_row(m["item"], m["threshold"], evaluator_name(m["from_evaluator"]))
        for m in s["monitoring_plan"]
    ]
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
            field(row["assumption"]),
            f"±{row['step']:.1%}",
            number(row["value_down"]),
            number(row["value_up"]),
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
            f"**Verdict: {EVALUATOR_VERDICTS[result['verdict']]}**, confidence "
            f"{CONFIDENCE[result['confidence']]}: {result['confidence_reason']}",
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
        lines += [f"- ({CLAIM_TAGS[c['tag']]}) {c['statement']} — *{c['basis']}*" for c in result["claims"]]
        lines += ["", "</details>", ""]
    return lines


def data_quality_section(run: AutopsyRun) -> list[str]:
    q = run.pack["data_quality"]
    lines = [
        "## Data quality",
        "",
        "Sources: "
        + ", ".join(
            f"{SOURCES.get(k, field(k))} {FETCH_STATUS.get(v, v)}" for k, v in q["fetch_status"].items()
        )
        + ".",
        "",
    ]
    if q["restated"]:
        lines += [
            "| Restated | Period | Original | Restated | Original filed | Restating filing |",
            "|---|---|---|---|---|---|",
        ]
        lines += [
            table_row(
                field(r["field"]),
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
        *bullets(
            f"{field(m['field'])}: {', '.join(m['periods'])} "
            f"({MISSING_REASONS.get(m['reason'], m['reason'])})"
            for m in q["missing"]
        ),
        "",
    ]
    if q["partial"]:
        lines += ["**Partial:**", *bullets(f"{field(p['field'])}: {p['covers']}" for p in q["partial"]), ""]
    if q["source_conflicts"]:
        lines += [
            "**Source conflicts:**",
            *bullets(
                f"{field(c['field'])}: SEC {c['values']['edgar']:,}, "
                f"Yahoo Finance {c['values']['yfinance']:,}; "
                "the SEC figure is used"
                for c in q["source_conflicts"]
            ),
            "",
        ]
    if q["period_notes"]:
        lines += ["**Notes:**", *bullets(q["period_notes"]), ""]
    return lines


def number_check_section(run: AutopsyRun) -> list[str]:
    check = run.number_check
    counts = (
        "; ".join(f"{v}: {NUMBER_STATUS.get(k, k)}" for k, v in sorted(check["counts"].items())) or "none"
    )
    lines = [
        "## Number check",
        "",
        f"{check['data_claims']} claims that quote the data were checked against it by code. {counts}.",
        "",
    ]
    if check["problems"]:
        lines += ["| Evaluator | Statement | Basis | Problem |", "|---|---|---|---|"]
        for p in check["problems"]:
            detail = NUMBER_STATUS.get(p["status"], p["status"])
            if p.get("unmatched"):
                detail += ": " + ", ".join(number_words(n) for n in p["unmatched"])
            if p.get("bad_paths"):
                detail += "; missing data cited: " + ", ".join(p["bad_paths"])
            lines.append(table_row(evaluator_name(p["evaluator"]), p["statement"], p["basis"], detail))
        lines.append("")
    return lines + grounding_lines(check)


PROSE_ROWS_SHOWN = 15


def unknown_words(hit: dict) -> str:
    """'FY2019, FY2020: not reported in the filings' for each reason the value is unknown."""
    return "; ".join(
        f"{', '.join(u['periods'])}: {MISSING_REASONS.get(u['reason'], u['reason'])}" for u in hit["unknown"]
    )


def grounding_lines(check: dict) -> list[str]:
    """Calculated claims, numbers in the text, and unknowns stated as zero (reporting/grounding.py)."""
    lines = []
    derived = check.get("derived")
    if derived and derived["claims"]:
        reproduced = derived["counts"].get("reproduced", 0)
        lines += [
            f"**Calculated claims:** {reproduced} of {derived['claims']} could be reproduced by code "
            "from the data they cite.",
            "",
        ]
        if derived["problems"]:
            lines += ["| Evaluator | Statement | Not reproduced |", "|---|---|---|"]
            for p in derived["problems"]:
                numbers = ", ".join(number_words(n) for n in p.get("unexplained", []))
                lines.append(table_row(evaluator_name(p["evaluator"]), p["statement"], numbers))
            lines += ["", "Not reproduced does not mean wrong: the calculation may take several steps.", ""]
    absent = check.get("absent_as_zero", [])
    if absent:
        lines += [
            "**Unknown values stated as zero or none.** The data does not say these are zero; check them:",
            "",
            "| Source | Text | Unknown in the data |",
            "|---|---|---|",
            *(
                table_row(
                    evaluator_name(a["source"]),
                    a["text"],
                    f"{field(a['missing_field'])} ({unknown_words(a)})",
                )
                for a in absent
            ),
            "",
        ]
    prose = check.get("prose")
    if prose and prose["unsourced"]:
        shown = prose["unsourced"][:PROSE_ROWS_SHOWN]
        lines += [
            f"**Numbers in the text without a source:** {len(prose['unsourced'])} of {prose['numbers']} "
            "numbers in the analysts' and the committee's text appear neither in the data, the valuation "
            "math nor any tagged claim. Often they are the text's own arithmetic or assumptions; treat "
            "them as unverified.",
            "",
            "| Source | Number | Text |",
            "|---|---|---|",
            *(table_row(evaluator_name(u["source"]), u.get("shown") or number_words(u["number"]), u["text"])
              for u in shown),
            "",
        ]
        if len(prose["unsourced"]) > len(shown):
            lines += [f"{len(prose['unsourced']) - len(shown)} more are listed in report.json.", ""]
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
    pack = run.pack
    return humanize("\n".join(lines), pack["ticker"], company_display(pack["company_name"]))
