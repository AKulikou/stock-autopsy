"""
Golden tickers (decision D2): KO (boring quality), SNOW (fast-growing, loss-making),
KHC (accounting scandal: 2019 restatement). The packs are rebuilt from trimmed
SEC and price inputs frozen on 2026-10-15 and must match the frozen packs exactly;
after a deliberate change, refreeze with scripts/freeze_golden.py and review the diff.
"""

import json
from pathlib import Path

import pytest

from datalayer.pack import build_pack
from scripts.freeze_golden import FIXTURES, raw_from_fixture

GOLDEN = ("KO", "SNOW", "KHC")


@pytest.fixture(scope="module")
def packs() -> dict[str, dict]:
    return {ticker: build_pack(raw_from_fixture(FIXTURES / ticker))[0] for ticker in GOLDEN}


@pytest.mark.parametrize("ticker", GOLDEN)
def test_pack_matches_the_frozen_pack(packs, ticker):
    frozen = json.loads(Path(FIXTURES / ticker / "pack.json").read_text(encoding="utf-8"))
    assert packs[ticker] == frozen


def restated(pack: dict, field: str, period: str) -> dict | None:
    return next(
        (r for r in pack["data_quality"]["restated"] if r["field"] == field and r["period"] == period), None
    )


def test_khc_restatement_is_visible_in_the_numbers(packs):
    khc = packs["KHC"]
    entry = restated(khc, "operating_income", "FY2016")
    assert (entry["original"], entry["restated"], entry["filed"]) == (
        6_142_000_000,
        5_601_000_000,
        "2019-06-07",
    )
    assert restated(khc, "operating_cash_flow", "FY2016")["restated"] == 2_648_000_000


def test_khc_filing_history_shows_the_restatement_trail(packs):
    khc = packs["KHC"]
    events = {(e["form"], e.get("item")) for e in khc["filing_events"]}
    assert ("8-K", "4.02") in events and ("NT 10-K", None) in events
    late = [t for t in khc["annual_report_timing"] if t["days_after_period_end"] > 90]
    assert [t["period_end"] for t in late] == ["2018-12-29"]


def test_khc_53_week_year_is_flagged(packs):
    assert any("FY2022 has 53 weeks" in n for n in packs["KHC"]["data_quality"]["period_notes"])


def test_ko_recasts_appear_without_restatement_warning_signs(packs):
    """The forensic false-positive test: KO's values changed, but no 4.02, no late notices."""
    ko = packs["KO"]
    assert restated(ko, "revenue", "FY2018")["restated"] == 34_300_000_000
    assert not [e for e in ko["filing_events"] if e.get("item") == "4.02" or e["form"].startswith("NT ")]
    assert max(t["days_after_period_end"] for t in ko["annual_report_timing"]) < 60


def test_ko_lagging_company_facts_are_flagged(packs):
    notes = packs["KO"]["data_quality"]["period_notes"]
    assert any("2026-07-03" in n and "not yet in SEC company facts" in n for n in notes)


def test_snow_convertible_debt_is_found_and_absent_history_is_unknown(packs):
    snow = packs["SNOW"]
    assert snow["balance_sheet_latest"]["total_debt"] == 2_283_985_000
    early = [r for r in snow["financials_annual"] if r["fiscal_year"] <= 2023]
    assert all(r["total_debt"] is None for r in early)  # not 0: no debt concept reported then


def test_snow_loss_makes_earnings_multiples_not_meaningful(packs):
    valuation = packs["SNOW"]["derived"]["valuation"]
    assert valuation["pe"] is None and valuation["ev_ebit"] is None
    assert valuation["ev_revenue"] is not None


def test_snow_fiscal_year_ending_in_january_is_named_after_that_year(packs):
    assert packs["SNOW"]["financials_annual"][-1]["fiscal_year"] == 2026
    assert packs["SNOW"]["fiscal_year_end"] == "01-31"


@pytest.mark.parametrize("ticker", GOLDEN)
def test_no_number_in_a_golden_pack_is_nan_and_every_row_has_dates(packs, ticker):
    pack = packs[ticker]
    json.dumps(pack, allow_nan=False)
    for row in pack["financials_annual"] + pack["financials_quarterly"]:
        assert row["period_start"] < row["period_end"]
