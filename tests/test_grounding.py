"""
Grounding checks: the number check against deliberate errors (a mutation test on
the golden packs), signs, group bases, calculated claims, numbers in prose and
unknowns read as zero.
"""

import json
from pathlib import Path

import pytest
from derived_mutations import FACTORS, claims

from reporting.grounding import (
    absent_as_zero,
    check_derived_claim,
    formula_values,
    operand_constants,
    prose_numbers,
)
from reporting.number_check import check_claim, quantities

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
FIELDS = ("revenue", "net_income", "operating_income", "operating_cash_flow", "gross_profit",
          "total_debt", "cash", "capex")


def billions(value: float) -> str:
    return f"${abs(value) / 1e9:.1f} billion"


def golden_leaves() -> list[tuple[dict, str, float]]:
    """(pack, leaf path, value) for every annual value above 100 million in the golden packs."""
    leaves = []
    for ticker in ("KO", "SNOW", "KHC"):
        pack = json.loads((GOLDEN / ticker / "pack.json").read_text(encoding="utf-8"))
        leaves += [
            (pack, f"financials_annual.FY{row['fiscal_year']}.{name}", row[name])
            for row in pack["financials_annual"]
            for name in FIELDS
            if isinstance(row.get(name), int | float) and abs(row[name]) > 1e8
        ]
    return leaves


LEAVES = golden_leaves()


def statuses(factor: float, basis_of=lambda path: path, wording="The figure was {} that year."):
    return [
        check_claim({"statement": wording.format(billions(value * factor)), "basis": basis_of(path)}, pack)[
            "status"
        ]
        for pack, path, value in LEAVES
    ]


# --- mutation test ---------------------------------------------------------------------


def test_the_golden_packs_give_enough_values_to_mutate():
    assert len(LEAVES) > 150


def test_correct_numbers_on_exact_paths_match():
    assert set(statuses(1.0)) == {"match"}


@pytest.mark.parametrize("factor", [1.10, 0.75, 2.0, 10.0])
def test_wrong_numbers_on_exact_paths_are_caught(factor):
    caught = statuses(factor).count("mismatch") / len(LEAVES)
    # "$0.3 billion" covers +-17% by its own precision, so a few small values still pass at +10%.
    assert caught >= 0.9, f"only {caught:.0%} of the x{factor} errors were caught"


def test_a_flipped_sign_is_caught_where_the_wording_states_it():
    flipped = [
        check_claim(
            {"statement": ("a loss of " if value > 0 else "a profit of ") + billions(value), "basis": path},
            pack,
        )["status"]
        for pack, path, value in LEAVES
    ]
    assert set(flipped) == {"mismatch"}


def test_a_number_that_only_matches_inside_a_cited_table_is_a_weaker_match():
    on_group = statuses(1.10, basis_of=lambda path: "financials_annual")
    assert "match" not in on_group  # never a full match
    assert set(on_group) <= {"group_match", "mismatch"}
    exact_on_group = statuses(1.0, basis_of=lambda path: "financials_annual")
    assert set(exact_on_group) == {"group_match"}


# --- signs -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement, sign",
    [
        ("Net loss of $1.33 billion in FY2026.", -1),
        ("an operating loss of about $1.24 billion", -1),
        ("Revenue fell 14.88% while it grew 1.87% elsewhere.", -1),
        ("free cash flow of -$447 million", -1),
        ("a profit of $2.1 billion", 1),
        ("operating income of $5.6 billion", 1),
        ("revenue grew by about 3%", 1),
        ("revenue fell to $10 billion", None),  # a level, not a change
        ("revenue was $10 billion", None),
        ("an impairment loss of $1.2 billion", None),  # stored as a positive charge
    ],
)
def test_the_direction_comes_from_the_wording(statement, sign):
    assert quantities(statement)[0].sign == sign


def test_a_stated_loss_matches_a_negative_value_and_not_a_positive_one():
    pack = {"ttm": {"net_income": -1_330_000_000, "revenue": 1_330_000_000}}
    assert check_claim({"statement": "A net loss of $1.33 billion.", "basis": "ttm.net_income"}, pack)[
        "status"
    ] == "match"
    assert check_claim({"statement": "A net loss of $1.33 billion.", "basis": "ttm.revenue"}, pack)[
        "status"
    ] == "mismatch"
    assert check_claim({"statement": "Revenue of $1.33 billion.", "basis": "ttm.net_income"}, pack)[
        "status"
    ] == "match"  # no direction stated: read as a size


