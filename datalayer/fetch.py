"""
Fetch everything the DATA PACK needs for one ticker, through the daily cache.

Company facts are required: without the financial statements there is nothing
to analyze, so a failure there stops the run. The filing history and the price
are recorded as failed and the pack is built without them; data_quality then
says so, instead of an empty value passing for "none".

Run it directly to fetch one ticker and print what came back:

    python -m datalayer.fetch KO
"""

import argparse
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from datalayer.cache import DailyCache
from datalayer.prices import fetch_price_snapshot
from datalayer.sec import SecClient, find_cik, format_cik, normalize_ticker

logger = logging.getLogger(__name__)

OK, FAILED, NOT_FETCHED = "ok", "failed", "not_fetched"

PriceProvider = Callable[[str, date], dict]


class DataUnavailableError(RuntimeError):
    """The financial statements could not be fetched; no analysis is possible."""


@dataclass
class RawCompanyData:
    ticker: str
    cik: int
    company_name: str
    as_of: date
    company_facts: dict
    submissions: dict | None
    price: dict | None
    fetch_status: dict[str, str] = field(default_factory=dict)
    fetch_errors: dict[str, str] = field(default_factory=dict)
    from_cache: dict[str, bool] = field(default_factory=dict)


def fetch_company(
    ticker: str,
    as_of: date,
    sec: SecClient,
    cache: DailyCache,
    price_provider: PriceProvider = fetch_price_snapshot,
) -> RawCompanyData:
    """
    Raises:
        UnknownTickerError: the ticker is not a US SEC filer
        DataUnavailableError: company facts could not be fetched
    """
    symbol = normalize_ticker(ticker)
    ticker_map, _ = cache.load_or_fetch("sec", "company_tickers", fetch=sec.ticker_map)
    cik, title = find_cik(ticker_map, symbol)
    padded = format_cik(cik)
    status: dict[str, str] = {}
    errors: dict[str, str] = {}
    hits: dict[str, bool] = {}

    try:
        facts, hits["edgar_companyfacts"] = cache.load_or_fetch(
            symbol, "companyfacts", fetch=lambda: sec.company_facts(padded)
        )
        status["edgar_companyfacts"] = OK
    except Exception as e:
        raise DataUnavailableError(f"{symbol}: company facts could not be fetched: {e}") from e

    try:
        submissions, hits["edgar_submissions"] = cache.load_or_fetch(
            symbol, "submissions", fetch=lambda: sec.submissions(padded)
        )
        status["edgar_submissions"] = OK
    except Exception as e:
        logger.warning(f"{symbol}: filing history not fetched: {e}")
        submissions, status["edgar_submissions"], errors["edgar_submissions"] = None, FAILED, str(e)

    try:
        price, hits["yfinance"] = cache.load_or_fetch(
            symbol, "price", fetch=lambda: price_provider(symbol, as_of)
        )
        status["yfinance"] = OK
    except Exception as e:  # yfinance raises anything from network errors to KeyError
        logger.warning(f"{symbol}: price not fetched: {type(e).__name__}: {e}")
        price, status["yfinance"], errors["yfinance"] = None, FAILED, f"{type(e).__name__}: {e}"

    return RawCompanyData(
        ticker=symbol,
        cik=cik,
        company_name=str(facts.get("entityName") or title),
        as_of=as_of,
        company_facts=facts,
        submissions=submissions,
        price=price,
        fetch_status=status,
        fetch_errors=errors,
        from_cache=hits,
    )


def summary_lines(raw: RawCompanyData) -> list[str]:
    taxonomies = raw.company_facts.get("facts", {})
    counts = ", ".join(f"{name} {len(concepts)}" for name, concepts in sorted(taxonomies.items()))
    lines = [
        f"{raw.ticker}: {raw.company_name} (CIK {format_cik(raw.cik)}), as_of {raw.as_of}",
        f"Concepts: {counts or 'none'}",
    ]
    if raw.submissions:
        lines.append(
            f"Fiscal year end {raw.submissions.get('fiscalYearEnd')}, SIC {raw.submissions.get('sic')} "
            f"{raw.submissions.get('sicDescription')}"
        )
    if raw.price:
        lines.append(f"Close {raw.price['close']:.2f} {raw.price['currency']} on {raw.price['date']}")
    for source, state in raw.fetch_status.items():
        cached = " (cache)" if raw.from_cache.get(source) else ""
        error = f": {raw.fetch_errors[source]}" if source in raw.fetch_errors else ""
        lines.append(f"  {source}: {state}{cached}{error}")
    return lines


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description="Fetch SEC and price data for one ticker (no LLM calls).")
    parser.add_argument("ticker")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)
    load_dotenv(override=True)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sec = SecClient(os.getenv("SEC_USER_AGENT"))
    raw = fetch_company(args.ticker, args.as_of, sec, DailyCache(args.as_of))
    print("\n".join(summary_lines(raw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
