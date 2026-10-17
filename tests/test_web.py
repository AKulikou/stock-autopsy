"""The web UI's API end to end, with a fake Claude and the frozen Coca-Cola fixture (no network)."""

import json
import re
import threading
import time
from dataclasses import replace

import pytest
from conftest import text_response
from fastapi.testclient import TestClient
from sample_outputs import handler_for

from datalayer.pack import build_pack
from datalayer.sec import UnknownTickerError
from scripts.freeze_golden import FIXTURES, raw_from_fixture
from translate.numbers import numbers_in
from web import app as app_module
from web import resolve as resolve_module
from web.app import create_app
from web.resolve import Suggestion, Suggestions
from web.view import file_name_part

BASE_URL = "http://127.0.0.1:8001"
TICKER_MAP = {
    "0": {"cik_str": 21344, "ticker": "KO", "title": "COCA COLA CO"},
    "1": {"cik_str": 1041061, "ticker": "YUM", "title": "YUM BRANDS INC"},
    "2": {"cik_str": 1577552, "ticker": "BABA", "title": "Alibaba Group Holding Ltd"},
}
CODES = ("STRONG_CASE", "CONDITIONAL_CASE", "WEAK_CASE", "RED_FLAGGED", "INSUFFICIENT_DATA",
         "RED_FLAG", "ADEQUATE", "[DATA]", "financials_annual.", "derived.")
CODE_KEYS = {"verdict", "status", "kind", "key", "check"}


def fake_fetch(ticker, as_of):
    if ticker == "BABA":  # a foreign filer: a price, no us-gaap statements
        raw = raw_from_fixture(FIXTURES / "KO")
        return replace(raw, ticker="BABA", company_facts={"cik": 1, "entityName": "Alibaba", "facts": {}})
    if ticker != "KO":
        raise UnknownTickerError(f"{ticker}: Stock Autopsy covers US SEC filers only.")
    return raw_from_fixture(FIXTURES / "KO")


def fake_filer_check(ticker, cik):
    return "Files Form 20-F (a foreign company): no financial data." if ticker == "BABA" else None


@pytest.fixture
def ko_pack():
    return build_pack(raw_from_fixture(FIXTURES / "KO"))[0]


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "results", fetch=fake_fetch, ticker_map=lambda: TICKER_MAP,
                     filer_check=fake_filer_check)
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
    for asset in ("app.js", "events.js", "cards.js", "markdown.js", "tokens.css", "app.css"):
        assert client.get(f"/static/{asset}").status_code == 200, asset


def test_a_ticker_in_capitals_resolves_without_a_model_call(client, fake):
    found = client.post("/api/resolve", json={"query": "KO"}).json()
    assert found["candidates"] == [
        {"ticker": "KO", "name": "Coca Cola Co", "note": None, "unsupported": None}
    ]
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


def test_a_foreign_filer_is_flagged_at_the_lookup_for_free(client, fake):
    found = client.post("/api/resolve", json={"query": "BABA"}).json()
    assert found["candidates"][0]["unsupported"].startswith("Files Form 20-F")
    assert fake.requests == []


def test_a_run_on_an_empty_data_pack_stops_before_any_claude_call(client, fake):
    run_id = client.post("/api/runs", json={"ticker": "BABA"}).json()["run_id"]
    events = follow(client, run_id)
    stages = [(e["stage"], e["status"]) for e in events]
    assert stages == [("fetch", "started"), ("fetch", "done"), ("pack", "failed"), ("run", "failed")]
    assert "no annual statements" in events[-1]["text"]
    view = client.get(f"/api/runs/{run_id}/result").json()
    assert view["analyzed"] is False and "no annual statements" in view["error"]
    assert fake.requests == []


def test_requests_from_another_site_or_host_are_refused(client, fake, tmp_path):
    foreign = {"Origin": "https://evil.example"}
    assert client.post("/api/runs", json={"ticker": "KO"}, headers=foreign).status_code == 403
    app = create_app(tmp_path / "r", fetch=fake_fetch, ticker_map=lambda: TICKER_MAP)
    with TestClient(app, base_url="http://attacker.example") as other:
        assert other.get("/api/options").status_code == 400
    assert fake.requests == []


def test_a_finished_report_is_translated_on_demand_and_offered_as_a_file(client, fake):
    def russian(kwargs):
        source = kwargs["messages"][0]["content"]
        numbers = " и ".join(n.text.replace(".", ",") for n in numbers_in(source, english=True))
        words = "Перевод этого раздела отчёта на русский язык с сохранением всех чисел. " * 40
        return text_response(f"{source.splitlines()[0]} (RU)\n\n{words}{numbers}\n")

    fake.create_handler = russian
    options = client.get("/api/options").json()
    assert options["default_language"] == "Russian" and options["languages"][0]["label"] == "Русский"
    run_id = client.post("/api/runs", json={"ticker": "KO"}).json()["run_id"]
    follow(client, run_id)
    assert client.get(f"/api/runs/{run_id}/translations/ru").status_code == 404

    done = client.post(f"/api/runs/{run_id}/translation", json={"language": "Russian"}).json()
    assert done["download_label"] == "Save report in Russian (report.ru.md)"
    assert done["markdown"].startswith("> Machine translation into Russian") and done["kept_in_english"] == 0
    calls = len(fake.requests)
    file = client.get(f"/api/runs/{run_id}/translations/ru")
    assert file.status_code == 200 and file.text.replace("\r\n", "\n") == done["markdown"]
    again = client.post(f"/api/runs/{run_id}/translation", json={"language": "ru"}).json()
    assert "nothing was paid" in again["note"] and len(fake.requests) == calls
    assert client.post(f"/api/runs/{run_id}/translation", json={"language": "Klingon"}).status_code == 422


