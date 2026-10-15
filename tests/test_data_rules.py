"""
The data quality rules of the DATA PACK (docs/stock_autopsy_prompts.md), one
test or more per rule, on hand-built inputs.
"""

import pytest
from xbrl_samples import (
    AS_OF,
    FY2024,
    FY2025,
    PRICE,
    annual,
    base_gaap,
    fact,
    instant,
    raw,
    submissions,
)

from core.shared_context import canonical_json
from datalayer.pack import build_pack, pack_hash


def pack_of(**kwargs) -> dict:
    return build_pack(raw(**kwargs))[0]


def row(pack: dict, year: int) -> dict:
    return next(r for r in pack["financials_annual"] if r["fiscal_year"] == year)


def missing(pack: dict, field: str) -> list[dict]:
    return [m for m in pack["data_quality"]["missing"] if m["field"] == field]


# ---- rule 1: missing is null, never 0 ----------------------------------------


def test_missing_tag_is_null_with_a_reason_never_zero():
    pack = pack_of()
    assert row(pack, 2025)["interest_expense"] is None
    entry = missing(pack, "interest_expense")[0]
    assert entry["reason"] == "tag_not_found" and "FY2025" in entry["periods"]


def test_value_reported_in_other_years_only_is_not_reported_for_this_year():
    gaap = base_gaap()
    gaap["InterestExpense"] = [annual(3, FY2025)]
    pack = pack_of(gaap=gaap)
    assert row(pack, 2024)["interest_expense"] is None
    assert missing(pack, "interest_expense")[0] == {
        "field": "interest_expense",
        "periods": ["FY2024"],
        "reason": "not_reported",
    }


def test_no_debt_concept_at_all_gives_null_debt_not_zero():
    pack = pack_of()
    assert row(pack, 2025)["total_debt"] is None
    assert pack["balance_sheet_latest"]["total_debt"] is None
    assert missing(pack, "total_debt")[0]["reason"] == "tag_not_found"


def test_convertible_debt_counts_when_no_long_term_debt_is_reported():
    gaap = base_gaap()
    gaap["ConvertibleDebtNoncurrent"] = [instant(2_000, "2025-12-31")]
    pack = pack_of(gaap=gaap)
    assert row(pack, 2025)["total_debt"] == 2_000
    covers = [p["covers"] for p in pack["data_quality"]["partial"] if p["field"] == "total_debt"]
    assert any("non-current" in c for c in covers)
    assert any("short-term" in c for c in covers)


def test_debt_adds_long_term_and_short_term_borrowings():
    gaap = base_gaap()
    gaap["LongTermDebt"] = [instant(1_000, "2025-12-31")]
    gaap["CommercialPaper"] = [instant(200, "2025-12-31")]
    gaap["OtherShortTermBorrowings"] = [instant(50, "2025-12-31")]
    pack = pack_of(gaap=gaap)
    assert row(pack, 2025)["total_debt"] == 1_250
    assert not [p for p in pack["data_quality"]["partial"] if p["field"] == "total_debt"]


# ---- rule 2: an implausible zero is unknown -------------------------------------


def test_zero_share_count_from_the_price_provider_is_unknown():
    pack = pack_of(
        dei={"EntityCommonStockSharesOutstanding": [instant(1_000_000, "2026-07-31")]},
        price={**PRICE, "shares_reported": 0},
    )
    assert not pack["data_quality"]["source_conflicts"]
    assert any("treated as unknown" in n for n in pack["data_quality"]["period_notes"])


def test_zero_price_is_unknown_and_no_market_cap_is_computed():
    pack = pack_of(
        dei={"EntityCommonStockSharesOutstanding": [instant(1_000_000, "2026-07-31")]},
        price={**PRICE, "close": 0.0},
    )
    assert pack["price"] is None
    assert pack["derived"]["valuation"]["market_cap"] is None


# ---- rule 3: an empty result is not a failed fetch ---------------------------------


def test_insider_transactions_not_fetched_are_null_not_an_empty_list():
    pack = pack_of()
    assert pack["insider_transactions_12m"] is None
    assert pack["data_quality"]["fetch_status"]["form4"] == "not_fetched"
    assert missing(pack, "insider_transactions_12m")[0]["reason"] == "not_fetched"


def test_failed_price_fetch_is_recorded_as_provider_error():
    pack = pack_of(price=None)
    assert pack["price"] is None
    assert pack["data_quality"]["fetch_status"]["yfinance"] == "failed"
    assert missing(pack, "price")[0]["reason"] == "provider_error"


