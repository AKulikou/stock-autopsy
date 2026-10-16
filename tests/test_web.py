"""The web UI's API end to end, with a fake Claude and the frozen Coca-Cola fixture (no network)."""

import json

import pytest
from fastapi.testclient import TestClient
from sample_outputs import handler_for

from datalayer.pack import build_pack
from datalayer.sec import UnknownTickerError
from scripts.freeze_golden import FIXTURES, raw_from_fixture
from web import resolve as resolve_module
from web.app import create_app
from web.resolve import Suggestion, Suggestions

BASE_URL = "http://127.0.0.1:8001"
TICKER_MAP = {
    "0": {"cik_str": 21344, "ticker": "KO", "title": "COCA COLA CO"},
    "1": {"cik_str": 1041061, "ticker": "YUM", "title": "YUM BRANDS INC"},
}
CODES = ("STRONG_CASE", "CONDITIONAL_CASE", "WEAK_CASE", "RED_FLAGGED", "INSUFFICIENT_DATA",
         "RED_FLAG", "ADEQUATE", "[DATA]", "financials_annual.", "derived.")
CODE_KEYS = {"verdict", "status", "kind", "key", "check"}


def fake_fetch(ticker, as_of):
    if ticker != "KO":
        raise UnknownTickerError(f"{ticker}: Stock Autopsy covers US SEC filers only.")
    return raw_from_fixture(FIXTURES / "KO")


@pytest.fixture
def ko_pack():
    return build_pack(raw_from_fixture(FIXTURES / "KO"))[0]


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "results", fetch=fake_fetch, ticker_map=lambda: TICKER_MAP)
    with TestClient(app, base_url=BASE_URL) as test_client:
        yield test_client


@pytest.fixture
def fake(fake_claude, ko_pack, monkeypatch):
    suggestions = Suggestions(candidates=[
        Suggestion(ticker="YUM", note="KFC belongs to Yum! Brands."),
        Suggestion(ticker=None, note="KFC in China is Yum China, a separate company."),
    ])
    installed = fake_claude(handler_for(ko_pack, {Suggestions: lambda pack: suggestions}))
    monkeypatch.setattr(resolve_module, "get_client", lambda: installed)
    return installed


def follow(client, run_id) -> list[dict]:
    events = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


def shown_texts(value, key=None):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from shown_texts(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from shown_texts(v, key)
    elif isinstance(value, str) and key not in CODE_KEYS:
        yield value


def test_the_page_and_its_scripts_are_served(client):
    assert "<title>Stock Autopsy</title>" in client.get("/").text
    for asset in ("app.js", "events.js", "cards.js", "tokens.css", "app.css"):
        assert client.get(f"/static/{asset}").status_code == 200, asset


def test_a_ticker_in_capitals_resolves_without_a_model_call(client, fake):
    found = client.post("/api/resolve", json={"query": "KO"}).json()
    assert found["candidates"] == [{"ticker": "KO", "name": "Coca Cola Co", "note": None}]
    assert found["suggested"] is False and fake.requests == []


def test_a_brand_gets_suggestions_checked_against_the_sec_list(client, fake):
    found = client.post("/api/resolve", json={"query": "KFC"}).json()
    assert found["suggested"] is True
    assert [c["ticker"] for c in found["candidates"]] == ["YUM"]  # the unlisted one is dropped
    assert found["candidates"][0]["name"] == "Yum Brands Inc"
    assert len(fake.requests) == 1 and fake.requests[0]["model"] == "claude-haiku-5-5"


def test_a_full_run_streams_progress_and_ends_with_the_result_in_words(client, fake):
    run_id = client.post("/api/runs", json={"ticker": "ko"}).json()["run_id"]
    events = follow(client, run_id)
    stages = [(e["stage"], e["status"]) for e in events]
    assert stages[:3] == [("fetch", "started"), ("fetch", "done"), ("pack", "done")]
    assert stages.count(("evaluator", "done")) == 5
    assert ("dcf", "done") in stages and ("committee", "done") in stages
    assert stages[-2:] == [("number_check", "done"), ("run", "done")]

    view = client.get(f"/api/runs/{run_id}/result").json()
    assert view["analyzed"] is True and view["company"] == "Coca Cola Co"
    assert view["committee"]["verdict_text"].startswith("Conditional case")
    assert view["committee"]["reasons_for"] and view["committee"]["price_assumes"]
    assert view["number_check"]["data_claims"] > 0
    leaked = [t for t in shown_texts(view) if any(code in t for code in CODES) or "KO" in t.split()]
    assert leaked == []
    assert [d["kind"] for d in view["downloads"]] == ["report"]
    # report.json is still written for programs, but the page does not offer it.
    assert client.get(f"/api/runs/{run_id}/files/json").status_code == 404
    assert "Stock Autopsy" in client.get(f"/api/runs/{run_id}/files/report").text


def test_an_unknown_ticker_ends_the_run_with_the_reason(client, fake):
    run_id = client.post("/api/runs", json={"ticker": "ZZZZ"}).json()["run_id"]
    events = follow(client, run_id)
    assert events[-1]["status"] == "failed" and "SEC filers only" in events[-1]["text"]
    assert client.get(f"/api/runs/{run_id}/result").json()["analyzed"] is False
    assert fake.requests == []


def test_requests_from_another_site_or_host_are_refused(client, fake, tmp_path):
    foreign = {"Origin": "https://evil.example"}
    assert client.post("/api/runs", json={"ticker": "KO"}, headers=foreign).status_code == 403
    app = create_app(tmp_path / "r", fetch=fake_fetch, ticker_map=lambda: TICKER_MAP)
    with TestClient(app, base_url="http://attacker.example") as other:
        assert other.get("/api/options").status_code == 400
    assert fake.requests == []
