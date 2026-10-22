"""
The FastAPI application: one page and a small JSON API (design: docs/web_ui.md).

    GET  /                           the page (web/static/index.html)
    GET  /api/options                example companies
    POST /api/resolve {query}        ticker, or candidates for a name or brand, each
                                     checked for 10-K / 10-Q reports in its filing history
    POST /api/runs {ticker}          start an analysis (one at a time)
    GET  /api/runs/active            the run in progress, if any (to reattach after a reload)
    GET  /api/runs/recent            finished runs still in memory, to reopen their results
    GET  /api/runs/{id}/events?since=N  progress as server-sent events from event N (default the
                                     first), with a comment line as a heartbeat while it is quiet
    GET  /api/runs/{id}/result       the finished result, in words
    GET  /api/runs/{id}/files/{kind} downloads: report (report.json is not offered)
    POST /api/runs/{id}/translation {language}  a translated copy of the finished report (paid, cheap)
    GET  /api/runs/{id}/translations/{code}     download it (report.ru.md)

Meant for this machine only (python -m web binds to 127.0.0.1); the host and
origin checks also stop another website open in the same browser from starting
paid runs through it.
"""

import asyncio
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from analysis.runner import LIVE_ANALYSTS
from core.token_summary import call_cost, format_cost
from datalayer.cache import DailyCache
from datalayer.filings import unsupported_filer
from datalayer.sec import SecClient, format_cik, normalize_ticker
from datalayer.sector import FINANCIAL_NOTE, financial_kind
from reporting.wording import company_display
from translate.languages import DEFAULT_LANGUAGE, language_name, languages_for_page
from translate.translator import translate_report, translated_path
from web.resolve import FilerCheck, resolve
from web.runs import BusyError, RunManager, fetch_live
from web.view import download_name, download_paths, recent_view, run_view, translation_view

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
LOCAL_HOSTS = ("127.0.0.1", "localhost")
EVENT_POLL_S = 0.3
# An analyst call is silent for about a minute; a comment line every few seconds keeps
# the stream from looking dead to the browser or anything in between (2026-10-17:
# a stream dropped in a 40-second silence and the page reported a failure).
HEARTBEAT_S = 15.0
MEDIA_TYPES = {"report": "text/markdown; charset=utf-8"}
# The page and its files are checked with the server on every load (an unchanged file is a
# 304 by its ETag), so after an update the browser cannot keep an old app.css or app.js,
# nor an old module imported by app.js (2026-10-22: an old toolbar until a hard refresh).
FRESH = {"Cache-Control": "no-cache"}
EXAMPLES = (
    ("Coca-Cola", "KO"),
    ("Comcast", "CMCSA"),
    ("Kraft Heinz", "KHC"),
    ("Snowflake", "SNOW"),
    ("Plug Power", "PLUG"),
    ("KFC (a brand)", "KFC"),
)


class FreshStaticFiles(StaticFiles):
    """Static files the browser revalidates on every load instead of reusing a stale copy."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers.update(FRESH)
        return response


def load_ticker_map() -> dict:
    sec = SecClient(os.getenv("SEC_USER_AGENT"))
    ticker_map, _ = DailyCache(date.today()).load_or_fetch("sec", "company_tickers", fetch=sec.ticker_map)
    return ticker_map


def _submissions(ticker: str, cik: int) -> dict | None:
    """The company's SEC filing history (free; cached under the same name an analysis uses)."""
    symbol = normalize_ticker(ticker)
    try:
        sec = SecClient(os.getenv("SEC_USER_AGENT"))
        submissions, _ = DailyCache(date.today()).load_or_fetch(
            symbol, "submissions", fetch=lambda: sec.submissions(format_cik(cik))
        )
    except Exception as e:
        logger.warning(f"Filing history of {symbol} not checked: {type(e).__name__}: {e}")
        return None
    return submissions


def check_filer_live(ticker: str, cik: int) -> str | None:
    """
    Why the company cannot be analyzed, from its SEC filing history. None when it can, or
    when the history is not reachable: then the data pack check still stops an empty run.
    """
    submissions = _submissions(ticker, cik)
    return unsupported_filer(submissions) if submissions else None


def check_sector_live(ticker: str, cik: int) -> str | None:
    """The note for a bank or other financial company (SIC code), or None."""
    submissions = _submissions(ticker, cik)
    return FINANCIAL_NOTE if submissions and financial_kind(submissions.get("sic")) else None


class ResolveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=100)


class RunRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    name: str | None = Field(None, max_length=200, description="The company name on the page; display only.")
    related_to: str | None = Field(
        None, max_length=100,
        description="What the person looked up, when they picked this company as a related one; "
        "display only.",
    )


class TranslationRequest(BaseModel):
    language: str = Field(min_length=1, max_length=40, description="English name or code of the language.")


