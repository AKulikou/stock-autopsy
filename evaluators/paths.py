"""
Pack paths: how a claim points at a value in the DATA PACK.

Dotted keys; rows of financials_annual and derived.annual are addressed by fiscal
year, quarters by fiscal year and quarter, other list items by position:

    financials_annual.FY2025.revenue
    derived.annual.FY2024.gross_margin
    financials_quarterly.FY2026Q2.net_income
    ttm.operating_cash_flow
    filing_events.0.event
"""

import re
from typing import Any

PATH_HELP = (
    "Pack paths are dotted keys. Address rows of financials_annual and derived.annual by fiscal year "
    "(financials_annual.FY2025.revenue), quarters by fiscal year and quarter "
    "(financials_quarterly.FY2026Q2.revenue), and other list items by position (filing_events.0.event). "
    "Values Python computed are under derived: multiples in derived.valuation (derived.valuation.pe), "
    "margins and free cash flow in derived.annual and derived.ttm (derived.ttm.free_cash_flow)."
)

_YEAR = re.compile(r"^FY(\d{4})$")
_QUARTER = re.compile(r"^FY(\d{4})Q([1-4])$")


class PathError(LookupError):
    """The path does not name a value in the pack."""


def _step(node: Any, part: str, path: str) -> Any:
    if isinstance(node, dict):
        if part not in node:
            raise PathError(f"{path}: no key {part!r}")
        return node[part]
    if isinstance(node, list):
        year, quarter = _YEAR.match(part), _QUARTER.match(part)
        if year or quarter:
            wanted_year = int((year or quarter).group(1))
            for row in node:
                if not isinstance(row, dict) or row.get("fiscal_year") != wanted_year:
                    continue
                if quarter and row.get("fiscal_quarter") != int(quarter.group(2)):
                    continue
                if not quarter and "fiscal_quarter" in row:
                    continue
                return row
            raise PathError(f"{path}: no row {part}")
        if part.isdigit() and int(part) < len(node):
            return node[int(part)]
        raise PathError(f"{path}: no list item {part!r}")
    raise PathError(f"{path}: {part!r} goes past a value")


_PATH = re.compile(r"[A-Za-z_]\w*(?:\.\w+)*")


def basis_paths(basis: str) -> list[str]:
    """
    The pack paths in a DATA claim's basis. Several paths are separated by ';' or
    ','; text after a path (a parenthetical note, 'is null', '= not_fetched') is
    ignored. A part that does not start with a path yields nothing.
    """
    paths = []
    for part in re.split(r"[;,]", basis):
        match = _PATH.match(part.strip().strip("`").strip())
        if match:
            paths.append(match.group(0).rstrip("."))
    return paths


def resolve_basis(pack: dict, basis: str) -> tuple[list[Any], list[str]]:
    """(values of the paths that resolve, the paths that do not)."""
    values, bad = [], []
    paths = basis_paths(basis)
    for path in paths:
        try:
            values.append(resolve(pack, path))
        except PathError:
            bad.append(path)
    if not paths:
        bad.append(basis.strip() or "(empty)")
    return values, bad


def resolve(pack: dict, path: str) -> Any:
    """The value at `path`.

    Raises:
        PathError: if the path does not exist
    """
    clean = path.strip().strip("`").removeprefix("data_pack.").removeprefix("pack.")
    if not clean:
        raise PathError("empty path")
    node: Any = pack
    for part in clean.split("."):
        node = _step(node, part, clean)
    return node
