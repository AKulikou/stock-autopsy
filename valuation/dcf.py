"""
Discounted cash flow on the valuation evaluator's assumptions (decision D4:
base DCF for bear / base / bull, reverse DCF and one-at-a-time sensitivities;
the full sensitivity grid is Phase 2).

Free cash flow to the firm, years 1-5:
    revenue_t = revenue_(t-1) * (1 + growth_t), starting from TTM revenue
    NOPAT_t   = revenue_t * margin_t * (1 - tax)   (no tax credit on a loss)
    FCFF_t    = NOPAT_t - revenue_t * (capex% - D&A%) - NWC% * (revenue_t - revenue_(t-1))
Terminal value at year 5: FCFF of year 6 (revenue grows at terminal growth, the
year-5 margin holds) / (discount rate - terminal growth).
Equity = enterprise value - total debt + cash + short-term investments.

Every input comes from the pack; a missing input stops the calculation with a
reason, never a zero.
"""

from dataclasses import asdict, dataclass

from datalayer.sector import NOT_MEANINGFUL
from evaluators.schemas import ScenarioAssumptions

SCENARIOS = ("bear", "base", "bull")
REVERSE_GROWTH_RANGE = (-0.5, 1.0)
IMPLIED_RETURN_MARGIN = 0.005  # the lowest rate tried is terminal growth + this
IMPLIED_RETURN_MAX = 0.5
SENSITIVITY_STEPS = {
    "discount_rate": 0.01,
    "terminal_growth": 0.005,
    "operating_margin": 0.02,
    "revenue_growth": 0.02,
}


@dataclass(frozen=True)
class DcfInputs:
    revenue: float
    shares: float
    total_debt: float
    cash_and_investments: float
    price: float | None
    currency: str | None = None


def inputs_from_pack(pack: dict) -> tuple[DcfInputs | None, list[str]]:
    """The DCF inputs, or None and the reasons the DCF cannot run."""
    reasons = []
    ttm = pack.get("ttm") or {}
    balance = pack.get("balance_sheet_latest") or {}
    shares = pack.get("shares_outstanding") or {}
    if not ttm.get("revenue") or ttm["revenue"] <= 0:
        reasons.append("TTM revenue is missing or not positive")
    if not shares.get("value"):
        reasons.append("shares outstanding are missing")
    if balance.get("total_debt") is None:
        reasons.append("total debt is unknown (equity value needs it)")
    if balance.get("cash") is None:
        reasons.append("cash is unknown (equity value needs it)")
    if reasons:
        return None, reasons
    price = (pack.get("price") or {}).get("value")
    currency = (pack.get("price") or {}).get("currency")
    notes = []
    investments = balance.get("short_term_investments")
    if investments is None:
        notes.append("short-term investments not reported: equity value counts cash only")
    return (
        DcfInputs(
            revenue=ttm["revenue"],
            shares=shares["value"],
            total_debt=balance["total_debt"],
            cash_and_investments=balance["cash"] + (investments or 0),
            price=price,
            currency=currency,
        ),
        notes,
    )


