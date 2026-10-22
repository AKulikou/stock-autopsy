"""Banks and other financial companies (owner's manual test of 2026-10-22, Goldman Sachs): flagged by
SEC SIC code, revenue read from the tag banks use, EV-, DCF- and cash-flow-based numbers marked as
not meaningful. Nothing changes for any other company: the golden packs stay byte for byte."""

import pytest
from xbrl_samples import FY2024, FY2025, annual, base_gaap, instant, raw, submissions

from datalayer.pack import build_pack
from datalayer.sector import FINANCIAL_NOTE, NOT_MEANINGFUL, financial_kind
from valuation.dcf import ScenarioAssumptions, run_valuation


@pytest.mark.parametrize(("sic", "kind"), [
    ("6021", "bank"), ("6022", "bank"), ("6035", "bank"), ("6141", "credit company"),
    ("6211", "broker-dealer or investment adviser"), ("6282", "broker-dealer or investment adviser"),
    ("6311", "insurer"), ("6411", "insurer"),
    ("6798", None), ("6770", None), ("6500", None), ("2080", None), ("", None), (None, None),
])
def test_financial_companies_are_told_by_the_sec_sic_code(sic, kind):
    assert financial_kind(sic) == kind


def bank_gaap() -> dict:
    """A broker-dealer as Goldman Sachs reports: net revenues under RevenuesNetOfInterestExpense."""
    gaap = base_gaap()
    del gaap["Revenues"]
    gaap["RevenuesNetOfInterestExpense"] = [annual(53, FY2024, filed="2025-02-20"), annual(58, FY2025)]
    gaap["NetCashProvidedByUsedInOperatingActivities"] = [annual(-45, FY2024, filed="2025-02-20"),
                                                           annual(-40, FY2025)]
    gaap["Cash"] = [instant(30, "2024-12-31", filed="2025-02-20"), instant(35, "2025-12-31")]
    return gaap


def sic(code: str, description: str) -> dict:
    subs = submissions()
    subs.update(sic=code, sicDescription=description)
    return subs


def test_a_bank_gets_its_net_revenues_and_the_flag():
    broker = sic("6211", "Security Brokers, Dealers & Flotation Companies")
    pack, _ = build_pack(raw(bank_gaap(), subs=broker))
    assert [row["revenue"] for row in pack["financials_annual"]] == [53, 58]
    kind = "broker-dealer or investment adviser"
    assert pack["financial_company"] == {"kind": kind, "note": FINANCIAL_NOTE}
    assert FINANCIAL_NOTE in pack["data_quality"]["period_notes"]


def test_the_same_tag_is_not_read_for_a_company_that_is_not_financial():
    pack, _ = build_pack(raw(bank_gaap(), subs=sic("2080", "Beverages")))
    assert all(row["revenue"] is None for row in pack["financials_annual"])
    assert "financial_company" not in pack


def test_ev_and_cash_flow_multiples_are_marked_not_meaningful_for_a_bank():
    pack, _ = build_pack(raw(bank_gaap(), subs=sic("6021", "National Commercial Banks")))
    v = pack["derived"]["valuation"]
    for name in ("enterprise_value", "ev_revenue", "ev_ebit", "ev_ebitda", "p_fcf", "fcf_yield"):
        assert v[name] is None and f"{name}: {NOT_MEANINGFUL}" in v["notes"]
    assert not any(n.startswith("pe:") for n in v["notes"])  # price to earnings still means something


def test_the_dcf_is_not_computed_for_a_bank():
    pack, _ = build_pack(raw(bank_gaap(), subs=sic("6021", "National Commercial Banks")))
    base = ScenarioAssumptions(revenue_growth=[0.04] * 5, operating_margin=[0.3] * 5, tax_rate=0.21,
                               capex_pct_revenue=0.03, da_pct_revenue=0.03, nwc_pct_revenue_change=0.0,
                               discount_rate=0.09, terminal_growth=0.025)
    math = run_valuation({"bear": base, "base": base, "bull": base}, pack)
    assert math["computed"] is False and any(NOT_MEANINGFUL in r for r in math["reasons"])


def test_the_report_says_not_meaningful_for_a_bank_instead_of_unknown():
    from reporting.markdown import BANK_NOT_MEANINGFUL, multiple_text, number, pct
    pack, _ = build_pack(raw(bank_gaap(), subs=sic("6021", "National Commercial Banks")))
    v = pack["derived"]["valuation"]
    assert multiple_text(v, "ev_revenue", number) == BANK_NOT_MEANINGFUL
    assert multiple_text(v, "fcf_yield", pct) == BANK_NOT_MEANINGFUL
    other, _ = build_pack(raw(bank_gaap(), subs=sic("2080", "Beverages")))
    assert multiple_text(other["derived"]["valuation"], "ev_revenue", number) == "n/m"
