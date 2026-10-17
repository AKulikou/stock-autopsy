"""
Calculated (DERIVED) claims built from the golden packs, right and with deliberate
errors, for the mutation test of the calculation check (tests/test_grounding.py).

Four kinds, each worded the way analysts write them:
- change:   "Revenue fell by about $1.2 billion in FY2025."        basis: FY2025.x - FY2024.x
- growth:   "Revenue grew about 3.4% in FY2025."                    basis: FY2025.x / FY2024.x - 1
- spread:   "Costs below gross profit fell by about $3.0 billion."  basis: (gp - oi) FY2024 - (gp - oi) FY2025
- leverage: "Net debt is about $32.7 billion, about 2.1 times operating income."
            basis: (debt - cash - short-term investments) / operating income (the numerator
            is a sub-expression; no direction word, so it has no flipped variant)

Errors: the reported amount times 1.1, 0.75, 2 or 10, and the direction word flipped.
A pack-value literal in a basis is not used: the check must find the numbers itself.
"""

import json
from pathlib import Path

GOLDEN = Path(__file__).parent / "fixtures" / "golden"
TICKERS = ("KO", "SNOW", "KHC", "CMCSA", "PLUG")
FACTORS = (1.1, 0.75, 2.0, 10.0)
FIELDS = ("revenue", "operating_income", "gross_profit", "operating_cash_flow", "net_income")


def _billions(value: float) -> str:
    return f"${abs(value) / 1e9:.2f} billion"


def _row(pack: dict, year: int) -> dict | None:
    return next((r for r in pack["financials_annual"] if r["fiscal_year"] == year), None)


def _ok(*values) -> bool:
    return all(isinstance(v, int | float) and abs(v) > 1e8 for v in values)


def claims(factor: float = 1.0, flip: bool = False) -> list[tuple[str, dict, dict]]:
    """(kind, claim, pack) for every case the golden packs allow, mutated as asked."""
    out = []
    for ticker in TICKERS:
        pack = json.loads((GOLDEN / ticker / "pack.json").read_text(encoding="utf-8"))
        years = [r["fiscal_year"] for r in pack["financials_annual"]]
        for year in years[1:]:
            now, before = _row(pack, year), _row(pack, year - 1)
            if before is None:
                continue
            for name in FIELDS:
                a, b = now.get(name), before.get(name)
                if not _ok(a, b) or a == b or a <= 0 or b <= 0:
                    continue
                change = a - b
                up = (change > 0) != flip
                verb = "rose" if up else "fell"
                out.append(("change", {
                    "statement": f"The {name.replace('_', ' ')} {verb} by about {_billions(change * factor)} "
                                 f"in FY{year}.",
                    "basis": f"financials_annual.FY{year}.{name} - financials_annual.FY{year - 1}.{name}",
                }, pack))
                growth = a / b - 1
                if abs(growth) >= 0.01:
                    verb = "grew" if up else "fell"
                    out.append(("growth", {
                        "statement": f"The {name.replace('_', ' ')} {verb} about {abs(growth * factor):.1%} "
                                     f"in FY{year}.",
                        "basis": f"financials_annual.FY{year}.{name} / "
                                 f"financials_annual.FY{year - 1}.{name} - 1",
                    }, pack))
            gp0, oi0, gp1, oi1 = (before.get("gross_profit"), before.get("operating_income"),
                                  now.get("gross_profit"), now.get("operating_income"))
            if _ok(gp0, oi0, gp1, oi1):
                fall = (gp0 - oi0) - (gp1 - oi1)
                if abs(fall) > 1e8:
                    verb = ("fell" if fall > 0 else "rose") if not flip else ("rose" if fall > 0 else "fell")
                    out.append(("spread", {
                        "statement": f"Costs below gross profit {verb} by about {_billions(fall * factor)} "
                                     f"in FY{year}.",
                        "basis": f"(financials_annual.FY{year - 1}.gross_profit - "
                                 f"financials_annual.FY{year - 1}.operating_income) - "
                                 f"(financials_annual.FY{year}.gross_profit - "
                                 f"financials_annual.FY{year}.operating_income)",
                    }, pack))
            debt, cash, oi = now.get("total_debt"), now.get("cash"), now.get("operating_income")
            investments = now.get("short_term_investments")
            if _ok(debt, cash, oi, investments) and debt > cash + investments and oi > 0 and not flip:
                net = debt - cash - investments
                out.append(("leverage", {
                    "statement": f"Net debt is about {_billions(net * factor)}, about "
                                 f"{net / oi * factor:.1f} times operating income.",
                    "basis": f"(financials_annual.FY{year}.total_debt - financials_annual.FY{year}.cash - "
                             f"financials_annual.FY{year}.short_term_investments) / "
                             f"financials_annual.FY{year}.operating_income",
                }, pack))
    return out
