"""
Disk cache per day: every evaluator of a run, and every rerun on the same day,
sees the same fetched data.

Layout: <root>/<YYYY-MM-DD>/<part>/.../<name>.json. The cache is git-ignored;
golden fixtures for tests live in tests/fixtures/ instead.
"""

import json
import logging
import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ROOT = Path("data_cache")


class DailyCache:
    def __init__(self, day: date, root: Path = DEFAULT_ROOT):
        self.day = day
        self.root = Path(root)

    def path(self, *parts: str) -> Path:
        if not parts:
            raise ValueError("A cache entry needs a name")
        *dirs, name = parts
        return self.root.joinpath(self.day.isoformat(), *dirs, f"{name}.json")

    def load_or_fetch(self, *parts: str, fetch: Callable[[], Any]) -> tuple[Any, bool]:
        """
        The cached value and True, or the freshly fetched (and now cached) value
        and False. A cache file that cannot be read is fetched again.
        """
        path = self.path(*parts)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8")), True
            except (OSError, ValueError) as e:
                logger.warning(f"Unreadable cache file {path} ({e}); fetching again")
        value = fetch()
        self.store(path, value)
        return value, False

    @staticmethod
    def store(path: Path, value: Any) -> None:
        """Write through a temporary file, so a crash never leaves half a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        os.replace(tmp, path)
