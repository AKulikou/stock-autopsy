"""Small hand-built SEC inputs for data layer tests: each test states only the facts it is about."""

from datetime import date

from datalayer.fetch import RawCompanyData

AS_OF = date(2026, 10, 15)
SHARE_CONCEPTS = {"WeightedAverageNumberOfDilutedSharesOutstanding", "EntityCommonStockSharesOutstanding"}

# Calendar fiscal years.
FY2024 = ("2024-01-01", "2024-12-31")
FY2025 = ("2025-01-01", "2025-12-31")


def fact(val, end, start=None, filed="2026-02-20", form="10-K", accn=None):
    item = {
        "end": end,
        "val": val,
        "filed": filed,
        "form": form,
        "accn": accn or f"acc-{form}-{filed}",
        "fy": 0,
        "fp": "FY",
    }
    if start:
        item["start"] = start
    return item


def annual(val, period, filed="2026-02-20", form="10-K"):
    return fact(val, period[1], start=period[0], filed=filed, form=form)


def instant(val, end, filed="2026-02-20", form="10-K"):
    return fact(val, end, filed=filed, form=form)


def company_facts(gaap: dict, dei: dict | None = None) -> dict:
    def taxonomy(concepts: dict) -> dict:
        return {
            concept: {"units": {"shares" if concept in SHARE_CONCEPTS else "USD": items}}
            for concept, items in concepts.items()
        }

    return {
        "cik": 1,
        "entityName": "TEST CO",
        "facts": {"us-gaap": taxonomy(gaap), "dei": taxonomy(dei or {})},
    }


def base_gaap() -> dict:
    """Two complete fiscal years: revenue and net income, filed in each year's 10-K."""
    return {
        "Revenues": [annual(100, FY2024, filed="2025-02-20"), annual(120, FY2025)],
        "NetIncomeLoss": [annual(10, FY2024, filed="2025-02-20"), annual(12, FY2025)],
        "Assets": [instant(500, "2024-12-31", filed="2025-02-20"), instant(550, "2025-12-31")],
    }


def submissions(rows: list[tuple[str, str, str, str]] | None = None) -> dict:
    """Filing history from (form, filed, report_date, items) rows."""
    rows = rows or [("10-K", "2026-02-20", "2025-12-31", ""), ("10-K", "2025-02-20", "2024-12-31", "")]
    return {
        "sic": "2080",
        "sicDescription": "Beverages",
        "fiscalYearEnd": "1231",
        "filings": {
            "recent": {
                "form": [r[0] for r in rows],
                "filingDate": [r[1] for r in rows],
                "reportDate": [r[2] for r in rows],
                "items": [r[3] for r in rows],
            },
            "files": [],
        },
    }


PRICE = {
    "close": 10.0,
    "date": "2026-10-14",
    "currency": "USD",
    "market_cap_reported": None,
    "shares_reported": None,
    "splits": [],
    "source": "test prices",
}


def raw(
    gaap: dict | None = None, dei: dict | None = None, price=PRICE, subs=None, as_of=AS_OF
) -> RawCompanyData:
    status = {
        "edgar_companyfacts": "ok",
        "edgar_submissions": "ok" if subs is not False else "failed",
        "yfinance": "ok" if price is not None else "failed",
    }
    return RawCompanyData(
        ticker="TEST",
        cik=1,
        company_name="TEST CO",
        as_of=as_of,
        company_facts=company_facts(base_gaap() if gaap is None else gaap, dei),
        submissions=None if subs is False else (subs or submissions()),
        price=price,
        fetch_status=status,
    )