def project(s: ScenarioAssumptions, inputs: DcfInputs) -> dict:
    r, g_terminal = s.discount_rate, s.terminal_growth
    reinvest_rate = s.capex_pct_revenue - s.da_pct_revenue

    def fcff(revenue: float, previous: float, margin: float) -> tuple[float, float]:
        ebit = revenue * margin
        nopat = ebit * (1 - s.tax_rate) if ebit > 0 else ebit
        return ebit, nopat - revenue * reinvest_rate - s.nwc_pct_revenue_change * (revenue - previous)

    years = []
    previous = inputs.revenue
    present_value = 0.0
    for t, (growth, margin) in enumerate(zip(s.revenue_growth, s.operating_margin, strict=True), start=1):
        revenue = previous * (1 + growth)
        ebit, cash_flow = fcff(revenue, previous, margin)
        discounted = cash_flow / (1 + r) ** t
        present_value += discounted
        years.append(
            {
                "year": t,
                "revenue": round(revenue),
                "operating_income": round(ebit),
                "fcff": round(cash_flow),
                "present_value": round(discounted),
            }
        )
        previous = revenue
    terminal_revenue = previous * (1 + g_terminal)
    _, terminal_fcff = fcff(terminal_revenue, previous, s.operating_margin[-1])
    terminal_value = terminal_fcff / (r - g_terminal)
    terminal_pv = terminal_value / (1 + r) ** len(years)
    enterprise_value = present_value + terminal_pv
    equity_value = enterprise_value - inputs.total_debt + inputs.cash_and_investments
    return {
        "years": years,
        "terminal_value": round(terminal_value),
        "terminal_value_share_of_ev": round(terminal_pv / enterprise_value, 4)
        if enterprise_value > 0
        else None,
        "enterprise_value": round(enterprise_value),
        "equity_value": round(equity_value),
        "value_per_share": round(equity_value / inputs.shares, 2),
    }


def _with(s: ScenarioAssumptions, **changes) -> ScenarioAssumptions:
    return ScenarioAssumptions(**{**s.model_dump(), **changes})


def reverse_dcf(base: ScenarioAssumptions, inputs: DcfInputs) -> dict:
    """The constant revenue growth (years 1-5) at which the base case equals the price."""
    if inputs.price is None:
        return {"implied_revenue_growth": None, "reason": "price unknown"}

    def value(growth: float) -> float:
        return project(_with(base, revenue_growth=[growth] * 5), inputs)["value_per_share"] - inputs.price

    low, high = REVERSE_GROWTH_RANGE
    v_low, v_high = value(low), value(high)
    if v_low * v_high > 0:
        return {
            "implied_revenue_growth": None,
            "reason": "no constant growth between -50% and +100% a year reaches the price with the base-case "
            "margins, discount rate and terminal growth",
        }
    for _ in range(80):
        middle = (low + high) / 2
        v_middle = value(middle)
        if v_low * v_middle <= 0:
            high = middle
        else:
            low, v_low = middle, v_middle
    return {
        "implied_revenue_growth": round((low + high) / 2, 4),
        # The condition the growth holds under: the return it earns and for how long it must last.
        "discount_rate": base.discount_rate,
        "years": 5,
        "holding": "base-case operating margins, tax, reinvestment, discount rate and terminal growth",
    }


def implied_annual_return(base: ScenarioAssumptions, inputs: DcfInputs) -> dict:
    """
    The discount rate at which the base-case cash flows are worth today's price: the
    yearly return a buyer at this price gets if the base case comes true. Unlike the
    implied growth, it does not depend on the discount rate the model chose.
    """
    if inputs.price is None:
        return {"implied_annual_return": None, "reason": "price unknown"}

    def value(rate: float) -> float:
        return project(_with(base, discount_rate=rate), inputs)["value_per_share"] - inputs.price

    low, high = base.terminal_growth + IMPLIED_RETURN_MARGIN, IMPLIED_RETURN_MAX
    v_low, v_high = value(low), value(high)
    if v_low < 0:
        return {
            "implied_annual_return": None,
            "below": round(low, 4),
            "reason": f"even at a return of {low:.1%} a year the base case is worth less than the price",
        }
    if v_high > 0:
        return {
            "implied_annual_return": None,
            "above": IMPLIED_RETURN_MAX,
            "reason": "the base case is worth more than the price even at a return of "
            f"{IMPLIED_RETURN_MAX:.0%} a year",
        }
    for _ in range(80):
        middle = (low + high) / 2
        if value(middle) > 0:
            low = middle
        else:
            high = middle
    return {
        "implied_annual_return": round((low + high) / 2, 4),
        "holding": "base-case revenue growth, operating margins, tax, reinvestment and terminal growth",
    }