def create_app(
    results_dir: Path = ROOT / "results",
    fetch: Callable = fetch_live,
    ticker_map: Callable[[], dict] = load_ticker_map,
    filer_check: FilerCheck = check_filer_live,
    sector_check: FilerCheck = check_sector_live,
    translate: Callable[[Path, str], dict] = translate_report,
) -> FastAPI:
    app = FastAPI(title="Stock Autopsy", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(LOCAL_HOSTS))
    runs = RunManager(results_dir, fetch)
    # One translation at a time: a double click must not pay twice.
    translating = threading.Lock()

    @app.middleware("http")
    async def same_origin_posts(request: Request, call_next):
        """A browser sends Origin with a cross-site POST: refuse any that is not this page."""
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and urlparse(origin).hostname not in LOCAL_HOSTS:
            return JSONResponse({"detail": "Requests from other sites are not accepted."}, status_code=403)
        return await call_next(request)

    def get_run(run_id: str):
        run = runs.get(run_id)
        if run is None:
            raise HTTPException(404, "No such analysis (the server keeps only recent ones in memory).")
        return run

    @app.get("/", include_in_schema=False)
    def page():
        return FileResponse(STATIC_DIR / "index.html", headers=FRESH)

    @app.get("/api/options")
    def options():
        analysts = [{"key": p.key, "label": p.name, "waits_for": waits} for p, waits in LIVE_ANALYSTS]
        return {"examples": [{"title": title, "query": query} for title, query in EXAMPLES],
                "analysts": analysts,
                "languages": languages_for_page(), "default_language": DEFAULT_LANGUAGE}

    @app.post("/api/resolve")
    def resolve_company(body: ResolveRequest):
        try:
            known = ticker_map()
        except Exception as e:
            logger.warning(f"Ticker map unavailable: {type(e).__name__}: {e}")
            raise HTTPException(503, "The SEC ticker list is not reachable right now.") from None
        return resolve(body.query, known, filer_check, sector_check)

    @app.post("/api/runs", status_code=202)
    def start_run(body: RunRequest):
        try:
            run = runs.start(normalize_ticker(body.ticker), body.name, body.related_to)
        except BusyError as e:
            return JSONResponse(
                {"detail": "Another analysis is running. It takes about 3 minutes; this page follows it.",
                 "active_run_id": e.active_run_id},
                status_code=409,
            )
        return {"run_id": run.id}

    @app.get("/api/runs/active")
    def active_run():
        run = runs.get(runs.active_run_id) if runs.active_run_id else None
        if run is None:
            return {"run_id": None, "elapsed_s": None, "ticker": None, "name": None}
        return {"run_id": run.id, "elapsed_s": round((datetime.now() - run.started_at).total_seconds()),
                "ticker": run.ticker, "related_to": run.related_to,
                "name": run.name or (company_display(run.company) if run.company else None)}

    @app.get("/api/runs/recent")
    def recent_runs():
        return {"runs": [recent_view(run) for run in runs.recent()]}

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str, since: int = Query(0, ge=0)):
        """From event `since` on, so a page that lost the stream resumes without a replay."""
        run = get_run(run_id)

        async def stream():
            sent = since
            quiet_since = time.monotonic()
            while True:
                events, finished = run.events_since(sent)
                for event in events:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                sent += len(events)
                if finished:
                    return
                if events:
                    quiet_since = time.monotonic()
                elif time.monotonic() - quiet_since >= HEARTBEAT_S:
                    yield ": still working\n\n"  # a comment line: browsers ignore it
                    quiet_since = time.monotonic()
                await asyncio.sleep(EVENT_POLL_S)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/runs/{run_id}/result")
    def run_result(run_id: str):
        run = get_run(run_id)
        if not run.finished:
            raise HTTPException(409, "The analysis is still running.")
        return run_view(run)

    @app.get("/api/runs/{run_id}/files/{kind}")
    def run_file(run_id: str, kind: str):
        run = get_run(run_id)
        path = download_paths(run).get(kind) if run.finished else None
        if path is None:
            raise HTTPException(404, "This file is not available for this analysis.")
        return FileResponse(path, media_type=MEDIA_TYPES[kind], filename=download_name(run, path))

    @app.post("/api/runs/{run_id}/translation")
    def translate_result(run_id: str, body: TranslationRequest):
        """Blocks until the translation is written (under a minute); an existing one is reused for free."""
        run = get_run(run_id)
        language = language_name(body.language)
        if language is None:
            raise HTTPException(422, f"Translation into {body.language} is not offered.")
        if not run.finished or run.out_dir is None or not download_paths(run).get("report"):
            raise HTTPException(409, "Only a finished analysis with a saved report can be translated.")
        if not translating.acquire(blocking=False):
            raise HTTPException(409, "A translation is already running; it takes up to a minute.")
        try:
            outcome = translate(run.out_dir, language)
        finally:
            translating.release()
        cost = call_cost(outcome) if outcome.get("input_tokens") is not None else None
        logger.info(f"Web run {run.id}: translation into {language} {outcome['status']}, {format_cost(cost)}")
        if outcome["status"] != "success":
            raise HTTPException(
                502, f"The translation failed ({outcome['error']}). The English report is complete."
            )
        return translation_view(outcome, language, cost)

    @app.get("/api/runs/{run_id}/translations/{code}")
    def translation_file(run_id: str, code: str):
        run = get_run(run_id)
        language = language_name(code)
        path = translated_path(run.out_dir, language) if language and run.out_dir else None
        if path is None or not path.exists():
            raise HTTPException(404, "This translation does not exist yet.")
        return FileResponse(path, media_type="text/markdown; charset=utf-8",
                            filename=download_name(run, path))

    app.mount("/static", FreshStaticFiles(directory=STATIC_DIR), name="static")
    return app
