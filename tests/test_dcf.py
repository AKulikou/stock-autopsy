import pytest

from evaluators.paths import PathError, resolve
from evaluators.schemas import ScenarioAssumptions
from reporting.number_check import quantities
from valuation.dcf import (
    DcfInputs,
    implied_annual_return,
    inputs_from_pack,
    price_assumes,
    project,
    reverse_dcf,
    run_valuation,
    sensitivities,
)

INPUTS = DcfInputs(revenue=100.0, shares=10.0, total_debt=20.0, cash_and_investments=5.0, price=50.0)


def flat(growth=0.0, margin=0.2, r=0.1, g=0.0) -> ScenarioAssumptions:
    return ScenarioAssumptions(
        revenue_growth=[growth] * 5,
        operating_margin=[margin] * 5,
        tax_rate=0.25,
        capex_pct_revenue=0.05,
        da_pct_revenue=0.05,
        nwc_pct_revenue_change=0.0,
        discount_rate=r,
        terminal_growth=g,
    )


def test_no_growth_no_reinvestment_is_a_perpetuity():
    # FCFF = 100 * 20% * (1 - 25%) = 15 every year; at 10% with no growth the firm is worth 150.
    result = project(flat(), INPUTS)
    assert result["enterprise_value"] == 150
    assert result["equity_value"] == 150 - 20 + 5
    assert result["value_per_share"] == pytest.approx(13.5)


def test_a_loss_gets_no_tax_credit():
    years = project(flat(margin=-0.1), INPUTS)["years"]
    assert years[0]["fcff"] == -10


def test_growth_raises_value_and_reinvestment_lowers_it():
    base = project(flat(), INPUTS)["value_per_share"]
    assert project(flat(growth=0.05), INPUTS)["value_per_share"] > base
    reinvesting = flat().model_copy(update={"capex_pct_revenue": 0.08})
    assert project(reinvesting, INPUTS)["value_per_share"] < base


def test_reverse_dcf_finds_the_growth_that_reproduces_the_price():
    base = flat(margin=0.3)
    price = project(flat(growth=0.12, margin=0.3), INPUTS)["value_per_share"]
    result = reverse_dcf(base, DcfInputs(**{**INPUTS.__dict__, "price": price}))
    assert result["implied_revenue_growth"] == pytest.approx(0.12, abs=1e-3)


def test_reverse_dcf_says_why_when_no_growth_reaches_the_price():
    result = reverse_dcf(flat(margin=0.01), DcfInputs(**{**INPUTS.__dict__, "price": 10_000.0}))
    assert result["implied_revenue_growth"] is None and "no constant growth" in result["reason"]


def test_implied_return_is_the_rate_at_which_the_base_case_equals_the_price():
    price = project(flat(r=0.08), INPUTS)["value_per_share"]
    result = implied_annual_return(flat(r=0.12), DcfInputs(**{**INPUTS.__dict__, "price": price}))
    assert result["implied_annual_return"] == pytest.approx(0.08, abs=1e-3)  # independent of the chosen 12%


def test_implied_return_says_when_the_price_is_out_of_reach():
    expensive = implied_annual_return(flat(), DcfInputs(**{**INPUTS.__dict__, "price": 10_000.0}))
    assert expensive["implied_annual_return"] is None and "worth less than the price" in expensive["reason"]
    cheap = implied_annual_return(flat(), DcfInputs(**{**INPUTS.__dict__, "price": 0.01}))
    assert cheap["implied_annual_return"] is None and "even at a return of 50%" in cheap["reason"]


def test_the_price_sentence_is_written_by_python():
    price = project(flat(r=0.08), INPUTS)["value_per_share"]
    inputs = DcfInputs(**{**INPUTS.__dict__, "price": price})
    sentence = price_assumes(flat(), inputs, implied_annual_return(flat(), inputs))
    assert sentence.endswith("a buyer earns about 8.0% a year.")
    assert "revenue growth of 0% to 0% a year and an operating margin of 20% to 20%" in sentence


def test_sensitivities_are_sorted_by_effect():
    rows = sensitivities(flat(g=0.02), INPUTS)
    effects = [row["largest_change_per_share"] for row in rows]
    assert effects == sorted(effects, reverse=True)
    assert {row["assumption"] for row in rows} == {
        "discount_rate",
        "terminal_growth",
        "operating_margin",
        "revenue_growth",
    }


def test_unknown_debt_stops_the_dcf_with_a_reason_not_a_zero():
    pack = {
        "ttm": {"revenue": 100},
        "shares_outstanding": {"value": 10},
        "balance_sheet_latest": {"total_debt": None, "cash": 5, "short_term_investments": None},
        "price": {"value": 50},
    }
    inputs, reasons = inputs_from_pack(pack)
    assert inputs is None and any("total debt is unknown" in r for r in reasons)
    assert run_valuation({}, pack) == {"computed": False, "reasons": reasons}


PACK = {
    "financials_annual": [{"fiscal_year": 2024, "revenue": 1}, {"fiscal_year": 2025, "revenue": 2}],
    "financials_quarterly": [{"fiscal_year": 2026, "fiscal_quarter": 2, "revenue": 3}],
    "filing_events": [{"event": "late"}],
    "ttm": {"revenue": 4},
}


@pytest.mark.parametrize(
    "path, value",
    [
        ("financials_annual.FY2025.revenue", 2),
        ("financials_quarterly.FY2026Q2.revenue", 3),
        ("filing_events.0.event", "late"),
        ("ttm.revenue", 4),
        ("`data_pack.ttm.revenue`", 4),
    ],
)
def test_pack_paths_resolve(path, value):
    assert resolve(PACK, path) == value


@pytest.mark.parametrize(
    "path", ["financials_annual.FY2031.revenue", "ttm.margin", "filing_events.5", "ttm.revenue.x", ""]
)
def test_unknown_pack_paths_raise(path):
    with pytest.raises(PathError):
        resolve(PACK, path)


def test_a_year_path_does_not_pick_a_quarter_row():
    with pytest.raises(PathError):
        resolve(PACK, "financials_quarterly.FY2026.revenue")


@pytest.mark.parametrize(
    "statement, expected",
    [
        ("TTM revenue is $24.9 billion, the starting point for year 1.", [24.9e9]),
        ("Revenue CAGR is -1.98% over 3 years and -0.97% over 5 years.", [0.0198, 0.0097]),
        ("It filed two Item 4.02 non-reliance 8-Ks and a late 10-K.", []),
        ("Growth in years 1-5 averages 2% over 2 quarters.", [0.02]),
        ("The 10-K was filed 160 days after the period end.", [160.0]),
    ],
)
def test_durations_ordinals_and_form_names_are_not_quantities(statement, expected):
    assert [round(q.candidates[0], 6) for q in quantities(statement)] == expected