def test_an_analysis_that_did_not_finish_cannot_be_translated(client, fake):
    run_id = client.post("/api/runs", json={"ticker": "BABA"}).json()["run_id"]
    follow(client, run_id)
    assert client.post(f"/api/runs/{run_id}/translation", json={"language": "Russian"}).status_code == 409
    assert fake.requests == []


def test_events_resume_from_a_given_event_without_a_replay(client, fake):
    run_id = client.post("/api/runs", json={"ticker": "KO"}).json()["run_id"]
    everything = follow(client, run_id)
    later = []
    with client.stream("GET", f"/api/runs/{run_id}/events?since=3") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                later.append(json.loads(line[len("data: "):]))
    assert later == everything[3:]


def test_a_quiet_run_sends_a_heartbeat_comment(tmp_path, fake, monkeypatch):
    def slow_fetch(ticker, as_of):
        time.sleep(0.6)
        raise UnknownTickerError(f"{ticker}: Stock Autopsy covers US SEC filers only.")

    monkeypatch.setattr(app_module, "HEARTBEAT_S", 0.1)
    app = create_app(tmp_path / "results", fetch=slow_fetch, ticker_map=lambda: TICKER_MAP,
                     filer_check=fake_filer_check)
    with TestClient(app, base_url=BASE_URL) as slow:
        run_id = slow.post("/api/runs", json={"ticker": "KO"}).json()["run_id"]
        with slow.stream("GET", f"/api/runs/{run_id}/events") as stream:
            lines = list(stream.iter_lines())
    assert ": still working" in lines
    assert json.loads([line for line in lines if line.startswith("data: ")][-1][6:])["stage"] == "run"


def test_a_running_analysis_answers_still_running_not_failed(tmp_path, fake):
    release = threading.Event()

    def waiting_fetch(ticker, as_of):
        release.wait(5)
        raise UnknownTickerError("stop")

    app = create_app(tmp_path / "results", fetch=waiting_fetch, ticker_map=lambda: TICKER_MAP,
                     filer_check=fake_filer_check)
    with TestClient(app, base_url=BASE_URL) as waiting:
        run_id = waiting.post("/api/runs", json={"ticker": "KO"}).json()["run_id"]
        answer = waiting.get(f"/api/runs/{run_id}/result")
        assert answer.status_code == 409 and answer.json()["detail"] == "The analysis is still running."
        assert waiting.get("/api/runs/recent").json()["runs"] == []
        release.set()
        follow(waiting, run_id)


def test_finished_analyses_can_be_reopened_from_the_recent_list(client, fake):
    run_id = client.post("/api/runs", json={"ticker": "KO"}).json()["run_id"]
    follow(client, run_id)
    failed_id = client.post("/api/runs", json={"ticker": "ZZZZ"}).json()["run_id"]
    follow(client, failed_id)
    recent = client.get("/api/runs/recent").json()["runs"]
    assert [r["run_id"] for r in recent] == [failed_id, run_id]  # newest first
    assert recent[1]["company"] == "Coca Cola Co" and recent[1]["outcome"] == "Conditional case"
    assert recent[0]["analyzed"] is False
    assert all("KO" not in text.split() for r in recent for text in shown_texts(r))


def test_the_tagline_claims_only_what_the_number_check_proves(client):
    page = client.get("/").text
    assert "every quoted number checked against the data" in page
    assert "traced to a filing" not in page


@pytest.mark.parametrize(
    ("company", "part"),
    [("COCA COLA CO", "Coca_Cola_Co"), ("Yum! Brands, Inc.", "Yum_Brands_Inc"), ("AT&T INC.", "At_T_Inc")],
)
def test_the_company_part_of_a_file_name(company, part):
    assert file_name_part(company) == part


def test_a_name_cut_at_forty_characters_ends_without_an_underscore():
    assert file_name_part("Abcdefghij " * 6) == "Abcdefghij_Abcdefghij_Abcdefghij_Abcdefg"
    assert file_name_part("Abcdefghi " * 6).endswith("Abcdefghi")


def test_the_downloaded_report_is_named_after_the_company_first(client, fake):
    run_id = client.post("/api/runs", json={"ticker": "KO"}).json()["run_id"]
    follow(client, run_id)
    disposition = client.get(f"/api/runs/{run_id}/files/report").headers["content-disposition"]
    assert re.search(r'filename="Coca_Cola_Co_KO_\d{4}-\d{2}-\d{2}_\d{6}_report\.md"', disposition)


def test_the_page_learns_the_five_analysts_and_what_each_waits_for(client):
    analysts = client.get("/api/options").json()["analysts"]
    assert [a["key"] for a in analysts] == [
        "valuation_assumptions", "business_model", "forensic", "valuation", "pre_mortem"]
    assert analysts[0]["waits_for"] == "the data pack"
    assert all(a["label"] and a["waits_for"] for a in analysts)
