"""
A client that sends structured requests through the Message Batches API.

Batched requests cost half the normal token price, but results arrive after
minutes instead of seconds, so this suits the eval, not an interactive run.

It is a drop-in for the one call the pipeline makes, `client.messages.parse()`:
each calling thread blocks while its request waits in a batch. Requests that
arrive close together (all eval cases start at once, and their perspectives run in
parallel) are collected into one batch; after `window_s` without a new request
the batch is sent. The pipeline code stays unchanged: retries, validation and
server-tool continuations simply become requests in the next batch.

Prompt caching works inside batches only on a best-effort basis: batched
requests run concurrently and in any order, so a shared prefix may be written
several times. The prompt caching docs suggest sending one request with the
shared prefix first and the rest after it completes.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import anthropic
from anthropic import Anthropic, transform_schema
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger(__name__)

# One call to the batches API, not the batch: it should answer in seconds (2026-10-22: a call
# hung for the SDK's default 10 minutes, three times, and the eval lost two finished batches).
CREATE_TIMEOUT_S = 120.0
CALL_TIMEOUT_S = 60.0
MAX_CALL_FAILURES = 30  # failed status checks in a row before the batch is given up
TRANSIENT = (anthropic.APIConnectionError, anthropic.InternalServerError, anthropic.RateLimitError,
             TimeoutError)


@dataclass
class _Slot:
    params: dict
    done: threading.Event = field(default_factory=threading.Event)
    message: object = None
    error: Exception | None = None


class BatchingClient:
    """Collects messages.parse() calls from many threads into Message Batches."""

    def __init__(self, client: Anthropic, window_s: float = 10.0, poll_s: float = 30.0):
        self._client = client
        self._window_s = window_s
        self._poll_s = poll_s
        self._lock = threading.Lock()
        self._pending: list[_Slot] = []
        self._timer: threading.Timer | None = None
        self.batches_sent = 0
        self._seen: set[str] = set()  # batches already used, never adopted twice
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, *, output_format: type[BaseModel], **params) -> SimpleNamespace:
        """Same arguments and result fields as messages.parse(), answered from a batch."""
        schema = transform_schema(TypeAdapter(output_format).json_schema())
        output_config = dict(params.pop("output_config", None) or {})
        output_config["format"] = {"type": "json_schema", "schema": schema}
        slot = _Slot({**params, "output_config": output_config})

        with self._lock:
            self._pending.append(slot)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._window_s, self._flush)
            self._timer.daemon = True
            self._timer.start()

        slot.done.wait()
        if slot.error:
            raise slot.error
        return _parsed(slot.message, output_format)

    def _flush(self) -> None:
        with self._lock:
            slots, self._pending, self._timer = self._pending, [], None
        if not slots:
            return
        try:
            self._run_batch(slots)
        except Exception as e:  # the whole batch failed: every waiting caller gets the error
            logger.warning(f"Batch of {len(slots)} request(s) failed: {type(e).__name__}: {e}")
            for slot in slots:
                if not slot.done.is_set():
                    slot.error = e
                    slot.done.set()

    def _api(self, timeout_s: float, retries: int):
        """The batches API with a per-call timeout (a fake client in tests has no with_options)."""
        client = self._client
        if hasattr(client, "with_options"):
            client = client.with_options(timeout=timeout_s, max_retries=retries)
        return client.messages.batches

    def _create(self, requests: list) -> object:
        """
        Send the batch once. A create call that times out may still have made the batch on the
        server (2026-10-22: two batches ran and were billed while the client gave up), so the
        client looks for it before it gives up, and never sends a second, paid copy.
        """
        sent_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        try:
            return self._api(CREATE_TIMEOUT_S, 0).create(requests=requests)
        except TRANSIENT as e:
            logger.warning(f"Batch create failed ({type(e).__name__}); looking for the batch on the server")
            time.sleep(self._poll_s)
            for batch in self._api(CALL_TIMEOUT_S, 2).list(limit=20):
                counts = batch.request_counts
                total = sum(getattr(counts, k, 0) or 0 for k in ("processing", "succeeded", "errored",
                                                                  "canceled", "expired"))
                if batch.created_at >= sent_at and total == len(requests) and batch.id not in self._seen:
                    logger.warning(f"Batch {batch.id}: adopted the batch the failed create call made")
                    return batch
            raise

    def _retrieve(self, batch_id: str):
        """The batch's status; a status check that fails is tried again at the next poll."""
        failures = 0
        while True:
            try:
                return self._api(CALL_TIMEOUT_S, 2).retrieve(batch_id)
            except TRANSIENT as e:
                failures += 1
                if failures >= MAX_CALL_FAILURES:
                    raise
                logger.warning(f"Batch {batch_id}: status check failed ({type(e).__name__}), "
                               f"{failures} in a row")
                time.sleep(self._poll_s)

    def _results(self, batch_id: str) -> list:
        failures = 0
        while True:
            try:
                return list(self._api(CALL_TIMEOUT_S, 2).results(batch_id))
            except TRANSIENT as e:
                failures += 1
                if failures >= MAX_CALL_FAILURES:
                    raise
                logger.warning(f"Batch {batch_id}: results download failed ({type(e).__name__}), retrying")
                time.sleep(self._poll_s)

    def _run_batch(self, slots: list[_Slot]) -> None:
        by_id = {f"r{i}": slot for i, slot in enumerate(slots)}
        batch = self._create([
            Request(custom_id=custom_id, params=MessageCreateParamsNonStreaming(**slot.params))
            for custom_id, slot in by_id.items()
        ])
        self._seen.add(batch.id)
        self.batches_sent += 1
        logger.info(f"Batch {batch.id}: {len(slots)} request(s) sent")
        started = time.monotonic()
        while batch.processing_status != "ended":
            time.sleep(self._poll_s)
            batch = self._retrieve(batch.id)
        logger.info(f"Batch {batch.id}: ended after {time.monotonic() - started:.0f}s")

        # Results come in any order: match them by custom_id, never by position.
        for item in self._results(batch.id):
            slot = by_id.get(item.custom_id)
            if slot is None:
                continue
            if item.result.type == "succeeded":
                slot.message = item.result.message
            else:
                detail = getattr(getattr(item.result, "error", None), "error", None)
                slot.error = RuntimeError(f"Batch request {item.result.type}: {detail or 'no details'}")
            slot.done.set()
        for custom_id, slot in by_id.items():
            if not slot.done.is_set():
                slot.error = RuntimeError(f"Batch {batch.id} returned no result for {custom_id}")
                slot.done.set()


def _parsed(message, output_format: type[BaseModel]) -> SimpleNamespace:
    """The fields request_structured() reads from a messages.parse() result."""
    parsed = None
    if message.stop_reason == "end_turn":
        texts = [block.text for block in message.content if block.type == "text"]
        if not texts:
            raise RuntimeError("Batch result has no text block to parse")
        # With server tools the structured answer is the final text block.
        parsed = output_format.model_validate_json(texts[-1])
    return SimpleNamespace(
        content=message.content,
        stop_reason=message.stop_reason,
        usage=message.usage,
        parsed_output=parsed,
        _request_id=message.id,
    )
