"""The batching client: many threads' requests in one batch, answers matched by id."""

import json
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from core import token_summary
from core.batch_client import BatchingClient


class Answer(BaseModel):
    value: str


def message(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        id="msg_1", stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


class FakeBatches:
    """Answers each request with its own user message, results in reverse order."""

    def __init__(self, fail_ids=()):
        self.created = []
        self.fail_ids = set(fail_ids)

    def create(self, requests):
        self.created.append(requests)
        return SimpleNamespace(id=f"batch_{len(self.created)}", processing_status="in_progress")

    def retrieve(self, batch_id):
        return SimpleNamespace(id=batch_id, processing_status="ended")

    def results(self, batch_id):
        requests = self.created[int(batch_id.split("_")[1]) - 1]
        for request in reversed(requests):
            custom_id, params = request["custom_id"], request["params"]
            if custom_id in self.fail_ids:
                result = SimpleNamespace(type="errored", error=SimpleNamespace(error="overloaded"))
            else:
                user = params["messages"][0]["content"]
                result = SimpleNamespace(type="succeeded", message=message(json.dumps({"value": user})))
            yield SimpleNamespace(custom_id=custom_id, result=result)


def client_with(batches) -> BatchingClient:
    return BatchingClient(SimpleNamespace(messages=SimpleNamespace(batches=batches)), window_s=0.2, poll_s=0)


def ask(client, text, out, key):
    try:
        out[key] = client.messages.parse(
            model="m", max_tokens=100, system="s",
            messages=[{"role": "user", "content": text}],
            output_format=Answer, output_config={"effort": "low"},
        )
    except Exception as e:
        out[key] = e


def ask_in_parallel(client, texts) -> dict:
    out = {}
    threads = [threading.Thread(target=ask, args=(client, t, out, t)) for t in texts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    return out


def test_parallel_requests_share_one_batch_and_get_their_own_answers():
    batches = FakeBatches()
    out = ask_in_parallel(client_with(batches), ["a", "b", "c"])
    assert len(batches.created) == 1 and len(batches.created[0]) == 3
    assert {k: v.parsed_output.value for k, v in out.items()} == {"a": "a", "b": "b", "c": "c"}


def test_request_carries_the_schema_and_keeps_other_output_settings():
    batches = FakeBatches()
    ask_in_parallel(client_with(batches), ["a"])
    config = batches.created[0][0]["params"]["output_config"]
    assert config["effort"] == "low"
    assert config["format"]["type"] == "json_schema"
    assert "value" in config["format"]["schema"]["properties"]


def test_a_failed_request_raises_only_for_its_caller():
    batches = FakeBatches(fail_ids={"r0"})
    out = ask_in_parallel(client_with(batches), ["only"])
    assert isinstance(out["only"], RuntimeError) and "errored" in str(out["only"])


def test_a_truncated_answer_is_passed_on_unparsed_for_the_caller_to_reject():
    batches = FakeBatches()
    batches.results = lambda batch_id: iter([SimpleNamespace(
        custom_id="r0", result=SimpleNamespace(type="succeeded", message=message('{"val', "max_tokens")))])
    out = ask_in_parallel(client_with(batches), ["x"])
    assert out["x"].stop_reason == "max_tokens" and out["x"].parsed_output is None


def test_batch_pricing_halves_token_cost(monkeypatch):
    full = token_summary.estimate_cost(1_000_000, 0, "claude-sonnet-4-6")
    monkeypatch.setattr(token_summary, "token_price_factor", token_summary.BATCH_TOKEN_DISCOUNT)
    assert token_summary.estimate_cost(1_000_000, 0, "claude-sonnet-4-6") == pytest.approx(full / 2)


class FlakyBatches(FakeBatches):
    """The network failures of 2026-10-22: the create call times out after the batch exists
    on the server, and status checks time out now and then."""

    def __init__(self, create_fails=0, retrieve_fails=0, adoptable=True):
        super().__init__()
        self.create_fails, self.retrieve_fails, self.adoptable = create_fails, retrieve_fails, adoptable
        self.listed = 0

    def create(self, requests):
        batch = super().create(requests)
        if self.create_fails:
            self.create_fails -= 1
            if not self.adoptable:
                self.created.pop()
            raise TimeoutError("create timed out")
        return batch

    def retrieve(self, batch_id):
        if self.retrieve_fails:
            self.retrieve_fails -= 1
            raise TimeoutError("retrieve timed out")
        return super().retrieve(batch_id)

    def list(self, limit=20):
        self.listed += 1
        now = datetime.now(timezone.utc)
        return [SimpleNamespace(id=f"batch_{n}", created_at=now, processing_status="in_progress",
                                request_counts=SimpleNamespace(processing=len(requests), succeeded=0,
                                                               errored=0, canceled=0, expired=0))
                for n, requests in reversed(list(enumerate(self.created, start=1)))]


def test_a_batch_created_although_the_create_call_timed_out_is_adopted_not_sent_again():
    batches = FlakyBatches(create_fails=1)
    out = ask_in_parallel(client_with(batches), ["a", "b"])
    assert len(batches.created) == 1 and batches.listed == 1  # no second, paid copy
    assert {k: v.parsed_output.value for k, v in out.items()} == {"a": "a", "b": "b"}


def test_status_checks_that_time_out_do_not_fail_the_batch():
    batches = FlakyBatches(retrieve_fails=3)
    out = ask_in_parallel(client_with(batches), ["a"])
    assert out["a"].parsed_output.value == "a"


def test_a_create_that_failed_without_a_batch_reaches_the_callers():
    batches = FlakyBatches(create_fails=1, adoptable=False)
    out = ask_in_parallel(client_with(batches), ["a"])
    assert isinstance(out["a"], TimeoutError) and batches.created == []