# --- calculated claims ---------------------------------------------------------------------

PACK = {
    "financials_annual": [
        {"fiscal_year": 2025, "free_cash_flow": 5_296_000_000, "dividends_paid": 8_779_000_000,
         "operating_income": 13_762_000_000, "revenue": 47_061_000_000},
        {"fiscal_year": 2024, "operating_income": 9_992_000_000, "revenue": 46_197_000_000},
    ],
    "balance_sheet_latest": {
        "total_debt": 19_001_000_000, "cash": 2_419_000_000, "short_term_investments": 262_000_000,
    },
    "derived": {"valuation": {"pe": 28.82}},
    "data_quality": {"missing": [
        {"field": "total_debt", "periods": ["FY2019", "FY2020"], "reason": "not_reported"},
        {"field": "peers", "periods": ["TTM"], "reason": "not_fetched"},
    ]},
}


def derived(statement: str, basis: str) -> dict:
    return check_derived_claim({"statement": statement, "basis": basis}, PACK)


def test_a_ratio_of_two_cited_values_is_reproduced():
    claim = derived(
        "Free cash flow covered only about 60% of dividends.",
        "financials_annual.FY2025.free_cash_flow / financials_annual.FY2025.dividends_paid",
    )
    assert claim["status"] == "reproduced"


def test_a_formula_with_several_steps_is_evaluated():
    basis = ("balance_sheet_latest.total_debt - balance_sheet_latest.cash - "
             "balance_sheet_latest.short_term_investments = 19001000000 - 2419000000 - 262000000")
    assert formula_values(basis, PACK)[0] == pytest.approx(16_320_000_000)
    assert derived("Net debt is about $16.32 billion.", basis)["status"] == "reproduced"


def test_a_constant_in_the_basis_is_an_operand():
    assert derived("A 50% fall would take the P/E to about 14.4.", "derived.valuation.pe / 2")[
        "status"
    ] in ("reproduced", "partial")


def test_a_wrong_calculation_is_not_reproduced():
    claim = derived(
        "Operating income rose about 52% in FY2025.",
        "financials_annual.FY2025.operating_income / financials_annual.FY2024.operating_income - 1",
    )
    assert claim["status"] == "not_reproduced" and claim["unexplained"] == [0.52]
    right = derived(
        "Operating income rose about 37.7% in FY2025.",
        "financials_annual.FY2025.operating_income / financials_annual.FY2024.operating_income - 1",
    )
    assert right["status"] == "reproduced"


def test_formulas_never_run_code():
    assert formula_values("__import__('os').getcwd()", PACK) == []
    assert formula_values("financials_annual.FY2025.revenue ** 99999", PACK) == []


# --- prose and unknowns ----------------------------------------------------------------------


def result(**fields) -> dict:
    return {"key": "forensic", "status": "success", "claims": [], **fields}


def test_a_number_in_prose_without_any_source_is_listed():
    results = [result(summary="Revenue was $47.1 billion, and the backlog is $12.3 billion.")]
    found = prose_numbers(results, None, PACK)
    assert [u["number"] for u in found["unsourced"]] == [12.3e9]
    assert found["unsourced"][0]["field"] == "summary"


def test_counts_and_model_thresholds_are_not_prose_facts():
    results = [result(summary="Three risks in 2 areas.",
                      invalidation_criteria=[{"signal": "gross margin below 55%", "metric": "x"}])]
    assert prose_numbers(results, None, PACK)["unsourced"] == []


def test_no_debt_where_the_pack_says_unknown_is_flagged():
    text = "The company had no debt then and pays no dividends, so there was nothing to report."
    hits = absent_as_zero([result(red_flags=[{"innocent_explanation": text}])], None, PACK)
    assert [(h["missing_field"], h["field"]) for h in hits] == [
        ("total_debt", "red_flags.0.innocent_explanation")
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Total debt was 0 in FY2024 and $2.27 billion in FY2025.",  # a period the pack reports
        "The pack has no debt figures before FY2024.",  # about the data, which is right
        "There are no peers in the pack.",  # not fetched: a statement about the pack
        "There was no change in debt.",
    ],
)
def test_statements_that_respect_the_unknown_are_not_flagged(text):
    assert absent_as_zero([result(summary=text)], None, PACK) == []