def path_words(name: str, first: float, last: float, unit: str = "") -> str:
    """'revenue growth of 4% a year', or '... slowing from 5% to 3% a year' / 'rising from ... to ...'."""
    start, end = f"{first:.0%}", f"{last:.0%}"
    if start == end:
        return f"{name} of {start}{unit}"
    direction = "rising" if last > first else ("slowing" if "growth" in name else "falling")
    return f"{name} {direction} from {start} to {end}{unit}"


def price_words(price: float, currency: str | None) -> str:
    """"$93.90" for US dollars, "93.90 EUR" for another currency, the bare number when it is unknown."""
    if currency == "USD":
        return f"${price:,.2f}"
    return f"{price:,.2f} {currency}" if currency else f"{price:,.2f}"


def price_assumes(base: ScenarioAssumptions, inputs: DcfInputs, implied: dict) -> str | None:
    """One plain sentence on what today's price assumes, filled in by Python, not the model."""
    if inputs.price is None:
        return None
    price = price_words(inputs.price, inputs.currency)
    growth = path_words("revenue growth", base.revenue_growth[0], base.revenue_growth[-1], " a year")
    margin = path_words("an operating margin", base.operating_margin[0], base.operating_margin[-1])
    case = f"{growth} and {margin} over five years"
    rate = implied.get("implied_annual_return")
    if rate is not None:
        return (
            f"At today's price of {price}, if the base case comes true ({case}), "
            f"a buyer earns about {rate:.1%} a year."
        )
    if "below" in implied:
        return (
            f"At today's price of {price}, the base case ({case}) does not pay back the price "
            f"even at a return of {implied['below']:.1%} a year: the price assumes more than the base case."
        )
    return (
        f"At today's price of {price}, the base case ({case}) would pay more than "
        f"{IMPLIED_RETURN_MAX:.0%} a year: the price assumes much less than the base case."
    )


def sensitivities(base: ScenarioAssumptions, inputs: DcfInputs) -> list[dict]:
    """Base-case value per share when one assumption moves up or down, largest effect first."""
    reference = project(base, inputs)["value_per_share"]
    rows = []
    for name, step in SENSITIVITY_STEPS.items():
        values = {}
        for direction, delta in (("down", -step), ("up", step)):
            if name in ("operating_margin", "revenue_growth"):
                changed = _with(base, **{name: [v + delta for v in getattr(base, name)]})
            else:
                changed = _with(base, **{name: getattr(base, name) + delta})
            if changed.terminal_growth >= changed.discount_rate:
                values[direction] = None
                continue
            values[direction] = project(changed, inputs)["value_per_share"]
        effect = max((abs(v - reference) for v in values.values() if v is not None), default=0.0)
        rows.append(
            {
                "assumption": name,
                "step": step,
                "value_down": values["down"],
                "value_up": values["up"],
                "largest_change_per_share": round(effect, 2),
            }
        )
    return sorted(rows, key=lambda row: row["largest_change_per_share"], reverse=True)


def run_valuation(scenarios: dict[str, ScenarioAssumptions], pack: dict) -> dict:
    """Everything the valuation step B and the report need; None values carry a reason."""
    if pack.get("financial_company"):
        return {"computed": False, "reasons": [
            f"DCF {NOT_MEANINGFUL}: debt is the raw material of the business and its cash flows are "
            "not free cash flows in the usual sense"]}
    inputs, notes = inputs_from_pack(pack)
    if inputs is None:
        return {"computed": False, "reasons": notes}
    results = {name: project(scenarios[name], inputs) for name in SCENARIOS}
    implied = implied_annual_return(scenarios["base"], inputs)
    return {
        "computed": True,
        "inputs": asdict(inputs),
        "notes": notes,
        "scenarios": results,
        "value_per_share": {name: results[name]["value_per_share"] for name in SCENARIOS},
        "price": inputs.price,
        "reverse_dcf": reverse_dcf(scenarios["base"], inputs),
        "implied_return": implied,
        "price_assumes": price_assumes(scenarios["base"], inputs, implied),
        "sensitivities": sensitivities(scenarios["base"], inputs),
    }
