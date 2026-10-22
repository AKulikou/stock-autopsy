"""Company lookup (decision D5): exact matches, related companies, private companies, failures."""

import logging

import pytest
from conftest import response

from web import resolve as resolve_module
from web.resolve import LOOKUP_FAILED, NOT_FOUND, Suggestion, Suggestions, resolve, same_company

TICKER_MAP = {
    "0": {"cik_str": 21344, "ticker": "KO", "title": "COCA COLA CO"},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    "2": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "3": {"cik_str": 1605484, "ticker": "STLA", "title": "Stellantis N.V."},
    "4": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
    "5": {"cik_str": 1652044, "ticker": "GOOG", "title": "Alphabet Inc."},
    "6": {"cik_str": 1826011, "ticker": "PARA", "title": "Banzai International, Inc."},
    "7": {"cik_str": 2041610, "ticker": "PSKY", "title": "Skydance Corp"},
}


def filer_check(ticker, cik):
    return "Files Form 20-F (a foreign company): no financial data." if ticker == "STLA" else None


def listed_name(ticker):
    """The company name the model gives: the SEC title here, unless a test says otherwise."""
    entry = next((e for e in TICKER_MAP.values() if e["ticker"] == ticker.upper()), None)
    return entry["title"] if entry else "Unknown Company"


def exact(ticker, note="The company itself.", share_class=None, company_name=None):
    return Suggestion(ticker=ticker, company_name=company_name or listed_name(ticker), match_type="exact",
                      relation=None, share_class=share_class, note=note)


def related(ticker, relation):
    return Suggestion(ticker=ticker, company_name=listed_name(ticker), match_type="related",
                      relation=relation, share_class=None,
                      note=f"{relation[0].upper()}{relation[1:]}.")


def answer(query_name, candidates, reason=None):
    return Suggestions(query_name=query_name, is_private_or_not_listed=reason is not None,
                       not_listed_reason=reason, candidates=candidates)


@pytest.fixture
def lookup(fake_claude, monkeypatch):
    """Answers the lookup call with the given Suggestions (or raises the given error)."""
    def install(result):
        def handle(request):
            if isinstance(result, Exception):
                raise result
            return response(result)
        fake = fake_claude(handle)
        monkeypatch.setattr(resolve_module, "get_client", lambda: fake)
        return fake
    return install


def test_an_exact_match_is_offered_without_a_banner(lookup):
    lookup(answer("Coca-Cola", [exact("KO")]))
    found = resolve("coca cola", TICKER_MAP, filer_check)
    assert [(c["ticker"], c["match_type"], c["relation"]) for c in found["candidates"]] == [
        ("KO", "exact", None)]
    assert found["banner"] is None and found["message"] is None and found["error"] is None


def test_related_companies_of_a_private_company_come_under_a_banner(lookup):
    lookup(answer("OpenAI", [related("MSFT", "major investor in OpenAI"),
                             related("NVDA", "investor in OpenAI and its chip supplier")],
                  reason="is a private company"))
    found = resolve("openai", TICKER_MAP, filer_check)
    assert found["banner"] == ("OpenAI is a private company and files no reports with the SEC. "
                               "Related public companies:")
    assert [(c["name"], c["match_type"], c["relation"]) for c in found["candidates"]] == [
        ("Microsoft Corp", "related", "major investor in OpenAI"),
        ("Nvidia Corp", "related", "investor in OpenAI and its chip supplier"),
    ]
    assert all(c["unsupported"] is None for c in found["candidates"])


def test_a_private_company_with_no_related_one_gets_a_calm_message(lookup):
    lookup(answer("Acme Robotics", [], reason="is a private company"))
    found = resolve("acme robotics", TICKER_MAP, filer_check)
    assert found["candidates"] == [] and found["error"] is None and found["banner"] is None
    assert found["message"] == ("Acme Robotics is a private company and files no reports with the SEC. "
                                "No related US-listed company was found.")


def test_a_related_foreign_filer_is_shown_but_cannot_be_analyzed(lookup):
    lookup(answer("Chrysler", [related("STLA", "parent of Chrysler")],
                  reason="is a brand, not a company of its own"))
    found = resolve("chrysler", TICKER_MAP, filer_check)
    (stellantis,) = found["candidates"]
    assert stellantis["match_type"] == "related" and stellantis["relation"] == "parent of Chrysler"
    assert stellantis["unsupported"].startswith("Files Form 20-F")
    assert found["banner"] == ("Chrysler is a brand, not a company of its own, and files no reports with "
                               "the SEC. Related public companies:")


def test_a_failed_model_call_is_an_error_to_retry_not_a_message(lookup):
    lookup(RuntimeError("model unreachable"))
    found = resolve("openai", TICKER_MAP, filer_check)
    assert found["candidates"] == [] and found["message"] is None
    assert found["error"] == LOOKUP_FAILED


def test_nothing_found_is_a_calm_message(lookup):
    lookup(answer("Xyzzy", []))
    found = resolve("xyzzy", TICKER_MAP, filer_check)
    assert found["message"] == NOT_FOUND and found["error"] is None


def test_candidates_come_exact_then_related_then_those_that_cannot_be_analyzed(lookup):
    lookup(answer("Mixed", [related("STLA", "parent of a brand"), related("MSFT", "investor"), exact("KO")]))
    found = resolve("mixed", TICKER_MAP, filer_check)
    assert [c["ticker"] for c in found["candidates"]] == ["KO", "MSFT", "STLA"]


