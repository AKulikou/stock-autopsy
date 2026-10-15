"""report.md is for people: no verdict codes, field names, pack paths, claim tags or tickers in it."""

import re

import pytest
from sample_outputs import handler_for, synthesis

from analysis.runner import run_autopsy
from datalayer.pack import build_pack
from reporting.markdown import build_report
from reporting.wording import company_display, humanize, path_words
from scripts.freeze_golden import FIXTURES, raw_from_fixture
from synthesis.committee import SynthesisResult

CODE_PATTERNS = {
    "verdict or status code": r"\b[A-Z]{2,}_[A-Z_]+\b",
    "enum word": r"\b(STRONG|ADEQUATE|WEAK|HIGH|MEDIUM|LOW|DATA|DERIVED|ASSUMPTION|UNVERIFIED"
    r"|BULL|BEAR|BALANCED)\b",
    "field name": r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b",
    "pack path": r"\b[a-z_]+\.[a-z_]+\.[A-Za-z0-9_]+",
    "claim tag": r"\[(DATA|DERIVED|ASSUMPTION|UNVERIFIED)\]",
}


def codes_in(text: str, ticker: str) -> dict[str, list[str]]:
    found = {name: sorted(set(re.findall(p, text))) for name, p in CODE_PATTERNS.items()}
    found["ticker"] = re.findall(rf"\b{ticker}\b", text)
    return {name: hits for name, hits in found.items() if hits}


@pytest.mark.parametrize("ticker", ["KO", "SNOW", "KHC"])
def test_the_report_holds_no_codes(fake_claude, ticker):
    raw = raw_from_fixture(FIXTURES / ticker)
    pack = build_pack(raw)[0]

    def red_flagged(p):
        result = synthesis("CONDITIONAL_CASE")
        result.bull_case += (
            " The Valuation=WEAK view and business_model vs pre_mortem [DATA] RED_FLAG for " + ticker
        )
        return result

    fake_claude(handler_for(pack, {SynthesisResult: red_flagged}))
    report = build_report(run_autopsy(raw))
    assert codes_in(report, ticker) == {}
    assert company_display(pack["company_name"]) in report


def test_codes_from_model_text_become_words():
    text = humanize(
        "Moat=STRONG vs Valuation=WEAK, see financials_annual.FY2025.revenue and FY2025Q3 [UNVERIFIED] "
        "(business_model vs pre_mortem), CONDITIONAL_CASE for KHC",
        "KHC",
        "Kraft Heinz Co",
    )
    assert text == (
        "Moat=strong vs Valuation=weak, see annual figures › FY2025 › revenue and Q3 FY2025 (unverified) "
        "(Business Model Analyst vs Pre-Mortem Analyst), conditional case for Kraft Heinz Co"
    )


def test_paths_and_names_in_words():
    assert (
        path_words("financials_quarterly.FY2026Q2.net_income") == "quarterly figures › Q2 FY2026 › net income"
    )
    assert path_words("filing_events.0.event") == "filing events › item 1 › event"
    assert company_display("COCA COLA CO") == "Coca Cola Co"
    assert company_display("Kraft Heinz Co") == "Kraft Heinz Co"


def test_ordinary_words_are_left_alone():
    text = "Revenue fell 3% in FY2024; the 10-K, P/E and EV/EBIT are standard terms. Item 4.02 matters."
    assert humanize(text, "KO", "Coca Cola Co") == text
