"""
Run independent calls in parallel threads, optionally after one warm-up call.

Prompt caching needs the warm-up: a cache entry becomes available only after the
first response that wrote it begins, so calls sent at the same moment all miss
the cache and each pays for writing the shared prefix. Running the first task
alone, then the rest in parallel, turns n-1 cache writes into cache reads at the
cost of one call's latency. When the first task is needed first anyway (Stock
Autopsy's valuation assumptions, before the Python DCF), the warm-up is free.

Results come back in the order of the tasks, whatever order they finish in.
"""

import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


def _run_one(label: str, task: Callable[[], dict]) -> dict:
    """A task should never raise; if one does, its error becomes its result."""
    try:
        return task()
    except Exception as e:
        logger.debug(f"{label}: task raised", exc_info=True)
        return {"label": label, "status": "error", "error": f"{type(e).__name__}: {e}"}


def run_parallel(
    tasks: Sequence[tuple[str, Callable[[], dict]]],
    warm_up_first: bool = True,
    on_done: Callable[[int, dict], None] | None = None,
) -> list[dict]:
    """
    Run (label, task) pairs and return their results in the same order.

    Args:
        warm_up_first: run the first task alone before starting the others, so
            they can read the prompt cache it wrote.
        on_done: called with (task index, result) as each task finishes, from the
            calling thread (for live progress).
    """
    if not tasks:
        return []
    results: list[dict | None] = [None] * len(tasks)
    started = time.monotonic()
    first = 0
    if warm_up_first:
        label, task = tasks[0]
        logger.info(f"[1/{len(tasks)}] {label} ... started (warm-up)")
        results[0] = _run_one(label, task)
        if on_done:
            on_done(0, results[0])
        first = 1
    rest = range(first, len(tasks))
    if rest:
        with ThreadPoolExecutor(max_workers=len(rest)) as pool:
            futures = {}
            for index in rest:
                label, task = tasks[index]
                logger.info(f"[{index + 1}/{len(tasks)}] {label} ... started")
                futures[pool.submit(_run_one, label, task)] = index
            for future in as_completed(futures):
                results[futures[future]] = future.result()
                if on_done:
                    on_done(futures[future], results[futures[future]])
    logger.info(f"{len(tasks)} calls finished in {time.monotonic() - started:.0f}s")
    missing = [tasks[i][0] for i, result in enumerate(results) if result is None]
    if missing:
        raise RuntimeError(f"No result for: {', '.join(missing)}")
    return [result for result in results if result is not None]
