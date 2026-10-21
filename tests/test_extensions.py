"""Company extension concepts: parsing filing XBRL, choosing a concept, using it in the pack."""

import json
from datetime import date

import pytest
from xbrl_samples import base_gaap, company_facts, instant, raw, submissions

from datalayer.cache import DailyCache
from datalayer.extensions import (
    extension_gap,
    fetch_extension_facts,
    filings_to_read,
    instance_name,
    is_receivable_balance,
    matching_concepts,
    parse_instance,
)
from datalayer.http import HttpError
from datalayer.pack import build_pack
from datalayer.sec import SecClient

NEW = "TradeReceivablesAndContractAssetsAfterAllowanceForCreditLossCurrent"
OLD = "TradeReceivablesandContractAssetsafterAllowanceforCreditLossCurrent"  # how it was spelled until 2024

INSTANCE = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2025"
  xmlns:co="http://www.example.com/20251231" xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
  <xbrli:context id="c2025"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
  <xbrli:context id="d2025"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate>
    </xbrli:period></xbrli:context>
  <xbrli:context id="seg"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier>
    <xbrli:segment><xbrldi:explicitMember dimension="a">b</xbrldi:explicitMember></xbrli:segment>
    </xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
  <co:TradeReceivablesAndContractAssetsAfterAllowanceForCreditLossCurrent contextRef="c2025" unitRef="usd"
    decimals="-3">1108201000</co:TradeReceivablesAndContractAssetsAfterAllowanceForCreditLossCurrent>
  <co:TradeReceivablesAndContractAssetsAfterAllowanceForCreditLossCurrent contextRef="seg" unitRef="usd"
    decimals="-3">5</co:TradeReceivablesAndContractAssetsAfterAllowanceForCreditLossCurrent>
  <co:IncreaseDecreaseInTradeReceivablesAndContractAssets contextRef="d2025" unitRef="usd"
    decimals="-3">69129000</co:IncreaseDecreaseInTradeReceivablesAndContractAssets>
  <us-gaap:Assets contextRef="c2025" unitRef="usd" decimals="-3">100</us-gaap:Assets>
  <co:PolicyText contextRef="d2025">text</co:PolicyText>
