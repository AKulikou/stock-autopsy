"""Companies whose filings this version cannot read are stopped before any paid call."""

from dataclasses import replace

import pytest
from sample_outputs import handler_for

from analysis.runner import run_autopsy
from datalayer.fetch import DataUnavailableError
from datalayer.filings import unsupported_filer
from datalayer.pack import build_pack, require_statements
from scripts.freeze_golden import FIXTURES, raw_from_fixture


def history(*forms: str) -> dict:
    return {"filings": {"recent": {"form": list(forms)}}}


@pytest.mark.parametrize("forms", [("10-K", "8-K", "4"), ("10-Q", "S-1"), ("10-K/A",), ("10-KT",)])
def test_a_company_with_10k_or_10q_reports_can_be_analyzed(forms):
    assert unsupported_filer(history(*forms)) is None


@pytest.mark.parametrize(
    ("forms", "expected"),
    [
        (("20-F", "6-K", "20-F/A"), "Files Form 20-F (a foreign company)"),
        (("40-F", "6-K"), "Files Form 40-F (a Canadian company)"),
        (("NPORT-P", "485BPOS", "N-CSR"), "A fund"),
        (("S-1", "S-1/A"), "No 10-K or 10-Q report"),
        ((), "No 10-K or 10-Q report"),
    ],
)
def test_foreign_filers_funds_and_shells_are_named_with_the_reason(forms, expected):
    reason = unsupported_filer(history(*forms))
    assert reason.startswith(expected)
    assert "10-K and 10-Q reports only" in reason


def empty_raw():
    """What a foreign filer looks like after the fetch: a price, no us-gaap statements."""
    raw = raw_from_fixture(FIXTURES / "KO")
    return replace(raw, company_facts={"cik": raw.cik, "entityName": raw.company_name, "facts": {}})


def test_a_pack_without_annual_statements_is_refused():
    pack, _ = build_pack(empty_raw())
    assert pack["price"] is not None and pack["financials_annual"] == []
    with pytest.raises(DataUnavailableError, match="no annual statements"):
        require_statements(pack)


def test_a_golden_pack_passes_the_check():
    require_statements(build_pack(raw_from_fixture(FIXTURES / "KO"))[0])


def test_an_empty_pack_stops_the_run_before_any_claude_call(fake_claude):
    raw = empty_raw()
    fake = fake_claude(handler_for(build_pack(raw)[0]))
    events = []
    with pytest.raises(DataUnavailableError):
        run_autopsy(raw, on_event=events.append)
    assert fake.requests == []
    assert [(e.stage, e.status) for e in events] == [("pack", "failed")]
