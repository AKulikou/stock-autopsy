import gzip
import json

import pytest

from datalayer.http import HttpError, decode_body
from datalayer.sec import (
    MIN_INTERVAL_S,
    SecAccessError,
    SecClient,
    UnknownTickerError,
    check_user_agent,
    find_cik,
    format_cik,
    normalize_ticker,
)

UA = "Test Runner tester@example.org"


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def client_with(responses, clock=None):
    """A SecClient whose GETs return (or raise) the given items in order."""
    clock = clock or FakeClock()
    calls = []

    def http_get(url, headers):
        calls.append((url, dict(headers)))
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return json.dumps(item).encode()

    return SecClient(UA, http_get=http_get, clock=clock, sleep=clock.sleep), calls, clock


@pytest.mark.parametrize("bad", [None, "", "Just A Name", "Your Name your-email@example.com"])
def test_user_agent_needs_a_real_contact_email(bad):
    with pytest.raises(SecAccessError):
        check_user_agent(bad)


def test_user_agent_is_sent_with_every_request():
    client, calls, _ = client_with([{"a": 1}])
    assert client.get_json("https://data.sec.gov/x") == {"a": 1}
    assert calls[0][1]["User-Agent"] == UA


def test_requests_are_spaced_to_stay_under_ten_per_second():
    client, _, clock = client_with([{}, {}, {}])
    for _ in range(3):
        client.get_json("https://data.sec.gov/x")
    assert sum(clock.slept) == pytest.approx(2 * MIN_INTERVAL_S)
    assert MIN_INTERVAL_S >= 1 / 10


def test_transient_error_is_retried_once():
    client, calls, _ = client_with([HttpError("u", 503), {"ok": True}])
    assert client.get_json("https://data.sec.gov/x") == {"ok": True}
    assert len(calls) == 2


def test_second_transient_error_is_raised():
    client, _, _ = client_with([HttpError("u", 503), HttpError("u", 503)])
    with pytest.raises(HttpError):
        client.get_json("https://data.sec.gov/x")


def test_not_found_is_not_retried():
    client, calls, _ = client_with([HttpError("u", 404)])
    with pytest.raises(HttpError):
        client.get_json("https://data.sec.gov/x")
    assert len(calls) == 1


def test_forbidden_points_at_the_user_agent():
    client, _, _ = client_with([HttpError("u", 403)])
    with pytest.raises(SecAccessError, match="SEC_USER_AGENT"):
        client.get_json("https://data.sec.gov/x")


def test_company_facts_url_uses_the_ten_digit_cik():
    client, calls, _ = client_with([{}])
    client.company_facts(21344)
    assert calls[0][0] == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000021344.json"


@pytest.mark.parametrize("bad", ["", "12a", "12345678901"])
def test_format_cik_rejects_non_ciks(bad):
    with pytest.raises(ValueError):
        format_cik(bad)


TICKER_MAP = {
    "0": {"cik_str": 21344, "ticker": "KO", "title": "COCA COLA CO"},
    "1": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
}


@pytest.mark.parametrize("ticker", ["KO", "ko", " Ko "])
def test_ticker_lookup_ignores_case_and_spaces(ticker):
    assert find_cik(TICKER_MAP, ticker) == (21344, "COCA COLA CO")


def test_share_class_with_a_dot_maps_to_the_sec_dash():
    assert normalize_ticker("brk.b") == "BRK-B"
    assert find_cik(TICKER_MAP, "BRK.B")[0] == 1067983


def test_unknown_ticker_says_us_filers_only():
    with pytest.raises(UnknownTickerError, match="US SEC filers"):
        find_cik(TICKER_MAP, "NESN")


def test_gzip_body_is_decoded():
    assert decode_body(gzip.compress(b"{}"), "gzip") == b"{}"
    assert decode_body(b"{}", None) == b"{}"
