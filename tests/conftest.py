"""
Shared test fixtures. No test calls the Anthropic API: a fake client stands in
for it and answers each structured request according to the test's script.
"""

import os
import threading
from types import SimpleNamespace

# config.py refuses to import without a plausible key; tests never use it.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-not-used")

import pytest

from analysis import runner as runner_module
from core import claude_client as claude_client_module
from eval import judge as judge_module
from perspectives import perspective as perspective_module
from translate import translator as translator_module


def response(parsed, stop_reason="end_turn", input_tokens=1000, output_tokens=500,
             cache_write=0, cache_read=0, web_searches=0):
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="server_tool_use")] if stop_reason == "pause_turn" else [],
        _request_id="req_test",
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_write,
            cache_read_input_tokens=cache_read,
            server_tool_use=SimpleNamespace(web_search_requests=web_searches),
        ),
    )


class FakeClaude:
    """
    Answers messages.parse(). `handler` takes the request kwargs and returns a
    response() or raises. Every request is recorded (thread-safe).

    With `simulate_cache`, a request whose first system block carries a cache
    breakpoint reports a cache write the first time that text is seen and a cache
    read afterwards, like the API once the first response has begun.
    """

    def __init__(self, handler=None, simulate_cache=False, create_handler=None):
        self.requests: list[dict] = []
        self.handler = handler
        self.create_handler = create_handler
        self.simulate_cache = simulate_cache
        self._cached: set[str] = set()
        self._lock = threading.Lock()
        self.messages = SimpleNamespace(parse=self._parse, create=self._create)

    def _create(self, **kwargs):
        """Plain-text requests (the translator); answered by `create_handler`."""
        with self._lock:
            self.requests.append(kwargs)
        if self.create_handler is None:
            raise RuntimeError("this test sent a messages.create request it did not script")
        return self.create_handler(kwargs)

    def _parse(self, **kwargs):
        with self._lock:
            self.requests.append(kwargs)
            write = read = 0
            system = kwargs.get("system")
            if self.simulate_cache and isinstance(system, list) and system[0].get("cache_control"):
                prefix = system[0]["text"]
                size = len(prefix) // 4
                if prefix in self._cached:
                    read = size
                else:
                    write = size
                    self._cached.add(prefix)
        answer = self.handler(kwargs)
        answer.usage.cache_creation_input_tokens = write or answer.usage.cache_creation_input_tokens
        answer.usage.cache_read_input_tokens = read or answer.usage.cache_read_input_tokens
        return answer


def text_response(text, stop_reason="end_turn", input_tokens=3000, output_tokens=4000):
    """A messages.create() answer with one text block."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


@pytest.fixture
def fake_claude(monkeypatch):
    """Factory: build a FakeClaude and install it where the code gets its client."""
    def install(handler, simulate_cache=False) -> FakeClaude:
        fake = FakeClaude(handler, simulate_cache)
        monkeypatch.setattr(perspective_module, "get_client", lambda: fake)
        monkeypatch.setattr(runner_module, "get_client", lambda: fake)
        monkeypatch.setattr(judge_module, "get_client", lambda: fake)
        monkeypatch.setattr(translator_module, "get_client", lambda: fake)
        return fake
    return install


@pytest.fixture(autouse=True)
def no_real_client(monkeypatch):
    """A module that calls get_client() without being patched fails loudly
    instead of reaching the real API."""
    def refuse():
        raise RuntimeError("a test reached the real Anthropic client; patch its module in fake_claude")
    monkeypatch.setattr(claude_client_module, "_direct_client", refuse)


# Scale and unit words a fake translation must keep as words of the same meaning.
RUSSIAN_UNITS = {"trillion": "трлн", "billion": "млрд", "million": "млн", "thousand": "тыс.",
                 "percent": "процентов", "times": "раза", "points": "п. п.", "point": "п. п.",
                 "percentage": ""}


def fake_russian(source: str) -> str:
    """
    A stand-in translation that keeps the Markdown structure, every number, date and
    code span, and turns each English word into a Russian one (scale words into their
    Russian forms), so it passes the translator's checks the way a good answer does.
    """
    import re

    def word(match: re.Match) -> str:
        return RUSSIAN_UNITS.get(match.group(0).lower(), "текст")

    kept = re.split(r"(`[^`]*`)", source)
    return "".join(part if part.startswith("`") else re.sub(r"\b[A-Za-z]{2,}\b", word, part) for part in kept)
