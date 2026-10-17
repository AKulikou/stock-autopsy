"""How a person reads the data_quality block (M2): grouped, ordered by impact, no leftovers of field paths."""

import copy
import json

import pytest

from reporting.data_quality import quality_lines, statements_to
from scripts.freeze_golden import FIXTURES


@pytest.fixture
def ko_pack():
    return json.loads((FIXTURES / "KO" / "pack.json").read_text(encoding="utf-8"))


def test_coca_cola_reads_as_four_lines_with_the_freshness_gap_first(ko_pack):
    lines = quality_lines(ko_pack)
    assert len(lines) == 4
    assert lines[0].startswith(
        "Latest quarter missing: the 10-Q for the quarter ending 2026-07-03 (filed 2026-07-29)"
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
    pack["data_quality"]["period_notes"] = [n for n in notes if "not yet in SEC company facts" not in n]
    lines = quality_lines(pack)
    assert "last twelve months: periods up to 2026-04-03 only" in lines
    assert "latest balance sheet: periods up to 2026-04-03 only" in lines
    assert not any(line.startswith("Latest quarter missing") for line in lines)
    assert statements_to(pack) == ko_pack["ttm"]["period_end"]


def test_the_statements_date_names_the_missing_filing(ko_pack):
    assert statements_to(ko_pack) == "2026-04-03 (the latest 10-Q is not yet in SEC company facts)"


def test_a_conflict_says_which_source_is_used_without_float_noise(ko_pack):
    pack = copy.deepcopy(ko_pack)
    pack["data_quality"]["source_conflicts"] = [
        {"field": "market_cap", "values": {"edgar": 75_148_500_000, "yfinance": 76_881_214_602.91882},
         "used": "edgar", "dates": {}},
        {"field": "shares_outstanding", "values": {"edgar": 4_000, "yfinance": 3_000}, "used": "yfinance",
         "dates": {}},
    ]
    lines = quality_lines(pack)
    assert "market cap: SEC 75,148,500,000, Yahoo Finance 76,881,214,603; the SEC figure is used" in lines
    assert any(line.endswith("the Yahoo Finance figure is used because the SEC one is out of date")
               for line in lines)
