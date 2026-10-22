"""
Deterministic math on the pack's figures: margins, growth, free cash flow and
valuation multiples. Python computes these so evaluators never do arithmetic;
they cite the results as [DERIVED] with the formula listed in FORMULAS.

A ratio with a missing input is None, never 0. A multiple whose denominator is
zero or negative is not meaningful (a P/E on a loss): None with a note saying why.
Multiples use TTM flows only, so fiscal-year and TTM figures never mix.
"""

from datalayer.sector import NOT_MEANINGFUL

RATIO_DIGITS = 4

FORMULAS = {
    "revenue_growth": "revenue / previous fiscal year revenue - 1",
    "gross_margin": "gross_profit / revenue",
    "operating_margin": "operating_income / revenue",
    "net_margin": "net_income / revenue",
    "free_cash_flow": "operating_cash_flow - capex",
    "fcf_margin": "free_cash_flow / revenue",
    "sbc_to_revenue": "stock_based_compensation / revenue",
    "cash_conversion": "operating_cash_flow / net_income (only when net_income > 0)",
    "receivables_growth": "accounts_receivable / previous fiscal year accounts_receivable - 1",
    "shares_diluted_change": "shares_diluted / previous fiscal year shares_diluted - 1",
    "revenue_cagr": "(revenue now / revenue N years earlier) ^ (1 / N) - 1",
    "market_cap": "price * shares_outstanding (EDGAR cover page)",
    "enterprise_value": "market_cap + total_debt - cash - short_term_investments (latest balance sheet)",
    "pe": "market_cap / TTM net_income",
    "ev_revenue": "enterprise_value / TTM revenue",
    "ev_ebit": "enterprise_value / TTM operating_income",
    "ev_ebitda": "enterprise_value / (TTM operating_income + TTM depreciation_amortization)",
    "p_fcf": "market_cap / TTM free_cash_flow",
    "fcf_yield": "TTM free_cash_flow / market_cap",
}


def ratio(numerator, denominator) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator, RATIO_DIGITS)


def growth(current, previous) -> float | None:
    """Growth is only meaningful from a positive base."""
    if current is None or previous is None or previous <= 0:
        return None
    return round(current / previous - 1, RATIO_DIGITS)


def free_cash_flow(row: dict) -> int | float | None:
    if row.get("operating_cash_flow") is None or row.get("capex") is None:
        return None
    return row["operating_cash_flow"] - row["capex"]


def margins(row: dict) -> dict:
    fcf = free_cash_flow(row)
    revenue = row.get("revenue")
    net_income = row.get("net_income")
    return {
        "gross_margin": ratio(row.get("gross_profit"), revenue),
        "operating_margin": ratio(row.get("operating_income"), revenue),
        "net_margin": ratio(net_income, revenue),
        "free_cash_flow": fcf,
        "fcf_margin": ratio(fcf, revenue),
        "sbc_to_revenue": ratio(row.get("stock_based_compensation"), revenue),
        "cash_conversion": (
            ratio(row.get("operating_cash_flow"), net_income)
            if net_income is not None and net_income > 0
            else None
        ),
    }


def annual_metrics(rows: list[dict]) -> list[dict]:
    metrics = []
    previous = None
    for row in rows:
        consecutive = previous is not None and previous["fiscal_year"] == row["fiscal_year"] - 1
        before = previous if consecutive else {}
        metrics.append(
            {
                "fiscal_year": row["fiscal_year"],
                "revenue_growth": growth(row.get("revenue"), before.get("revenue")),
                **margins(row),
                "receivables_growth": growth(
                    row.get("accounts_receivable"), before.get("accounts_receivable")
                ),
                "shares_diluted_change": growth(row.get("shares_diluted"), before.get("shares_diluted")),
            }
        )
        previous = row
    return metrics


def revenue_cagr(rows: list[dict], years: int) -> float | None:
    by_year = {row["fiscal_year"]: row.get("revenue") for row in rows}
    if not rows:
        return None
    last = rows[-1]["fiscal_year"]
    now, then = by_year.get(last), by_year.get(last - years)
    if now is None or then is None or now <= 0 or then <= 0:
        return None
    return round((now / then) ** (1 / years) - 1, RATIO_DIGITS)


def valuation(price: dict | None, shares: dict | None, ttm: dict | None, balance: dict | None,
              financial: bool = False) -> dict:
    """
    Multiples on TTM figures. For a bank or other financial company (datalayer/sector.py) the
    EV- and free-cash-flow-based ones are left out with a reason: debt is its raw material and
    operating cash flow swings with trading and lending, so they would mislead.
    """
    notes: list[str] = []
    market_cap = None
    if price is not None and shares is not None:
        market_cap = round(price["value"] * shares["value"])
    else:
        notes.append("market_cap: price or shares outstanding missing")
    enterprise_value = None
    if market_cap is not None and balance is not None:
        parts = [balance.get("total_debt"), balance.get("cash")]
        if None in parts:
            notes.append("enterprise_value: total_debt or cash missing in the latest balance sheet")
        else:
            investments = balance.get("short_term_investments")
            if investments is None:
                notes.append("enterprise_value: short_term_investments not reported, treated as none")
            enterprise_value = market_cap + parts[0] - parts[1] - (investments or 0)
    ttm = ttm or {}
    fcf = free_cash_flow(ttm)
    ebitda = None
    if ttm.get("operating_income") is not None and ttm.get("depreciation_amortization") is not None:
        ebitda = ttm["operating_income"] + ttm["depreciation_amortization"]

    def multiple(name: str, value, denominator):
        if value is None or denominator is None:
            return None
        if denominator <= 0:
            notes.append(f"{name}: not meaningful, the denominator is zero or negative")
            return None
        return round(value / denominator, 2)

    result = {
        "basis": ttm.get("basis"),
        "ttm_period_end": ttm.get("period_end"),
        "price_date": price["date"] if price else None,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "pe": multiple("pe", market_cap, ttm.get("net_income")),
        "ev_revenue": multiple("ev_revenue", enterprise_value, ttm.get("revenue")),
        "ev_ebit": multiple("ev_ebit", enterprise_value, ttm.get("operating_income")),
        "ev_ebitda": multiple("ev_ebitda", enterprise_value, ebitda),
        "p_fcf": multiple("p_fcf", market_cap, fcf),
        "fcf_yield": ratio(fcf, market_cap) if market_cap else None,
        "notes": notes,
    }
    if financial:
        names = ("enterprise_value", "ev_revenue", "ev_ebit", "ev_ebitda", "p_fcf", "fcf_yield")
        notes[:] = [n for n in notes if n.split(":")[0] not in names]
        for name in names:
            result[name] = None
            notes.append(f"{name}: {NOT_MEANINGFUL}")
    return result
