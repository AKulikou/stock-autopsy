"""
The DATA PACK: one JSON document per ticker per day that every evaluator gets
byte-identical (schema in docs/stock_autopsy_prompts.md, extended where a Phase 1
evaluator needs more: filing events, derived metrics, the latest balance sheet).

build_pack() also returns the provenance of each value (concept, filing,
accession number). Provenance stays out of the prompt to keep it short; the
number-check after a run and a human reviewer use it.

    python -m datalayer.pack KO          # fetch (cached), build, save, print a summary
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import replace
from datetime import date

from core.shared_context import canonical_json, sha256_of
from datalayer import derived
from datalayer.cache import DailyCache
from datalayer.extensions import EXTENSION_MATCHERS, EXTENSION_TAXONOMY, matching_concepts
from datalayer.fetch import OK, DataUnavailableError, RawCompanyData, fetch_company
from datalayer.filings import annual_report_timing, coverage_start, filing_events, filing_rows
from datalayer.financials import STALE_SHARES_DAYS, Financials, Split, real_splits
from datalayer.line_items import ALL_CONCEPTS, SHARES_OUTSTANDING_CONCEPT
from datalayer.quality import NOT_FETCHED, PROVIDER_ERROR, DataQuality
from datalayer.sec import SecClient
from datalayer.xbrl import load_facts

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
DEFAULT_USER_CONTEXT = {"horizon": "5y", "risk_tolerance": "medium"}
HORIZONS = ("1y", "5y", "10y")
RISK_TOLERANCES = ("low", "medium", "high")
# Two sources whose values differ by more than this share are recorded as a conflict;
# a factor of ORDER_OF_MAGNITUDE or more is a units or scale bug until proven otherwise.
CONFLICT_THRESHOLD = 0.02
# Above this difference a stale EDGAR value gives way to the fresher source.
STALE_CONFLICT_THRESHOLD = 0.05
ORDER_OF_MAGNITUDE = 8
PERIODIC_FORMS = ("10-K", "10-Q", "10-KT")


def check_user_context(context: dict) -> dict:
    if context.get("horizon") not in HORIZONS or context.get("risk_tolerance") not in RISK_TOLERANCES:
        raise ValueError(f"user_context needs horizon in {HORIZONS} and risk_tolerance in {RISK_TOLERANCES}")
    return {"horizon": context["horizon"], "risk_tolerance": context["risk_tolerance"]}


def positive_or_none(value, field_name: str, quality: DataQuality) -> float | None:
    """Rule 2: a zero (or negative) price, share count or market cap from a provider is unknown."""
    if value is None:
        return None
    if value <= 0:
        quality.note(f"{field_name}: provider returned {value}; treated as unknown, not as zero")
        return None
    return value


def compare_sources(
    field_name: str, edgar, yahoo, quality: DataQuality, dates: dict, edgar_stale: bool = False
) -> str:
    """
    Rule 7: record both values when EDGAR and Yahoo disagree. EDGAR is used, unless
    its value is stale and the two differ by more than STALE_CONFLICT_THRESHOLD: then
    the fresher Yahoo value is used and the entry says why. Returns the source used.
    """
    if edgar is None or yahoo is None:
        return "edgar"
    largest = max(abs(edgar), abs(yahoo))
    if largest == 0 or abs(edgar - yahoo) / largest <= CONFLICT_THRESHOLD:
        return "edgar"
    used = "yfinance" if edgar_stale and abs(edgar - yahoo) / largest > STALE_CONFLICT_THRESHOLD else "edgar"
    entry = {"field": field_name, "values": {"edgar": edgar, "yfinance": yahoo}, "used": used, "dates": dates}
    if used == "yfinance":
        entry["reason"] = "the EDGAR value is stale and differs by more than 5%; the fresher source is used"
    quality.source_conflicts.append(entry)
    factor = largest / max(min(abs(edgar), abs(yahoo)), 1)
    if factor >= ORDER_OF_MAGNITUDE:
        quality.note(
            f"{field_name}: EDGAR and Yahoo differ by a factor of {factor:.0f}: a units or scale bug "
            "until proven otherwise"
        )
    return used


def use_extensions(raw: RawCompanyData, facts: dict, quality: DataQuality) -> dict[str, tuple[str, ...]]:
    """
    Add the company extension concept chosen for each line item to `facts` (keyed
    'ext:<concept>') and return them per line item. Two candidates for one line
    item are ambiguous: neither is used, and a note says so.
    """
    if "edgar_extensions" in raw.fetch_status:
        quality.fetch_status["edgar_extensions"] = raw.fetch_status["edgar_extensions"]
    if not raw.extension_facts:
        return {}
    chosen: dict[str, tuple[str, ...]] = {}
    for key in EXTENSION_MATCHERS:
        groups = matching_concepts(raw.extension_facts, key)
        if len(groups) > 1:
            names = ", ".join(group[0] for group in groups)
            quality.note(f"{key}: several company-specific concepts could hold it ({names}); none used")
            continue
        if not groups:
            continue
        loaded, _ = load_facts(raw.extension_facts, raw.as_of, set(groups[0]), taxonomy=EXTENSION_TAXONOMY)
        for name, items in loaded.items():
            facts[f"ext:{name}"] = [replace(f, concept=f"ext:{name}") for f in items]
        chosen[key] = tuple(f"ext:{name}" for name in groups[0])
    return chosen


def note_extension_periods(fin: Financials, quality: DataQuality) -> None:
    """Say which values came from a company extension concept: its definition can differ."""
    used: dict[tuple[str, str], list[str]] = {}
    spelling: dict[tuple[str, str], str] = {}  # one note per concept, whatever its spelling
    for key, source in fin.provenance.items():
        concept = source.get("concept", "")
        if concept.startswith("ext:"):
            period, field_name = key.split(".", 1)
            used.setdefault((field_name, concept.lower()), []).append(
                "the latest balance sheet" if period == "balance" else period
            )
            spelling[(field_name, concept.lower())] = concept
    for (field_name, lowered), periods in used.items():
        concept = spelling[(field_name, lowered)]
        quality.note(
            f"{field_name} for {', '.join(periods)} comes from the company's own XBRL concept "
            f"{concept.removeprefix('ext:')}, not a us-gaap concept: its definition can differ from the "
            "us-gaap concept of other periods (it may include more, such as contract assets); do not trend "
            "the line item across the switch"
        )


# Growth metrics and the line item each compares year over year.
GROWTH_OF = {"receivables_growth": "accounts_receivable"}


def no_growth_across_switch(metrics: list[dict], provenance: dict, quality: DataQuality) -> list[dict]:
    """
    A growth rate between a year read from a us-gaap concept and a year read from
    a company extension concept compares two definitions: it is set to None and noted.
    """
    def source(year: int, field_name: str) -> str:
        concept = provenance.get(f"FY{year}.{field_name}", {}).get("concept", "")
        return "ext" if concept.startswith("ext:") else "us-gaap"

    for row in metrics:
        year = row["fiscal_year"]
        for growth, field_name in GROWTH_OF.items():
            if row.get(growth) is not None and source(year, field_name) != source(year - 1, field_name):
                row[growth] = None
                quality.note(
                    f"{growth} FY{year}: not computed, {field_name} changes definition between FY{year - 1} "
                    f"and FY{year} (us-gaap concept to the company's own concept or back)"
                )
    return metrics


def check_freshness(rows: list[dict], facts: dict, as_of: date, quality: DataQuality) -> None:
    """
    Company facts can lag the filings: a 10-Q in the filing history whose period
    is not yet in the facts means the TTM and the balance sheet are a quarter old.
    """
    periodic = [
        r
        for r in rows
        if r["form"] in PERIODIC_FORMS and r["report_date"] and date.fromisoformat(r["filed"]) <= as_of
    ]
    if not periodic:
        return
    newest = max(periodic, key=lambda r: r["report_date"])
    latest_fact_end = max(
        (f.end for concept, items in facts.items() if not concept.startswith("ext:") for f in items),
        default=None,
    )
    if latest_fact_end is None or date.fromisoformat(newest["report_date"]) <= latest_fact_end:
        return
    covers = f"periods up to {latest_fact_end.isoformat()} only"
    quality.add_partial("ttm", covers)
    quality.add_partial("balance_sheet_latest", covers)
    quality.note(
        f"The {newest['form']} for the period ending {newest['report_date']} (filed {newest['filed']}) "
        "is not yet in SEC company facts: TTM, quarters and the latest balance sheet end "
        f"{latest_fact_end.isoformat()}"
    )


def fiscal_year_end(raw: RawCompanyData, last_period_end: str | None, quality: DataQuality) -> str | None:
    reported = (raw.submissions or {}).get("fiscalYearEnd")
    if reported and len(reported) == 4:
        return f"{reported[:2]}-{reported[2:]}"
    if last_period_end:
        quality.note("fiscal_year_end taken from the last annual period end (filing history unavailable)")
        return last_period_end[5:]
    return None


def build_pack(raw: RawCompanyData, user_context: dict | None = None) -> tuple[dict, dict]:
    """(pack, provenance) for one ticker."""
    quality = DataQuality()
    quality.fetch_status = {
        "edgar_companyfacts": raw.fetch_status.get("edgar_companyfacts", NOT_FETCHED),
        "edgar_submissions": raw.fetch_status.get("edgar_submissions", NOT_FETCHED),
        "yfinance": raw.fetch_status.get("yfinance", NOT_FETCHED),
        "form4": NOT_FETCHED,
        "transcript": "absent",
    }
    as_of = raw.as_of

    # Price and splits (Yahoo).
    price = None
    splits = None
    if raw.price:
        close = positive_or_none(raw.price.get("close"), "price", quality)
        if close is not None:
            # Yahoo returns float32 noise (91.77999877929688); four decimals are exact enough.
            price = {
                "value": round(close, 4),
                "currency": raw.price["currency"],
                "date": raw.price["date"],
                "source": raw.price["source"] + ", close of the last trading day before as_of",
            }
        splits = real_splits(
            [Split(date.fromisoformat(s["date"]), float(s["ratio"])) for s in raw.price.get("splits", [])],
            quality,
        )
    if price is None:
        quality.missing("price", "latest", PROVIDER_ERROR)
    if splits is None:
        quality.add_partial("shares_diluted", "split history unavailable: share counts not split-adjusted")

    # Financial statements (EDGAR).
    facts, dropped = load_facts(raw.company_facts, as_of, ALL_CONCEPTS)
    dei, dropped_dei = load_facts(raw.company_facts, as_of, {SHARES_OUTSTANDING_CONCEPT}, taxonomy="dei")
    if dropped + dropped_dei:
        quality.note(
            f"{dropped + dropped_dei} facts with a period end or filing date after as_of were dropped"
        )
        logger.info(f"{raw.ticker}: dropped {dropped + dropped_dei} facts dated after {as_of}")
    extension_concepts = use_extensions(raw, facts, quality)
    fin = Financials(facts, as_of, quality, splits, extension_concepts=extension_concepts)
    periods = fin.fiscal_years()
    annual = fin.annual_rows(periods)
    quarterly = fin.quarterly_rows(periods)
    ttm = fin.ttm(periods)
    balance = fin.latest_balance()
    note_extension_periods(fin, quality)
    shares = fin.shares_outstanding(dei.get(SHARES_OUTSTANDING_CONCEPT, []))

    # Cross-checks against Yahoo (rule 7).
    if raw.price:
        yahoo_shares = positive_or_none(raw.price.get("shares_reported"), "yfinance shares", quality)
        yahoo_cap = positive_or_none(raw.price.get("market_cap_reported"), "yfinance market cap", quality)
        if shares:
            stale = (as_of - date.fromisoformat(shares["date"])).days > STALE_SHARES_DAYS
            used = compare_sources(
                "shares_outstanding",
                shares["value"],
                yahoo_shares,
                quality,
                {"edgar": shares["date"], "yfinance": raw.price["date"]},
                edgar_stale=stale,
            )
            if used == "yfinance":
                shares = {
                    "value": yahoo_shares,
                    "date": raw.price["date"],
                    "source": f"{raw.price['source']} (reported share count); the SEC count dated "
                    f"{shares['date']} is stale",
                }
    valuation = derived.valuation(price, shares, ttm, balance)
    if raw.price:
        compare_sources(
            "market_cap",
            valuation["market_cap"],
            yahoo_cap,
            quality,
            {"edgar_shares": shares["date"] if shares else None, "price": raw.price["date"]},
        )

    # Filing history events (EDGAR submissions).
    events = None
    timing = None
    if raw.submissions:
        rows = filing_rows(raw.submissions, raw.older_submissions)
        since = date.fromisoformat(annual[0]["period_start"]) if annual else as_of
        events = filing_events(rows, since, as_of)
        timing = annual_report_timing(rows, since, as_of)
        first = coverage_start(rows)
        if first and first > since:
            quality.add_partial("filing_events", f"filings from {first.isoformat()} on only")
        check_freshness(rows, facts, as_of, quality)
    else:
        quality.missing("filing_events", "all", PROVIDER_ERROR)

    for name in ("insider_transactions_12m", "peers", "peer_multiples", "news_items", "earnings_transcript"):
        quality.missing(name, "all", NOT_FETCHED)
    if not periods:
        quality.missing("financials_annual", "all", "tag_not_found")

    submissions = raw.submissions or {}
    pack = {
        "schema_version": SCHEMA_VERSION,
        "ticker": raw.ticker,
        "company_name": raw.company_name,
        "cik": raw.cik,
        "sic": submissions.get("sic"),
        "sic_description": submissions.get("sicDescription"),
        "as_of": as_of.isoformat(),
        "fiscal_year_end": fiscal_year_end(raw, annual[-1]["period_end"] if annual else None, quality),
        "units": "Money in USD as absolute values (not thousands); share counts as numbers of shares; "
        "ratios as decimals (0.25 = 25%).",
        "sources": {
            "financial_statements": "SEC EDGAR company facts (XBRL), filings filed on or before as_of",
            "filing_history": "SEC EDGAR submissions",
            "price": price["source"] if price else None,
        },
        "price": price,
        "shares_outstanding": shares,
        "financials_annual": annual,
        "financials_quarterly": quarterly,
        "ttm": ttm,
        "balance_sheet_latest": balance,
        "derived": {
            "annual": no_growth_across_switch(derived.annual_metrics(annual), fin.provenance, quality),
            "ttm": derived.margins(ttm) if ttm else None,
            "revenue_cagr_3y": derived.revenue_cagr(annual, 3),
            "revenue_cagr_5y": derived.revenue_cagr(annual, 5),
            "valuation": valuation,
            "formulas": derived.FORMULAS,
        },
        "filing_events": events,
        "annual_report_timing": timing,
        "peers": None,
        "peer_multiples": None,
        "insider_transactions_12m": None,
        "earnings_transcript": None,
        "news_items": None,
        "user_context": check_user_context(user_context or DEFAULT_USER_CONTEXT),
        "data_quality": quality.as_dict(),
    }
    return pack, fin.provenance


NO_STATEMENTS = (
    "SEC company facts hold no annual statements for this company (a foreign company filing Form 20-F, "
    "or a fund?). This version reads 10-K and 10-Q reports only, so nothing was sent for analysis."
)


def require_statements(pack: dict) -> None:
    """
    Stop before any paid call when the pack has no annual revenue or net income:
    the analysts would only say there is nothing to analyze.

    Raises:
        DataUnavailableError: with NO_STATEMENTS
    """
    rows = pack.get("financials_annual") or []
    if not any(row.get("revenue") is not None or row.get("net_income") is not None for row in rows):
        raise DataUnavailableError(NO_STATEMENTS)


def pack_hash(pack: dict) -> str:
    return sha256_of(canonical_json(pack))


def summary_lines(pack: dict) -> list[str]:
    quality = pack["data_quality"]
    years = [row["fiscal_year"] for row in pack["financials_annual"]]
    valuation = pack["derived"]["valuation"]
    lines = [
        f"{pack['ticker']} {pack['company_name']}, as_of {pack['as_of']}, FYE {pack['fiscal_year_end']}",
        f"Annual FY{years[0]}-FY{years[-1]} ({len(years)} years)" if years else "Annual: none",
        f"Quarters {len(pack['financials_quarterly'])}; TTM to {(pack['ttm'] or {}).get('period_end')}",
        f"Price {pack['price']['value'] if pack['price'] else None}; market cap {valuation['market_cap']}; "
        f"EV {valuation['enterprise_value']}; P/E {valuation['pe']}; EV/EBIT {valuation['ev_ebit']}",
        f"Missing {len(quality['missing'])} fields, restated {len(quality['restated'])}, "
        f"conflicts {len(quality['source_conflicts'])}, partial {len(quality['partial'])}, "
        f"notes {len(quality['period_notes'])}",
        f"Filing events {len(pack['filing_events'] or [])}",
        f"Size {len(canonical_json(pack)):,} characters, hash {pack_hash(pack)[:16]}",
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description="Build the DATA PACK for one ticker (no LLM calls).")
    parser.add_argument("ticker")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--horizon", choices=HORIZONS, default=DEFAULT_USER_CONTEXT["horizon"])
    parser.add_argument("--risk", choices=RISK_TOLERANCES, default=DEFAULT_USER_CONTEXT["risk_tolerance"])
    args = parser.parse_args(argv)
    load_dotenv(override=True)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cache = DailyCache(args.as_of)
    raw = fetch_company(args.ticker, args.as_of, SecClient(os.getenv("SEC_USER_AGENT")), cache)
    pack, provenance = build_pack(raw, {"horizon": args.horizon, "risk_tolerance": args.risk})
    DailyCache.store(cache.path(raw.ticker, "pack"), pack)
    DailyCache.store(cache.path(raw.ticker, "provenance"), provenance)
    print("\n".join(summary_lines(pack)))
    try:
        require_statements(pack)
    except DataUnavailableError as e:
        print(f"An analysis would stop here: {e}")
    if raw.fetch_status.get("yfinance") != OK:
        print(f"Price source failed: {raw.fetch_errors.get('yfinance')}")
    print(f"Saved {cache.path(raw.ticker, 'pack')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["build_pack", "pack_hash", "require_statements", "summary_lines", "json"]
