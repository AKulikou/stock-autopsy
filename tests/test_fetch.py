import json
from datetime import date

import pytest

from datalayer.cache import DailyCache
from datalayer.fetch import FAILED, OK, DataUnavailableError, fetch_company, summary_lines
from datalayer.http import HttpError
from datalayer.prices import finite_or_none
from datalayer.sec import SecClient, UnknownTickerError

AS_OF = date(2026, 10, 15)
TICKERS = {"0": {"cik_str": 21344, "ticker": "KO", "title": "COCA COLA CO"}}
FACTS = {"cik": 21344, "entityName": "COCA COLA CO", "facts": {"us-gaap": {"Revenues": {}}}}
SUBMISSIONS = {"fiscalYearEnd": "1231", "sic": "2080", "sicDescription": "Beverages"}
PRICE = {"close": 91.5, "date": "2026-10-14", "currency": "USD", "splits": []}


class FakeSec:
    """Serves the SEC endpoints from dicts; a value that is an exception is raised."""

    def __init__(self, routes):
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, url, headers):
        self.calls.append(url)
        for fragment, value in self.routes.items():
            if fragment in url:
                if isinstance(value, Exception):
                    raise value
                return json.dumps(value).encode()
        raise HttpError(url, 404)


def sec_with(**overrides):
    routes = {"company_tickers": TICKERS, "companyfacts": FACTS, "submissions": SUBMISSIONS}
    routes.update(overrides)
    fake = FakeSec(routes)
    client = SecClient(
        "Test Runner tester@example.org", http_get=fake, clock=lambda: 0.0, sleep=lambda s: None
    )
    return client, fake


def test_fetch_collects_all_sources(tmp_path):
    sec, _ = sec_with()
    raw = fetch_company("ko", AS_OF, sec, DailyCache(AS_OF, tmp_path), price_provider=lambda t, d: PRICE)
    assert (raw.ticker, raw.cik, raw.company_name) == ("KO", 21344, "COCA COLA CO")
    assert raw.fetch_status == {"edgar_companyfacts": OK, "edgar_submissions": OK, "yfinance": OK}
    assert raw.price == PRICE and raw.submissions == SUBMISSIONS


def test_second_fetch_on_the_same_day_comes_from_the_cache(tmp_path):
    sec, fake = sec_with()
    cache = DailyCache(AS_OF, tmp_path)
    fetch_company("KO", AS_OF, sec, cache, price_provider=lambda t, d: PRICE)
    calls_after_first = len(fake.calls)

    def no_price(t, d):
        raise AssertionError("price must come from the cache")

    raw = fetch_company("KO", AS_OF, sec, cache, price_provider=no_price)
    assert len(fake.calls) == calls_after_first
    assert all(raw.from_cache.values())


def test_another_day_fetches_again(tmp_path):
    sec, fake = sec_with()
    fetch_company("KO", AS_OF, sec, DailyCache(AS_OF, tmp_path), price_provider=lambda t, d: PRICE)
    calls = len(fake.calls)
    next_day = date(2026, 10, 16)
    fetch_company("KO", next_day, sec, DailyCache(next_day, tmp_path), price_provider=lambda t, d: PRICE)
    assert len(fake.calls) > calls


def test_failed_price_is_recorded_not_raised(tmp_path):
    sec, _ = sec_with()

    def broken(ticker, as_of):
        raise KeyError("currentTradingPeriod")

    raw = fetch_company("KO", AS_OF, sec, DailyCache(AS_OF, tmp_path), price_provider=broken)
    assert raw.price is None
    assert raw.fetch_status["yfinance"] == FAILED
    assert "KeyError" in raw.fetch_errors["yfinance"]
    assert not DailyCache(AS_OF, tmp_path).path("KO", "price").exists()  # a failure is not cached


def test_failed_submissions_are_recorded_not_raised(tmp_path):
    sec, _ = sec_with(submissions=HttpError("u", 404))
    raw = fetch_company("KO", AS_OF, sec, DailyCache(AS_OF, tmp_path), price_provider=lambda t, d: PRICE)
    assert raw.submissions is None
    assert raw.fetch_status["edgar_submissions"] == FAILED


def test_missing_company_facts_stop_the_run(tmp_path):
    sec, _ = sec_with(companyfacts=HttpError("u", 404))
    with pytest.raises(DataUnavailableError):
        fetch_company("KO", AS_OF, sec, DailyCache(AS_OF, tmp_path), price_provider=lambda t, d: PRICE)


def test_unknown_ticker_stops_before_any_company_request(tmp_path):
    sec, fake = sec_with()
    with pytest.raises(UnknownTickerError):
        fetch_company("NESN", AS_OF, sec, DailyCache(AS_OF, tmp_path), price_provider=lambda t, d: PRICE)
    assert all("company_tickers" in url for url in fake.calls)


def test_unreadable_cache_file_is_fetched_again(tmp_path):
    cache = DailyCache(AS_OF, tmp_path)
    path = cache.path("KO", "price")
    path.parent.mkdir(parents=True)
    path.write_text("{truncated", encoding="utf-8")
    value, hit = cache.load_or_fetch("KO", "price", fetch=lambda: PRICE)
    assert (value, hit) == (PRICE, False)
    assert json.loads(path.read_text(encoding="utf-8")) == PRICE


def test_summary_names_failed_sources(tmp_path):
    sec, _ = sec_with(submissions=HttpError("u", 404))
    raw = fetch_company("KO", AS_OF, sec, DailyCache(AS_OF, tmp_path), price_provider=lambda t, d: PRICE)
    text = "\n".join(summary_lines(raw))
    assert "edgar_submissions: failed" in text and "Close 91.50 USD on 2026-10-14" in text


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), "n/a"])
def test_missing_or_non_finite_numbers_become_none(value):
    assert finite_or_none(value) is None