def test_failed_filing_history_leaves_events_unknown():
    pack = pack_of(subs=False)
    assert pack["filing_events"] is None
    assert missing(pack, "filing_events")[0]["reason"] == "provider_error"


# ---- rule 4: a slice is labelled as a slice -----------------------------------------


def test_filing_history_that_starts_late_is_partial():
    pack = pack_of(subs=submissions([("10-K", "2026-02-20", "2025-12-31", "")]))
    assert any(p["field"] == "filing_events" for p in pack["data_quality"]["partial"])


def test_company_facts_lagging_the_filings_are_flagged():
    subs = submissions(
        [
            ("10-Q", "2026-07-29", "2026-06-30", ""),
            ("10-K", "2026-02-20", "2025-12-31", ""),
            ("10-K", "2025-02-20", "2024-12-31", ""),
        ]
    )
    pack = pack_of(subs=subs)
    assert {"field": "ttm", "covers": "periods up to 2025-12-31 only"} in pack["data_quality"]["partial"]
    assert any("not yet in SEC company facts" in n for n in pack["data_quality"]["period_notes"])


# ---- rule 5: a future date is corrupt or not yet knowable ---------------------------


def test_facts_filed_after_as_of_are_dropped():
    gaap = base_gaap()
    gaap["NetIncomeLoss"].append(annual(99, FY2025, filed="2026-11-01", form="10-K/A"))
    pack = pack_of(gaap=gaap)
    assert row(pack, 2025)["net_income"] == 12
    assert any("after as_of were dropped" in n for n in pack["data_quality"]["period_notes"])


def test_point_in_time_pack_sees_only_what_was_filed_by_then():
    pack = pack_of(as_of=AS_OF.replace(year=2025, month=6))
    assert [r["fiscal_year"] for r in pack["financials_annual"]] == [2024]


# ---- rule 6: restatements stay visible ---------------------------------------------


def test_restated_value_keeps_the_latest_filing_and_records_the_original():
    gaap = base_gaap()
    gaap["NetIncomeLoss"].append(annual(8, FY2024, filed="2025-06-01", form="10-K/A"))
    pack = pack_of(gaap=gaap)
    assert row(pack, 2024)["net_income"] == 8
    assert pack["data_quality"]["restated"] == [
        {
            "field": "net_income",
            "period": "FY2024",
            "original": 10,
            "restated": 8,
            "original_filed": "2025-02-20",
            "filed": "2025-06-01",
            "form": "10-K/A",
        }
    ]


def test_restatement_under_a_new_revenue_concept_is_found():
    gaap = base_gaap()
    gaap["Revenues"] = [annual(120, FY2025)]
    gaap["SalesRevenueGoodsNet"] = [annual(100, FY2024, filed="2025-02-20")]
    gaap["RevenueFromContractWithCustomerExcludingAssessedTax"] = [annual(90, FY2024)]
    pack = pack_of(gaap=gaap)
    assert row(pack, 2024)["revenue"] == 90
    entry = pack["data_quality"]["restated"][0]
    assert (
        entry["concept_change"]
        == "SalesRevenueGoodsNet -> RevenueFromContractWithCustomerExcludingAssessedTax"
    )


def test_a_broader_cash_definition_in_a_later_filing_is_not_a_restatement():
    gaap = base_gaap()
    gaap["CashAndCashEquivalentsAtCarryingValue"] = [instant(50, "2024-12-31", filed="2025-02-20")]
    gaap["CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"] = [instant(55, "2024-12-31")]
    pack = pack_of(gaap=gaap)
    assert row(pack, 2024)["cash"] == 50
    assert pack["data_quality"]["restated"] == []


def test_rounding_between_filings_is_not_a_restatement():
    gaap = base_gaap()
    gaap["Revenues"] = [
        annual(26_601_428, FY2024, filed="2025-02-20"),
        annual(26_601_000, FY2024),
        annual(30_000_000, FY2025),
    ]
    pack = pack_of(gaap=gaap)
    assert pack["data_quality"]["restated"] == []
    assert any("smaller differences" in n for n in pack["data_quality"]["period_notes"])


def test_proxy_statement_figures_are_ignored():
    gaap = base_gaap()
    gaap["NetIncomeLoss"].append(annual(13, FY2025, filed="2026-05-01", form="DEF 14A"))
    pack = pack_of(gaap=gaap)
    assert row(pack, 2025)["net_income"] == 12
    assert pack["data_quality"]["restated"] == []


def test_an_annual_figure_quoted_in_a_10q_does_not_replace_the_10k():
    gaap = base_gaap()
    gaap["NetIncomeLoss"].append(annual(11, FY2024, filed="2025-08-01", form="10-Q"))
    assert row(pack_of(gaap=gaap), 2024)["net_income"] == 10


