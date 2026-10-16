"""
The FastAPI application: one page and a small JSON API (design: docs/web_ui.md).

    GET  /                           the page (web/static/index.html)
    GET  /api/options                example companies
    POST /api/resolve {query}        ticker, or candidates for a name or brand (decision D5)
    POST /api/runs {ticker}          start an analysis (one at a time)
    GET  /api/runs/active            the run in progress, if any (to reattach after a reload)
    GET  /api/runs/{id}/events       progress as server-sent events, from the first event
    GET  /api/runs/{id}/result       the finished result, in words
    GET  /api/runs/{id}/files/{kind} downloads: report (report.json is not offered)

Meant for this machine only (python -m web binds to 127.0.0.1); the host and
origin checks also stop another website open in the same browser from starting
paid runs through it.
"""

import asyncio
import json
import logging
import os
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from datalayer.cache import DailyCache
from datalayer.sec import SecClient, normalize_ticker
from web.resolve import resolve
from web.runs import BusyError, RunManager, fetch_live
from web.view import download_paths, run_view

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
LOCAL_HOSTS = ("127.0.0.1", "localhost")
EVENT_POLL_S = 0.3
MEDIA_TYPES = {"report": "text/markdown; charset=utf-8"}
EXAMPLES = (
    ("Coca-Cola", "KO"),
    ("Comcast", "CMCSA"),
    ("Kraft Heinz", "KHC"),
    ("Snowflake", "SNOW"),
    ("Plug Power", "PLUG"),
    ("KFC (a brand)", "KFC"),
)


def load_ticker_map() -> dict:
    sec = SecClient(os.getenv("SEC_USER_AGENT"))
    ticker_map, _ = DailyCache(date.today()).load_or_fetch("sec", "company_tickers", fetch=sec.ticker_map)
    return ticker_map


class ResolveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=100)


class RunRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)


def create_app(
    results_dir: Path = ROOT / "results",
    fetch: Callable = fetch_live,
    ticker_map: Callable[[], dict] = load_ticker_map,
) -> FastAPI:
    app = FastAPI(title="Stock Autopsy", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(LOCAL_HOSTS))
    runs = RunManager(results_dir, fetch)

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
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/options")
    def options():
        return {"examples": [{"title": title, "query": query} for title, query in EXAMPLES]}

    @app.post("/api/resolve")
    def resolve_company(body: ResolveRequest):
        try:
            known = ticker_map()
        except Exception as e:
            logger.warning(f"Ticker map unavailable: {type(e).__name__}: {e}")
            raise HTTPException(503, "The SEC ticker list is not reachable right now.") from None
        return resolve(body.query, known)

    @app.post("/api/runs", status_code=202)
    def start_run(body: RunRequest):
        try:
            run = runs.start(normalize_ticker(body.ticker))
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
            return {"run_id": None, "elapsed_s": None}
        return {"run_id": run.id, "elapsed_s": round((datetime.now() - run.started_at).total_seconds())}

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str):
        run = get_run(run_id)

        async def stream():
            sent = 0
            while True:
                events, finished = run.events_since(sent)
                for event in events:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                sent += len(events)
                if finished:
                    return
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
        return FileResponse(path, media_type=MEDIA_TYPES[kind], filename=f"{path.parent.name}_{path.name}")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