def test_a_dash_between_two_numbers_is_a_range_not_a_minus():
    found = quantities("Gross margin stayed within the 58.1%-62.1% range.")
    assert [(q.candidates[0], q.sign) for q in found] == [(0.581, None), (0.621, None)]


@pytest.mark.parametrize("text", ["a 2-point step in operating margin", "a 2 percentage point step"])
def test_percentage_points_are_read_as_percents(text):
    assert quantities(text)[0].candidates == [0.02, 2.0]


# --- calculated claims: the three correct KO statements once reported as not reproduced (M15) ---

KO_2026 = {
    "derived": {"valuation": {"pe": 29.49}},
    "balance_sheet_latest": {"total_debt": 45_000_000_000, "cash": 10_275_000_000,
                             "short_term_investments": 2_000_000_000},
    "ttm": {"operating_income": 13_300_000_000, "depreciation_amortization": 2_209_000_000},
    "financials_annual": [
        {"fiscal_year": 2025, "gross_profit": 29_000_000_000, "operating_income": 13_218_000_000},
        {"fiscal_year": 2024, "gross_profit": 28_745_000_000, "operating_income": 10_000_000_000},
    ],
}


@pytest.mark.parametrize(
    "statement, basis",
    [
        ("A 50% share price fall at unchanged trailing earnings would take the P/E to about 14.7.",
         "0.5 * derived.valuation.pe (29.49)"),
        ("Net debt is about $32.7 billion, about 2.1 times trailing EBITDA.",
         "(balance_sheet_latest.total_debt - balance_sheet_latest.cash - "
         "balance_sheet_latest.short_term_investments) / "
         "(ttm.operating_income + ttm.depreciation_amortization)"),
        ("Costs below gross profit fell by about $3.0 billion.",
         "(financials_annual.FY2024.gross_profit - financials_annual.FY2024.operating_income) - "
         "(financials_annual.FY2025.gross_profit - financials_annual.FY2025.operating_income)"),
    ],
)
def test_correct_ko_calculations_are_reproduced(statement, basis):
    assert check_derived_claim({"statement": statement, "basis": basis}, KO_2026)["status"] == "reproduced"


def test_a_quoted_value_in_brackets_is_not_an_operand():
    assert operand_constants("0.5 * derived.valuation.pe (29.49)") == [0.5]
    assert operand_constants("revenue / 2 - 1; x * 100") == [2.0]  # 1 and 100 are the formula's shape


def test_a_growth_rate_keeps_its_sign():
    basis = "financials_annual.FY2025.operating_income / financials_annual.FY2024.operating_income - 1"
    rose = {"statement": "Operating income rose about 32.2% in FY2025.", "basis": basis}
    assert check_derived_claim(rose, KO_2026)["status"] == "reproduced"
    fell = {**rose, "statement": "Operating income fell about 32.2% in FY2025."}
    assert check_derived_claim(fell, KO_2026)["status"] == "not_reproduced"


# --- calculated claims: mutation test on the golden packs (tests/derived_mutations.py) ---


def reproduced_share(factor: float = 1.0, flip: bool = False, kinds=None) -> float:
    cases = [(k, c, p) for k, c, p in claims(factor, flip) if kinds is None or k in kinds]
    done = [check_derived_claim(c, p)["status"] == "reproduced" for _, c, p in cases]
    return sum(done) / len(done)


def test_correct_calculations_on_the_golden_packs_are_reproduced():
    assert reproduced_share() >= 0.99


@pytest.mark.parametrize("factor", FACTORS)
def test_wrong_calculations_on_the_golden_packs_are_caught(factor):
    assert 1 - reproduced_share(factor) >= 0.9


def test_a_flipped_direction_of_a_growth_rate_is_caught():
    # A difference of two data terms has no sign of its own, so "rose by" and "fell by"
    # both fit it: a flipped direction is caught for growth rates only (measured in M15).
    assert 1 - reproduced_share(flip=True, kinds={"growth"}) >= 0.9