def test_share_classes_are_both_exact_matches_with_their_class(lookup):
    lookup(answer("Alphabet", [exact("GOOGL", share_class="Class A"), exact("GOOG", share_class="Class C")]))
    found = resolve("alphabet", TICKER_MAP, filer_check)
    assert [(c["match_type"], c["share_class"]) for c in found["candidates"]] == [
        ("exact", "Class A"), ("exact", "Class C")]


def test_the_log_says_what_was_proposed_kept_and_dropped(lookup, caplog):
    lookup(answer("OpenAI", [related("MSFT", "major investor in OpenAI"), related("ZZZZ", "not listed"),
                             related("STLA", "partner")],
                  reason="is a private company"))
    with caplog.at_level(logging.INFO, logger="web.resolve"):
        resolve("openai", TICKER_MAP, filer_check)
    log = caplog.text
    assert "'openai'" in log and "'OpenAI'" in log and "private or not US-listed: True" in log
    assert "MSFT related (major investor in OpenAI): kept" in log
    assert "ZZZZ related (not listed): dropped, not in the SEC list" in log
    assert "STLA related (partner): kept, cannot be analyzed: Files Form 20-F" in log


def test_a_duplicate_candidate_is_dropped_and_logged(lookup, caplog):
    lookup(answer("Microsoft", [exact("MSFT"), exact("msft", note="Again.")]))
    with caplog.at_level(logging.INFO, logger="web.resolve"):
        found = resolve("microsoft", TICKER_MAP, filer_check)
    assert [c["ticker"] for c in found["candidates"]] == ["MSFT"]
    assert "msft exact: dropped, duplicate" in caplog.text


def test_a_ticker_the_sec_list_gives_to_another_company_is_dropped(lookup, caplog):
    # Real lookup of "paramount", 2026-10-22: PARA was Paramount Global's ticker; the SEC list now
    # gives it to Banzai International, and the page showed that company as an exact match.
    lookup(answer("Paramount", [exact("PSKY", company_name="Paramount Skydance Corporation"),
                                exact("PARA", company_name="Paramount Global")]))
    with caplog.at_level(logging.INFO, logger="web.resolve"):
        found = resolve("paramount", TICKER_MAP, filer_check)
    assert [c["ticker"] for c in found["candidates"]] == ["PSKY"]
    assert "PARA exact: dropped, the SEC list gives this ticker to Banzai International, Inc." in caplog.text


@pytest.mark.parametrize(("model_name", "sec_title"), [
    ("Microsoft Corporation", "MICROSOFT CORP"), ("The Coca-Cola Company", "COCA COLA CO"),
    ("Amazon.com, Inc.", "AMAZON COM INC"), ("Yum! Brands", "YUM BRANDS INC"),
    ("Paramount Skydance Corporation", "Skydance Corp"), ("3M Company", "3M CO"),
])
def test_the_same_company_under_two_spellings_is_kept(model_name, sec_title):
    assert same_company(model_name, sec_title)


def test_different_companies_are_told_apart():
    assert not same_company("Paramount Global", "Banzai International, Inc.")
    assert not same_company("General Motors Company", "General Mills, Inc.")  # one shared word is not enough
    assert same_company("General Motors Company", "GENERAL MOTORS CO")
    assert same_company("Bank of America Corporation", "BANK OF AMERICA CORP /DE/")
    assert same_company("Alphabet Inc. (Google)", "Alphabet Inc.")


def test_a_long_not_listed_reason_gives_a_short_banner(lookup):
    # Real lookup of "chrysler", 2026-10-22: the model's reason ran to sixteen words.
    long_reason = "is a subsidiary of Stellantis, which is listed in the US and not separately by Chrysler"
    lookup(answer("Chrysler", [related("STLA", "parent of Chrysler")], reason=long_reason))
    found = resolve("chrysler", TICKER_MAP, filer_check)
    assert found["banner"] == ("Chrysler is not listed in the US on its own and files no reports with "
                               "the SEC. Related public companies:")


def test_a_typed_ticker_says_which_company_holds_it_now(lookup):
    # PARA was Paramount Global's ticker; the SEC list gives it to Banzai International now.
    fake = lookup(answer("unused", []))
    found = resolve("PARA", TICKER_MAP, filer_check)
    (card,) = found["candidates"]
    assert card["name"] == "Banzai International, Inc."
    assert card["note"] == "The ticker PARA belongs to Banzai International, Inc. in the SEC list."
    assert fake.requests == []  # no model call for a ticker


def test_lookup_cards_show_the_name_without_the_edgar_suffix(lookup):
    lookup(answer("unused", []))
    costco = {"0": {"cik_str": 909832, "ticker": "COST", "title": "COSTCO WHOLESALE CORP /NEW"}}
    (card,) = resolve("COST", costco, filer_check)["candidates"]
    assert card["name"] == "Costco Wholesale Corp"


def test_a_bank_gets_a_calm_note_and_can_still_be_analyzed(lookup):
    from datalayer.sector import FINANCIAL_NOTE
    lookup(answer("unused", []))
    gs = {"0": {"cik_str": 886982, "ticker": "GS", "title": "GOLDMAN SACHS GROUP INC"}}
    (card,) = resolve("GS", gs, filer_check, lambda ticker, cik: FINANCIAL_NOTE)["candidates"]
    assert card["financial_note"] == FINANCIAL_NOTE and card["unsupported"] is None