# ---- splits: per-share history and share counts on today's basis -------------------------


def split_gaap() -> dict:
    gaap = base_gaap()
    gaap["WeightedAverageNumberOfDilutedSharesOutstanding"] = [
        annual(100, FY2024, filed="2025-02-20"),
        annual(210, FY2025),  # filed after the split: already on the new basis
    ]
    return gaap


def test_share_counts_filed_before_a_split_are_adjusted():
    price = {**PRICE, "splits": [{"date": "2025-06-01", "ratio": 2.0}]}
    pack = pack_of(gaap=split_gaap(), price=price)
    assert row(pack, 2024)["shares_diluted"] == 200
    assert row(pack, 2025)["shares_diluted"] == 210
    assert pack["derived"]["annual"][-1]["shares_diluted_change"] == pytest.approx(0.05)


def test_a_split_adjusted_comparative_is_not_a_restatement():
    gaap = split_gaap()
    gaap["WeightedAverageNumberOfDilutedSharesOutstanding"].append(annual(200, FY2024))
    price = {**PRICE, "splits": [{"date": "2025-06-01", "ratio": 2.0}]}
    pack = pack_of(gaap=gaap, price=price)
    assert row(pack, 2024)["shares_diluted"] == 200
    assert pack["data_quality"]["restated"] == []


def test_split_like_change_without_split_history_is_noted_not_restated():
    gaap = split_gaap()
    gaap["WeightedAverageNumberOfDilutedSharesOutstanding"].append(annual(200, FY2024))
    pack = pack_of(gaap=gaap, price=None)
    assert pack["data_quality"]["restated"] == []
    assert any("looks like a stock split" in n for n in pack["data_quality"]["period_notes"])
    assert {
        "field": "shares_diluted",
        "covers": "split history unavailable: share counts not split-adjusted",
    } in pack["data_quality"]["partial"]


def test_cover_page_shares_filed_before_a_split_are_adjusted():
    dei = {
        "EntityCommonStockSharesOutstanding": [instant(1_000, "2025-04-20", filed="2025-04-30", form="10-Q")]
    }
    price = {**PRICE, "splits": [{"date": "2025-06-01", "ratio": 2.0}]}
    assert pack_of(dei=dei, price=price)["shares_outstanding"]["value"] == 2_000


# ---- rule 7: disagreeing sources are both recorded ----------------------------------


def test_units_mismatch_between_sources_is_caught_as_a_conflict():
    dei = {"EntityCommonStockSharesOutstanding": [instant(1_000_000, "2026-07-31")]}
    pack = pack_of(dei=dei, price={**PRICE, "shares_reported": 1_000})  # reported in thousands
    conflict = pack["data_quality"]["source_conflicts"][0]
    assert conflict["field"] == "shares_outstanding"
    assert conflict["values"] == {"edgar": 1_000_000, "yfinance": 1_000}
    assert conflict["used"] == "edgar"
    assert any("units or scale bug" in n for n in pack["data_quality"]["period_notes"])


def test_small_difference_between_sources_is_not_a_conflict():
    dei = {"EntityCommonStockSharesOutstanding": [instant(1_000_000, "2026-07-31")]}
    pack = pack_of(dei=dei, price={**PRICE, "shares_reported": 1_010_000})
    assert pack["data_quality"]["source_conflicts"] == []


# ---- periods ------------------------------------------------------------------------


def test_53_week_year_is_flagged():
    gaap = {"NetIncomeLoss": [annual(10, ("2021-12-26", "2022-12-31"))]}
    pack = pack_of(gaap=gaap)
    assert row(pack, 2022)["period_end"] == "2022-12-31"
    assert any("53 weeks" in n for n in pack["data_quality"]["period_notes"])


def test_year_ending_in_early_january_is_named_after_the_previous_year():
    gaap = {"NetIncomeLoss": [annual(10, ("2015-01-04", "2016-01-02"), filed="2016-02-20")]}
    assert pack_of(gaap=gaap)["financials_annual"][0]["fiscal_year"] == 2015


def ttm_gaap() -> dict:
    gaap = base_gaap()
    gaap["Revenues"] += [
        fact(25, "2025-03-31", start="2025-01-01", filed="2025-04-30", form="10-Q"),
        fact(60, "2025-06-30", start="2025-01-01", filed="2025-07-30", form="10-Q"),
        fact(90, "2025-09-30", start="2025-01-01", filed="2025-10-30", form="10-Q"),
        fact(30, "2026-03-31", start="2026-01-01", filed="2026-04-30", form="10-Q"),
        fact(70, "2026-06-30", start="2026-01-01", filed="2026-07-30", form="10-Q"),
        fact(60, "2025-06-30", start="2025-01-01", filed="2026-07-30", form="10-Q"),  # comparative
    ]
    return gaap