</xbrli:xbrl>"""


def test_instance_keeps_consolidated_extension_facts_only():
    facts = parse_instance(INSTANCE, "acc-1", "10-K", "2026-02-26")
    assert set(facts) == {NEW, "IncreaseDecreaseInTradeReceivablesAndContractAssets"}  # no us-gaap, no text
    assert facts[NEW]["units"]["USD"] == [
        {"end": "2025-12-31", "val": 1108201000, "accn": "acc-1", "form": "10-K", "filed": "2026-02-26"}
    ]  # the segment fact (5) is not consolidated
    change = facts["IncreaseDecreaseInTradeReceivablesAndContractAssets"]["units"]["USD"][0]
    assert (change["start"], change["end"]) == ("2025-01-01", "2025-12-31")


@pytest.mark.parametrize(
    "concept, expected",
    [
        (NEW, True),
        (OLD, True),
        ("AccountsReceivableNetCurrent", True),
        ("TradeReceivablesAndContractAssetsAllowanceForCreditLossCurrent", False),  # the allowance itself
        ("IncreaseDecreaseInTradeReceivablesAndContractAssets", False),
        ("LongTermReceivablesNoncurrent", False),
        ("OtherReceivablesCurrent", False),
        ("IncomeTaxesReceivableCurrent", False),
        ("UnbilledReceivablesCurrent", False),
    ],
)
def test_receivable_balance_matcher(concept, expected):
    assert is_receivable_balance(concept) is expected


def ext_facts(*names: str) -> dict:
    return {
        "facts": {
            "ext": {
                name: {"units": {"USD": [instant(10 + n, "2025-12-31", filed=f"202{n}-02-20")]}}
                for n, name in enumerate(names)
            }
        }
    }


def test_case_variants_are_one_concept_newest_spelling_first():
    assert matching_concepts(ext_facts(OLD, NEW), "accounts_receivable") == [(NEW, OLD)]


def test_two_different_candidates_are_ambiguous():
    groups = matching_concepts(ext_facts(NEW, "BilledReceivablesNetCurrent"), "accounts_receivable")
    assert len(groups) == 2


ROWS = [
    {"form": "10-K", "filed": "2026-02-26", "report_date": "2025-12-31", "accession": "a-25", "items": ""},
    {"form": "10-K", "filed": "2025-02-20", "report_date": "2024-12-31", "accession": "a-24", "items": ""},
    {"form": "10-K", "filed": "2019-02-20", "report_date": "2018-12-31", "accession": "a-18", "items": ""},
    {"form": "10-Q", "filed": "2025-11-01", "report_date": "2025-09-30", "accession": "q-25", "items": ""},
    {"form": "10-Q", "filed": "2026-08-01", "report_date": "2026-06-30", "accession": "q-26", "items": ""},
    {"form": "8-K", "filed": "2026-03-01", "report_date": None, "accession": "e-26", "items": "2.02"},
]


def test_gap_starts_where_us_gaap_receivables_stop():
    gaap = company_facts({"AccountsReceivableNetCurrent": [instant(5, "2019-09-30")]})
    assert extension_gap(gaap, ROWS, date(2015, 10, 15)) == date(2019, 9, 30)


def test_no_gap_when_us_gaap_covers_the_latest_annual_report():
    gaap = company_facts({"AccountsReceivableNetCurrent": [instant(5, "2025-12-31")]})
    assert extension_gap(gaap, ROWS, date(2015, 10, 15)) is None


def test_filings_read_are_the_10ks_after_the_gap_and_the_latest_later_10q():
    chosen = filings_to_read(ROWS, date(2019, 9, 30), date(2026, 10, 15))
    assert [r["accession"] for r in chosen] == ["a-24", "a-25", "q-26"]


def test_instance_name_prefers_the_extracted_inline_instance():
    index = {
        "directory": {
            "item": [
                {"name": n}
                for n in (
                    "FilingSummary.xml",
                    "co-20251231_lab.xml",
                    "co-20251231_htm.xml",
                    "co-20251231.htm",
                )
            ]
        }
    }
    assert instance_name(index) == "co-20251231_htm.xml"


def test_fetch_reads_each_filing_once_per_day(tmp_path):
    calls = []

    def http_get(url, headers):
        calls.append(url)
        if url.endswith("index.json"):
            return json.dumps({"directory": {"item": [{"name": "co-20251231_htm.xml"}]}}).encode()
        return INSTANCE

    sec = SecClient(
        "Test Runner tester@example.org", http_get=http_get, clock=lambda: 0.0, sleep=lambda s: None
    )
    cache = DailyCache(date(2026, 10, 15), tmp_path)
    rows = [ROWS[0]]
    first = fetch_extension_facts(sec, cache, "CO", 1, rows, date(2024, 12, 31), date(2026, 10, 15))
    second = fetch_extension_facts(sec, cache, "CO", 1, rows, date(2024, 12, 31), date(2026, 10, 15))
    assert first == second and NEW in first["facts"]["ext"]
    assert len(calls) == 2  # index + instance, then the cache


def test_a_failing_filing_raises_so_the_caller_records_it(tmp_path):
    def http_get(url, headers):
        raise HttpError(url, 404)

    sec = SecClient(
        "Test Runner tester@example.org", http_get=http_get, clock=lambda: 0.0, sleep=lambda s: None
    )
    with pytest.raises(HttpError):
        fetch_extension_facts(
            sec,
            DailyCache(date(2026, 10, 15), tmp_path),
            "CO",
            1,
            [ROWS[0]],
            date(2024, 12, 31),
            date(2026, 10, 15),
        )


# ---- in the pack ------------------------------------------------------------


def switched_raw():
    """Receivables in us-gaap for FY2024, then only in an extension concept for FY2025."""
    gaap = base_gaap()
    gaap["AccountsReceivableNetCurrent"] = [instant(30, "2024-12-31", filed="2025-02-20")]
    data = raw(gaap=gaap)
    data.extension_facts = {"facts": {"ext": {NEW: {"units": {"USD": [instant(45, "2025-12-31")]}}}}}
    data.fetch_status["edgar_extensions"] = "ok"
    return data


def test_extension_concept_fills_the_years_us_gaap_lacks():
    pack, provenance = build_pack(switched_raw())
    rows = {r["fiscal_year"]: r for r in pack["financials_annual"]}
    assert (rows[2024]["accounts_receivable"], rows[2025]["accounts_receivable"]) == (30, 45)
    assert provenance["FY2025.accounts_receivable"]["concept"] == f"ext:{NEW}"
    assert pack["data_quality"]["fetch_status"]["edgar_extensions"] == "ok"
    assert any(
        "company's own XBRL concept" in n and "FY2025" in n for n in pack["data_quality"]["period_notes"]
    )


def test_growth_across_the_definition_switch_is_not_computed():
    pack, _ = build_pack(switched_raw())
    fy2025 = next(m for m in pack["derived"]["annual"] if m["fiscal_year"] == 2025)
    assert fy2025["receivables_growth"] is None
    assert any("changes definition" in n for n in pack["data_quality"]["period_notes"])


def test_ambiguous_extension_concepts_are_not_used():
    data = switched_raw()
    data.extension_facts["facts"]["ext"]["BilledReceivablesNetCurrent"] = {
        "units": {"USD": [instant(40, "2025-12-31")]}
    }
    pack, _ = build_pack(data)
    assert pack["financials_annual"][-1]["accounts_receivable"] is None
    assert any("several company-specific concepts" in n for n in pack["data_quality"]["period_notes"])


def test_a_zero_contradicted_by_another_filing_is_a_tagging_error():
    gaap = base_gaap()
    gaap["AccountsReceivableNetCurrent"] = [
        instant(30, "2024-12-31", filed="2025-02-20"),
        instant(0, "2024-12-31", filed="2026-02-20"),  # the later 10-K leaves it at 0
    ]
    pack, _ = build_pack(raw(gaap=gaap))
    assert next(r for r in pack["financials_annual"] if r["fiscal_year"] == 2024)["accounts_receivable"] == 30
    assert any("tagging error" in n for n in pack["data_quality"]["period_notes"])
    assert pack["data_quality"]["restated"] == []


def test_freshness_ignores_extension_facts():
    data = switched_raw()
    data.extension_facts["facts"]["ext"][NEW]["units"]["USD"].append(instant(50, "2026-06-30", form="10-Q"))
    data.submissions = submissions(
        [
            ("10-Q", "2026-07-30", "2026-06-30", ""),
            ("10-K", "2026-02-20", "2025-12-31", ""),
            ("10-K", "2025-02-20", "2024-12-31", ""),
        ]
    )
    pack, _ = build_pack(data)
    assert any("not in SEC company facts" in n for n in pack["data_quality"]["period_notes"])
