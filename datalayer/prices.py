"""
Price, Yahoo's own share count and market cap, and the split history, from yfinance.

yfinance is unofficial: it scrapes Yahoo Finance and can break without notice, so
the version is pinned and a failure here is recorded, never fatal. Yahoo's terms
allow personal, non-commercial use; Stock Autopsy is a personal research and
learning tool.

The price is the close of the last trading day before as_of, so a run on one day
always sees the same price: an intraday quote would change from minute to minute.
"""

import math
from datetime import date, timedelta

LOOKBACK_DAYS = 10  # long enough to span a weekend plus holidays


def finite_or_none(value) -> float | None:
    """A float, or None for a missing, NaN or infinite value (absent is not zero)."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def yahoo_symbol(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def fetch_price_snapshot(ticker: str, as_of: date) -> dict:
    """
    The last close before as_of with its date, Yahoo's reported market cap and
    share count (for cross-checks only), and all stock splits.

    Raises:
        LookupError: no trading day with a close in the lookback window
    """
    import yfinance as yf  # heavy import (pandas); only needed for a live fetch

    stock = yf.Ticker(yahoo_symbol(ticker))
    history = stock.history(
        start=(as_of - timedelta(days=LOOKBACK_DAYS)).isoformat(),
        end=as_of.isoformat(),  # exclusive: the as_of day itself is not included
        auto_adjust=False,
    )
    closes = [
        (index.date(), finite_or_none(row["Close"]))
        for index, row in history.iterrows()
        if finite_or_none(row["Close"]) is not None
    ]
    if not closes:
        raise LookupError(f"No close for {ticker} in the {LOOKBACK_DAYS} days before {as_of}")
    close_date, close = closes[-1]

    info = stock.fast_info
    splits = [
        {"date": index.date().isoformat(), "ratio": ratio}
        for index, value in stock.splits.items()
        if (ratio := finite_or_none(value)) is not None and ratio > 0 and index.date() <= as_of
    ]
    return {
        "close": close,
        "date": close_date.isoformat(),
        "currency": info["currency"],
        "market_cap_reported": finite_or_none(info["marketCap"]),
        "shares_reported": finite_or_none(info["shares"]),
        "splits": splits,
        "source": f"Yahoo Finance via yfinance {yf.__version__}",
    }
