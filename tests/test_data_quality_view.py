"""How a person reads the data_quality block: grouped, ordered by impact, no leftovers of field paths."""

import copy
import json

import pytest

from reporting.data_quality import period_list, quality_lines, statements_to
from scripts.freeze_golden import FIXTURES


@pytest.fixture
def ko_pack():
    return json.loads((FIXTURES / "KO" / "pack.json").read_text(encoding="utf-8"))


def test_coca_cola_reads_as_four_lines_with_the_freshness_gap_first(ko_pack):
    lines = quality_lines(ko_pack)
    assert len(lines) == 4
    assert lines[0].startswith(
        "Latest quarter missing: the 10-Q for the quarter ending 2026-07-03 (filed 2026-07-29) is in the SEC "
        "filing list but still missing from SEC company facts 78 days later"
    )
    assert lines[0].endswith("the balance sheet end at 2026-04-03.")
    assert lines[1].startswith("FY2017, FY2018: earlier figures were restated (revenue, gross profit")
    assert "smaller differences" in lines[2]
    assert lines[3] == ("Not collected in this version (unknown, not zero): insider transactions, "
                        "peers and their multiples, news, earnings call transcripts.")
    assert not any("(all)" in line or "periods up to" in line or "12 months" in line for line in lines)


def test_without_the_freshness_note_the_partial_lines_stay(ko_pack):
    pack = copy.deepcopy(ko_pack)
    notes = pack["data_quality"]["period_notes"]
    pack["data_quality"]["period_notes"] = [n for n in notes if "not in SEC company facts" not in n]
    lines = quality_lines(pack)
    assert "Last twelve months: periods up to 2026-04-03 only" in lines
    assert "Latest balance sheet: periods up to 2026-04-03 only" in lines
    assert not any(line.startswith("Latest quarter missing") for line in lines)
    assert statements_to(pack) == ko_pack["ttm"]["period_end"]


def test_the_statements_date_names_the_missing_filing(ko_pack):
    assert statements_to(ko_pack) == "2026-04-03 (the 10-Q filed 2026-07-29 is not in SEC company facts)"


def test_a_conflict_says_which_source_is_used_without_float_noise(ko_pack):
    pack = copy.deepcopy(ko_pack)
    pack["data_quality"]["source_conflicts"] = [
        {"field": "market_cap", "values": {"edgar": 75_148_500_000, "yfinance": 76_881_214_602.91882},
         "used": "edgar", "dates": {}},
        {"field": "shares_outstanding", "values": {"edgar": 4_000, "yfinance": 3_000}, "used": "yfinance",
         "dates": {}},
    ]
    lines = quality_lines(pack)
    assert "Market cap: SEC 75,148,500,000, Yahoo Finance 76,881,214,603; the SEC figure is used" in lines
    assert any(line.endswith("the Yahoo Finance figure is used because the SEC one is out of date")
               for line in lines)


@pytest.fixture
def khc_pack():
    return json.loads((FIXTURES / "KHC" / "pack.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(("periods", "text"), [
    (["FY2016", "FY2017", "FY2018", "FY2019", "FY2020"], "FY2016-FY2020"),
    (["FY2016", "FY2017", "FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025"],
     "FY2016, FY2017, FY2019-FY2025"),
    (["FY2017", "FY2018"], "FY2017, FY2018"),           # two years stay a list
    (["FY2019"], "FY2019"),
    (["FY2016", "FY2017", "FY2018", "TTM"], "FY2016-FY2018, TTM"),
    (["FY2016", "FY2017", "FY2018", "balance 2026-09-30"], "FY2016-FY2018, balance 2026-09-30"),
])
def test_consecutive_fiscal_years_read_as_a_range(periods, text):
    assert period_list(periods) == text


def test_a_note_repeated_for_every_year_is_one_line_with_a_range(ko_pack):
    pack = copy.deepcopy(ko_pack)
    repeated = [f"gross_profit FY{year}: GrossProfit not reported; computed as revenue - cost of revenue"
                for year in (2016, 2017, *range(2019, 2026))]
    one_off = "operating_income FY2020: 0 where 10-K filed 2021-02-26 reports 123; not used"
    pack["data_quality"]["period_notes"] = [pack["data_quality"]["period_notes"][1], *repeated, one_off,
                                           pack["data_quality"]["period_notes"][0]]
    lines = quality_lines(pack)
    assert lines[0].startswith("Latest quarter missing")  # the freshness note stays first
    grouped = [line for line in lines if "GrossProfit" in line]
    assert grouped == ["Gross profit (FY2016, FY2017, FY2019-FY2025): GrossProfit not reported; "
                       "computed as revenue - cost of revenue"]
    assert "Operating income (FY2020): 0 where 10-K filed 2021-02-26 reports 123; not used" in lines
    rounding = next(line for line in lines if "smaller differences" in line)
    assert lines.index(grouped[0]) < lines.index(rounding)
    # The pack, and so report.json, keeps one note per period.
    assert sum("GrossProfit" in n for n in pack["data_quality"]["period_notes"]) == 9


def test_coca_cola_keeps_its_two_restated_years_as_a_list(ko_pack):
    assert quality_lines(ko_pack)[1].startswith("FY2017, FY2018: earlier figures were restated")


def test_kraft_heinz_missing_years_read_as_ranges(khc_pack):
    lines = quality_lines(khc_pack)
    assert "Share repurchases (FY2016-FY2020): not reported in the filings (unknown, not zero)" in lines
    assert "Short term investments (FY2016-FY2023): not reported in the filings (unknown, not zero)" in lines
    assert lines[0].startswith("FY2016: earlier figures were restated")  # impact order unchanged
    assert not any(", FY2017, FY2018" in line for line in lines)


def test_every_line_starts_with_a_capital_letter(ko_pack, khc_pack):
    for pack in (ko_pack, khc_pack):
        assert all(line[0].isupper() or line[0].isdigit() for line in quality_lines(pack))
