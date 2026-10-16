"""
Minimal local web UI for Stock Autopsy (design: docs/web_ui.md).

Run with `python -m web` and open http://127.0.0.1:8001. FastAPI serves one page
(web/static/) and a small JSON API; progress reaches the page as server-sent
events built from core.progress.ProgressEvent.
"""