def test_ttm_is_last_year_plus_this_year_to_date_minus_last_year_to_date():
    pack = pack_of(gaap=ttm_gaap())
    assert pack["ttm"]["revenue"] == 120 + 70 - 60
    assert pack["ttm"]["period_end"] == "2026-06-30"
    assert pack["ttm"]["basis"].startswith("TTM")


def test_ttm_without_a_later_quarter_is_the_last_fiscal_year():
    pack = pack_of()
    assert pack["ttm"]["revenue"] == 120
    assert pack["ttm"]["basis"].startswith("last fiscal year")


def test_q4_is_the_year_minus_nine_months():
    pack = pack_of(gaap=ttm_gaap())
    q4 = next(
        q for q in pack["financials_quarterly"] if q["fiscal_year"] == 2025 and q["fiscal_quarter"] == 4
    )
    assert q4["revenue"] == 120 - 90
    assert "revenue" in q4["computed_from_year_to_date"]


def test_gross_profit_falls_back_to_revenue_minus_cost_with_a_note():
    gaap = base_gaap()
    gaap["CostOfRevenue"] = [annual(70, FY2025)]
    pack = pack_of(gaap=gaap)
    assert row(pack, 2025)["gross_profit"] == 50
    assert any("computed as revenue - cost" in n for n in pack["data_quality"]["period_notes"])


# ---- TTM and fiscal-year figures never mix in one multiple ----------------------------


def test_multiples_use_ttm_only_and_stay_null_when_ttm_is_missing():
    gaap = ttm_gaap()
    gaap["Revenues"] = [f for f in gaap["Revenues"] if not (f["end"] == "2025-06-30")]  # no prior-year YTD
    gaap["LongTermDebt"] = [instant(10, "2025-12-31")]
    gaap["CommercialPaper"] = [instant(0, "2025-12-31")]
    gaap["CashAndCashEquivalentsAtCarryingValue"] = [instant(5, "2025-12-31")]
    dei = {"EntityCommonStockSharesOutstanding": [instant(100, "2026-07-31")]}
    pack = pack_of(gaap=gaap, dei=dei)
    assert row(pack, 2025)["revenue"] == 120  # the fiscal-year figure exists
    assert pack["ttm"]["revenue"] is None
    assert pack["derived"]["valuation"]["ev_revenue"] is None
    assert pack["derived"]["valuation"]["enterprise_value"] is not None


def test_pe_on_a_loss_is_not_meaningful():
    gaap = base_gaap()
    gaap["NetIncomeLoss"] = [annual(10, FY2024, filed="2025-02-20"), annual(-5, FY2025)]
    dei = {"EntityCommonStockSharesOutstanding": [instant(100, "2026-07-31")]}
    valuation = pack_of(gaap=gaap, dei=dei)["derived"]["valuation"]
    assert valuation["pe"] is None
    assert any(n.startswith("pe: not meaningful") for n in valuation["notes"])


# ---- the pack as a whole ------------------------------------------------------------------


def test_pack_is_canonical_json_and_its_hash_is_stable():
    first, second = pack_of(), pack_of()
    canonical_json(first)  # raises on NaN or infinity
    assert pack_hash(first) == pack_hash(second)


def test_user_context_is_validated():
    with pytest.raises(ValueError):
        build_pack(raw(), {"horizon": "forever", "risk_tolerance": "medium"})


def test_filing_events_include_non_reliance_and_late_notices():
    subs = submissions(
        [
            ("10-K", "2026-02-20", "2025-12-31", ""),
            ("8-K", "2025-05-06", "", "2.02,4.02,9.01"),
            ("NT 10-K", "2025-03-01", "2024-12-31", ""),
            ("10-K", "2025-06-07", "2024-12-31", ""),
            ("8-K", "2025-01-10", "", "5.02"),
        ]
    )
    pack = pack_of(subs=subs)
    events = [(e["form"], e.get("item")) for e in pack["filing_events"]]
    assert ("8-K", "4.02") in events and ("NT 10-K", None) in events
    assert ("8-K", "5.02") not in events
    timing = {t["period_end"]: t["days_after_period_end"] for t in pack["annual_report_timing"]}
    assert timing["2024-12-31"] == 158
