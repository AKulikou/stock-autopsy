"""
Analysis runs started from the web page: one at a time, each in its own thread.

A run is paid for, so a double click or a second browser tab must not start a
second one in parallel: RunManager.start() refuses while a run is active. Runs
live only in memory (the page has no history); their files are written to
results/ like a CLI run.
"""

import logging
import os
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from analysis.runner import AutopsyRun, run_autopsy
from core.progress import ProgressEvent
from core.token_summary import log_token_summary
from datalayer.cache import DailyCache
from datalayer.fetch import DataUnavailableError, RawCompanyData, fetch_company
from datalayer.sec import SecAccessError, SecClient, UnknownTickerError
from reporting.save import save_run

logger = logging.getLogger(__name__)

KEEP_RUNS = 10
USER_CONTEXT = {"horizon": "5y", "risk_tolerance": "medium"}


def fetch_live(ticker: str, as_of: date) -> RawCompanyData:
    """SEC filings and the price for one ticker, through the daily cache."""
    return fetch_company(ticker, as_of, SecClient(os.getenv("SEC_USER_AGENT")), DailyCache(as_of))


class BusyError(RuntimeError):
    def __init__(self, active_run_id: str | None):
        super().__init__("Another analysis is already running.")
        self.active_run_id = active_run_id


@dataclass
class Run:
    id: str
    ticker: str
    started_at: datetime
    company: str | None = None
    name: str | None = None  # the name the page showed when Analyze was pressed (display only)
    related_to: str | None = None  # what the person looked up, if they picked a related company
    autopsy: AutopsyRun | None = None
    out_dir: Path | None = None
    error: str | None = None
    finished_at: datetime | None = None
    _events: list[dict] = field(default_factory=list)
    _finished: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_event(self, event: ProgressEvent) -> None:
        with self._lock:
            self._events.append(event.to_dict())

    def finish(self, event: ProgressEvent) -> None:
        with self._lock:
            self._events.append(event.to_dict())
            self.finished_at = datetime.now()
            self._finished = True

    def events_since(self, count: int) -> tuple[list[dict], bool]:
        with self._lock:
            return self._events[count:], self._finished

    @property
    def finished(self) -> bool:
        with self._lock:
            return self._finished

    def cost_usd(self) -> float:
        if self.autopsy is not None and self.autopsy.total_cost is not None:
            return self.autopsy.total_cost
        with self._lock:
            return sum(e["cost_usd"] or 0.0 for e in self._events if e["stage"] != "run")


class RunManager:
    def __init__(self, results_dir: Path, fetch: Callable[[str, date], RawCompanyData] = fetch_live):
        self.results_dir = results_dir
        self.fetch = fetch
        self._busy = threading.Lock()
        self._runs: OrderedDict[str, Run] = OrderedDict()
        self._active: str | None = None

    def start(self, ticker: str, name: str | None = None, related_to: str | None = None) -> Run:
        """Start an analysis in a background thread. Raises BusyError if one is active."""
        if not self._busy.acquire(blocking=False):
            raise BusyError(self._active)
        try:
            run = Run(id=uuid.uuid4().hex[:12], ticker=ticker, started_at=datetime.now(), name=name,
                      related_to=related_to)
            self._runs[run.id] = run
            while len(self._runs) > KEEP_RUNS:
                self._runs.popitem(last=False)
            self._active = run.id
            threading.Thread(target=self._execute, args=(run,), name=f"run-{run.id}", daemon=True).start()
        except BaseException:
            self._active = None
            self._busy.release()
            raise
        return run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def recent(self) -> list[Run]:
        """Finished runs still in memory, newest first."""
        return [run for run in reversed(self._runs.values()) if run.finished]

    @property
    def active_run_id(self) -> str | None:
        return self._active

    def _execute(self, run: Run) -> None:
        final = None
        fetched = False
        try:
            logger.info(f"Web run {run.id} started: {run.ticker}")
            run.add_event(ProgressEvent("fetch", "started", label="SEC filings and price"))
            as_of = date.today()
            raw = self.fetch(run.ticker, as_of)
            fetched = True
            run.company = raw.company_name
            received = [name for name, status in raw.fetch_status.items() if status == "ok"]
            run.add_event(ProgressEvent("fetch", "done", label="SEC filings and price",
                                        text=f"{len(received)} sources received"))
            run.autopsy = run_autopsy(raw, USER_CONTEXT, on_event=run.add_event)
            run.autopsy.related_to = run.related_to
            run.out_dir = save_run(run.autopsy, raw.ticker, as_of, self.results_dir, run.started_at)
            log_token_summary(run.autopsy.calls)
            final = ProgressEvent("run", "done", text="analyzed", cost_usd=run.cost_usd())
        except (UnknownTickerError, DataUnavailableError, SecAccessError) as e:
            run.error = str(e)
            if not fetched:  # after the fetch, run_autopsy has already said which step stopped
                run.add_event(ProgressEvent("fetch", "failed", label="SEC filings and price", text=str(e)))
            final = ProgressEvent("run", "failed", text=run.error, cost_usd=run.cost_usd())
        except Exception as e:
            logger.exception(f"Web run {run.id} failed")
            run.error = f"{type(e).__name__}: {e}"
            final = ProgressEvent("run", "failed", text=run.error, cost_usd=run.cost_usd())
        finally:
            self._active = None
            self._busy.release()
            run.finish(final or ProgressEvent("run", "failed", text="interrupted"))
            logger.info(f"Web run {run.id} finished, est. cost ${run.cost_usd():.4f}")
