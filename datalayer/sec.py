"""
SEC EDGAR client: ticker to CIK, company facts (XBRL) and filing history.

SEC fair access rules (sec.gov, "Accessing EDGAR Data", checked 2026-10-15): at
most 10 requests per second, and a User-Agent that declares who is asking, with
a contact email. Without it the SEC answers 403. The endpoints need no API key
("EDGAR Application Programming Interfaces", checked 2026-10-15).
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from datalayer.http import HttpError, HttpGet, urllib_get

logger = logging.getLogger(__name__)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# The SEC allows 10 requests per second; 8 leaves a margin for clock jitter.
MIN_INTERVAL_S = 1 / 8
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_DELAY_S = 2.0
PLACEHOLDER_EMAIL_DOMAIN = "example.com"


class SecAccessError(RuntimeError):
    """The SEC refused the request or the User-Agent is not usable."""


class UnknownTickerError(LookupError):
    """The ticker is not in the SEC ticker map (not a US SEC filer, or a typo)."""


def check_user_agent(user_agent: str | None) -> str:
    """The User-Agent must name a contact email; the .env.example placeholder does not count."""
    value = (user_agent or "").strip()
    if "@" not in value:
        raise SecAccessError(
            "SEC_USER_AGENT must contain a contact email, e.g. 'Jane Doe jane@example.org' "
            "(set it in .env; the SEC refuses requests without one)."
        )
    if PLACEHOLDER_EMAIL_DOMAIN in value.lower():
        raise SecAccessError("SEC_USER_AGENT still holds the placeholder from .env.example.")
    return value


def format_cik(cik: int | str) -> str:
    """CIK as the 10-digit string with leading zeros the data.sec.gov URLs use."""
    digits = str(cik).strip()
    if not digits.isdigit() or len(digits) > 10:
        raise ValueError(f"Not a CIK: {cik!r}")
    return digits.zfill(10)


def normalize_ticker(ticker: str) -> str:
    """Upper case; share classes use a dash in the SEC map (BRK.B -> BRK-B)."""
    value = ticker.strip().upper().replace(".", "-")
    if not value:
        raise ValueError("Empty ticker")
    return value


class SecClient:
    """Throttled JSON GETs against SEC endpoints, with one retry on transient errors."""

    def __init__(
        self,
        user_agent: str | None,
        http_get: HttpGet = urllib_get,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._headers = {"User-Agent": check_user_agent(user_agent)}
        self._http_get = http_get
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def _throttle(self) -> None:
        with self._lock:
            now = self._clock()
            wait = self._next_allowed - now
            if wait > 0:
                self._sleep(wait)
                now += wait
            self._next_allowed = now + MIN_INTERVAL_S

    def get_json(self, url: str) -> Any:
        for attempt in (1, 2):
            self._throttle()
            try:
                body = self._http_get(url, self._headers)
                return json.loads(body)
            except HttpError as e:
                if e.status == 403:
                    raise SecAccessError(
                        f"SEC refused {url} (403). Check SEC_USER_AGENT and the request rate."
                    ) from e
                if attempt == 1 and (e.status in RETRY_STATUSES or e.status is None):
                    logger.warning(f"{e}; retrying in {RETRY_DELAY_S:.0f}s")
                    self._sleep(RETRY_DELAY_S)
                    continue
                raise
        raise AssertionError("unreachable")

    def ticker_map(self) -> dict:
        return self.get_json(TICKERS_URL)

    def company_facts(self, cik: int | str) -> dict:
        return self.get_json(COMPANY_FACTS_URL.format(cik=format_cik(cik)))

    def submissions(self, cik: int | str) -> dict:
        return self.get_json(SUBMISSIONS_URL.format(cik=format_cik(cik)))


def find_cik(ticker_map: dict, ticker: str) -> tuple[int, str]:
    """
    (CIK, company title) for a ticker from company_tickers.json, whose values look
    like {"cik_str": 21344, "ticker": "KO", "title": "COCA COLA CO"}.
    """
    wanted = normalize_ticker(ticker)
    for entry in ticker_map.values():
        if str(entry.get("ticker", "")).upper() == wanted:
            return int(entry["cik_str"]), str(entry.get("title", ""))
    raise UnknownTickerError(
        f"{wanted} is not in the SEC ticker map: Stock Autopsy covers US SEC filers only."
    )
