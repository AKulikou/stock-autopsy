import threading
import time

from core.fanout import run_parallel


def recorder():
    events: list[str] = []
    lock = threading.Lock()

    def task(name, delay=0.0):
        def run():
            with lock:
                events.append(f"start {name}")
            time.sleep(delay)
            with lock:
                events.append(f"end {name}")
            return {"label": name, "status": "success"}
        return run
    return events, task


def test_warm_up_task_finishes_before_any_other_starts():
    events, task = recorder()
    run_parallel([("first", task("first", 0.05)), ("b", task("b")), ("c", task("c"))])
    assert events[:2] == ["start first", "end first"]


def test_without_warm_up_all_tasks_start_together():
    events, task = recorder()
    run_parallel([("a", task("a", 0.05)), ("b", task("b", 0.05))], warm_up_first=False)
    assert events[:2] == ["start a", "start b"] or events[:2] == ["start b", "start a"]


def test_results_keep_task_order_whatever_finishes_first():
    _, task = recorder()
    results = run_parallel([("w", task("w")), ("slow", task("slow", 0.1)), ("fast", task("fast"))])
    assert [r["label"] for r in results] == ["w", "slow", "fast"]


def test_a_raising_task_becomes_an_error_result_and_others_still_run():
    def boom():
        raise ValueError("bad input")
    _, task = recorder()
    results = run_parallel([("ok", task("ok")), ("boom", boom), ("ok2", task("ok2"))])
    assert results[1] == {"label": "boom", "status": "error", "error": "ValueError: bad input"}
    assert results[2]["status"] == "success"


def test_no_tasks_no_results():
    assert run_parallel([]) == []
