"""Translated copies of a finished report (M13): number check, glossary, sections, retries, files."""

import re
from pathlib import Path

import pytest
from conftest import fake_russian, text_response

from translate.glossary import GLOSSARY_DIR, GlossaryError, load_glossary, parse_glossary
from translate.languages import LANGUAGES, language_name
from translate.numbers import missing_numbers, numbers_in
from translate.translator import (
    MACHINE_TRANSLATION_NOTE,
    RETRY_NOTE,
    UNTRANSLATED_NOTE,
    heading_untranslated,
    looks_untranslated,
    section_problem,
    split_sections,
    structure_changed,
    translate_document,
    translate_report,
    translated_path,
    wrong_language,
)

TEST_GLOSSARIES = Path(__file__).parent / "fixtures" / "glossary"


# ---- the number check ---------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "translation"),
    [
        ("revenue of 1.5 billion", "выручка 1,5 млн"),        # wrong scale
        ("a P/E of 6.71", "P/E 67,1"),                          # wrong decimal place
        ("P/E 6.71 and a margin of 12.2%", "P/E 6,71"),         # a dropped number
        ("a step of 4.5 points", "шаг 4,5 %"),                   # points became a percentage
        ("$2.963 billion", "2,96 млрд долл."),                  # rounded
        ("FY2017 and FY2018", "FY2017"),                        # a dropped year
    ],
)
def test_a_changed_or_dropped_number_is_found(source, translation):
    assert missing_numbers(source, translation)


@pytest.mark.parametrize(
    ("source", "translation"),
    [
        ("revenue of 1.5 billion", "выручка 1,5 млрд"),
        ("revenue of 1.5 billion", "выручка 1.5 billion"),      # kept as it was
        ("$36.21B, 36,212,000,000", "36,21 млрд $, 36 212 000 000"),
        ("$841.00M and 11,539 tokens", "841 млн и 11 539 токенов"),
        ("12.2% a year, 4.5 percentage points", "12,2 % в год, 4,5 п. п."),
        ("2.1 times EBITDA, a 6.71x multiple", "в 2,1 раза больше EBITDA, мультипликатор 6,71х"),
        ("margins of 21-25%", "маржа 21 %–25 %"),
        ("filed 2026-07-29 for FY2025", "подан 2026-07-29 за FY2025"),
        ("a loss of -3 billion", "убыток 3 млрд"),               # signs are not compared
        ("hash `570be69d4`, see [the file](a/b1.md)", "хеш `570be69d4`, см. файл"),
    ],
)
def test_the_same_numbers_written_the_russian_way_pass(source, translation):
    assert missing_numbers(source, translation) == []


@pytest.mark.parametrize(
    ("source", "translation"),
    [
        ("what drove the weak Q4 2025", "что повлияло на слабый четвёртый квартал 2025 года"),
        ("the high end of the 10-year record", "верхняя граница десятилетней истории"),
        ("the user's 5-year horizon, years 1-5", "пятилетний горизонт, годы с первого по пятый"),
        ("check the 10-K tax note and 8-K Item 4.02", "проверьте налоговое примечание годового отчёта"),
        ("10-Q/A filed 2024-05-30", "исправленный отчёт подан 30 мая 2024 года"),
        ("filed 2024-05-30", "подан 30.05.2024"),
        ("filed 2024-05-30", "filed May 30, 2024"),
    ],
)
def test_labels_durations_and_dates_may_be_written_in_words(source, translation):
    assert missing_numbers(source, translation) == []


@pytest.mark.parametrize(
    ("source", "translation"),
    [("filed 2024-05-30", "подан 30 июня 2024"), ("filed 2024-05-30 and 2025-02-20", "подан 30.05.2024"),
     ("FY2017 and FY2018", "FY2017")],
)
def test_a_wrong_or_dropped_date_or_year_is_still_found(source, translation):
    assert missing_numbers(source, translation)


def test_each_number_of_the_translation_answers_for_one_number_of_the_source():
    assert missing_numbers("2024 and 2024", "2024") == ["2024"]
    assert numbers_in("FY2024", english=True)[0].values == {2024}


# ---- the glossary -------------------------------------------------------------


def test_the_test_glossary_reads_with_its_title_and_three_fields():
    glossary = load_glossary("Russian", TEST_GLOSSARIES)
    assert glossary.title == "Словарь"
    assert glossary.entries[0].variants == ("free cash flow", "FCF")
    assert len(glossary.entries) == 3
    assert all(e.term and e.explanation for e in glossary.entries)


@pytest.mark.parametrize("path", sorted(GLOSSARY_DIR.glob("*.md")), ids=lambda p: p.name)
def test_every_glossary_in_the_repository_has_all_three_fields(path):
    glossary = parse_glossary(path.read_text(encoding="utf-8"), str(path))
    assert language_name(path.stem.replace("_", " ")), f"{path.name} is not an offered language"
    assert all(e.variants and e.term and e.explanation for e in glossary.entries)


@pytest.mark.parametrize(
    "text",
    [
        "| English | Термин | Пояснение |\n|---|---|---|\n| FCF | FCF | Деньги. |\n",  # no title
        "# Словарь\n\n| English | Термин | Пояснение |\n|---|---|---|\n| FCF | FCF |  |\n",
        "# Словарь\n\n| English | Термин | Пояснение |\n|---|---|---|\n| FCF | FCF |\n",
        "# Словарь\n\nNo table.\n",
    ],
)
def test_a_glossary_without_a_title_or_with_an_incomplete_row_is_refused(text):
    with pytest.raises(GlossaryError):
        parse_glossary(text)


def test_terms_match_whole_words_in_any_case_and_only_used_terms_are_listed():
    glossary = load_glossary("Russian", TEST_GLOSSARIES)
    terms = [e.term for e in glossary.used_in("Free Cash Flow fell; FCF yield")]
    assert terms == ["свободный денежный поток (FCF)"]
    assert glossary.used_in("FCFA and restatementary") == []  # whole words (or plurals) only
    assert len(glossary.used_in("two restatements")) == 1
    section = glossary.section("The FY2018 figures were restated.")
    assert section.startswith("## Словарь\n\n- **пересчёт отчётности** (restatement / restated): ")
    assert "свободный" not in section
    assert glossary.section("Nothing from the glossary.") == ""


def test_a_language_without_a_glossary_file_has_none(tmp_path):
    assert load_glossary("Russian", tmp_path) is None


# ---- section by section -------------------------------------------------------

REPORT = """\
# Stock Autopsy: Coca Cola Co

> Not investment advice.

## Verdict: Weak case: the evidence does not support the investment thesis

The price assumes a yearly return of 5.1% if the base case comes true, against a free cash flow yield of 2.9%.

### In plain words

Revenue was $47.94 billion in FY2025 and the FY2018 figures were restated by $2.44 billion.

## Analyst reports

### Forensic Accountant

The forensic review found the FY2017 and FY2018 restatements and no late filings after 2020.

## Data quality

The 10-Q for the period ending 2026-07-03 (filed 2026-07-29) is not yet in SEC company facts.
"""
RUSSIAN = ("Прежде чем делать выводы, стоит проверить отчётность компании за несколько лет "
           "и сравнить выручку, прибыль и денежный поток с ожиданиями рынка. ") * 2


def russian(source: str, wrong_numbers: bool = False) -> str:
    """A 'translation': the heading marked, Russian words, the source's numbers the Russian way."""
    heading = source.splitlines()[0]
    numbers = [n.text.replace(".", ",") for n in numbers_in(source, english=True)]
    if wrong_numbers:
        numbers = numbers[1:]
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", source)  # dates are checked as dates, copied as written
    return f"{heading} (RU)\n\n{RUSSIAN}{' и '.join(numbers + dates)}\n"


def translator(wrong_numbers_first: int = 0, wrong_in: str = "In plain words"):
    left = {"n": wrong_numbers_first}

    def handler(kwargs):
        source = kwargs["messages"][0]["content"]
        if wrong_in in source.splitlines()[0] and left["n"] > 0:
            left["n"] -= 1
            return text_response(russian(source, wrong_numbers=True))
        return text_response(russian(source))

    return handler


def translation_calls(fake):
    return [r for r in fake.requests if "output_format" not in r]


@pytest.fixture
def fake(fake_claude):
    return fake_claude(handler=None)


def test_a_report_splits_before_each_level_two_and_level_three_heading():
    parts = split_sections(REPORT)
    assert [p.splitlines()[0] for p in parts] == [
        "# Stock Autopsy: Coca Cola Co",
        "## Verdict: Weak case: the evidence does not support the investment thesis",
        "### In plain words",
        "## Analyst reports",
        "### Forensic Accountant",
        "## Data quality",
    ]
    assert "".join(parts) == REPORT


def test_sections_are_translated_in_order_with_the_cheap_model(fake):
    fake.create_handler = translator()
    outcome = translate_document(REPORT, "Russian")
    assert outcome["status"] == "success"
    assert (outcome["untranslated_sections"], outcome["number_rejections"]) == (0, 0)
    headings = [line for line in outcome["text"].splitlines() if line.startswith("#")]
    assert headings[2] == "### In plain words (RU)" and len(headings) == 6
    calls = translation_calls(fake)
    assert len(calls) == 6 and {c["model"] for c in calls} == {"claude-haiku-5-5"}
    assert all(c["output_config"] == {"effort": "low"} for c in calls)
    assert all("Forensic Accountant" in c["system"] for c in calls)  # analyst names stay English


def test_a_section_whose_numbers_changed_is_asked_again(fake):
    fake.create_handler = translator(wrong_numbers_first=1)
    outcome = translate_document(REPORT, "Russian")
    assert (outcome["untranslated_sections"], outcome["number_rejections"]) == (0, 1)
    calls = translation_calls(fake)
    assert len(calls) == 7
    retry = [c for c in calls if c["messages"][0]["content"].startswith("### In plain words")][-1]
    assert RETRY_NOTE.format(language="Russian") in retry["system"]
    assert retry["output_config"] == {"effort": "medium"}


def test_a_section_whose_numbers_change_twice_stays_in_english(fake):
    fake.create_handler = translator(wrong_numbers_first=2)
    outcome = translate_document(REPORT, "Russian")
    assert (outcome["untranslated_sections"], outcome["number_rejections"]) == (1, 2)
    assert UNTRANSLATED_NOTE + "### In plain words\n\nRevenue was $47.94 billion" in outcome["text"]


def test_glossary_terms_go_only_with_the_sections_that_use_them_and_are_appended(fake):
    fake.create_handler = translator()
    glossary = load_glossary("Russian", TEST_GLOSSARIES)
    outcome = translate_document(REPORT, "Russian", glossary)
    by_heading = {c["messages"][0]["content"].splitlines()[0]: c["system"] for c in translation_calls(fake)}
    verdict = "## Verdict: Weak case: the evidence does not support the investment thesis"
    assert "free cash flow / FCF → свободный денежный поток (FCF)" in by_heading[verdict]
    assert "пересчёт отчётности" in by_heading["### Forensic Accountant"]
    assert "свободный денежный поток" not in by_heading["### Forensic Accountant"]
    assert "пересчёт" not in by_heading["## Data quality"]
    assert outcome["text"].rstrip().endswith(
        "- **пересчёт отчётности** (restatement / restated): Компания исправляет ранее опубликованные цифры."
    )
    assert "## Словарь" in outcome["text"] and "going concern" not in outcome["text"]


def test_an_analyst_name_heading_is_not_a_heading_left_in_english():
    assert not heading_untranslated("### Forensic Accountant\n\nText.", "### Forensic Accountant\n\nТекст.")
    assert heading_untranslated("### In plain words\n\nText.", "### In plain words\n\nТекст.")


def test_one_failed_section_fails_the_whole_translation(fake):
    def fails_on_data_quality(kwargs):
        if kwargs["messages"][0]["content"].startswith("## Data quality"):
            raise ConnectionError("Connection error.")
        return text_response(russian(kwargs["messages"][0]["content"]))

    fake.create_handler = fails_on_data_quality
    outcome = translate_document(REPORT, "Russian")
    assert outcome["status"] == "error" and "Connection error" in outcome["error"]


def test_a_truncated_answer_is_an_error_not_half_a_section(fake):
    fake.create_handler = lambda kwargs: text_response("Половина", stop_reason="max_tokens")
    outcome = translate_document("## Data quality\n\nText.\n", "Russian")
    assert outcome["status"] == "error" and "max_tokens" in outcome["error"]


def test_untranslated_or_wrong_language_text_is_recognised():
    english = "Every analyst agreed that the free cash flow is the deciding question here. " * 4
    assert looks_untranslated(english, english)
    assert not looks_untranslated(english, RUSSIAN)
    assert wrong_language(english, "Russian")
    assert wrong_language(RUSSIAN, "Russian") is None


# ---- files and the command line -----------------------------------------------


def run_folder(tmp_path) -> Path:
    run_dir = tmp_path / "KO_2026-10-17_090436"
    run_dir.mkdir()
    (run_dir / "report.md").write_text(REPORT, encoding="utf-8")
    return run_dir


def test_the_translation_is_written_next_to_the_report_and_reused(fake, tmp_path):
    fake.create_handler = translator()
    run_dir = run_folder(tmp_path)
    outcome = translate_report(run_dir, "Russian", TEST_GLOSSARIES)
    target = run_dir / "report.ru.md"
    assert outcome["path"] == target == translated_path(run_dir, "Russian")
    text = target.read_text(encoding="utf-8")
    assert text.startswith(MACHINE_TRANSLATION_NOTE.format(language="Russian", original="report.md"))
    assert "## Словарь" in text
    assert (run_dir / "report.md").read_text(encoding="utf-8") == REPORT
    calls = len(translation_calls(fake))
    again = translate_report(run_dir, "Russian", TEST_GLOSSARIES)
    assert again["reused"] is True and len(translation_calls(fake)) == calls


def test_a_failed_translation_writes_no_file(fake, tmp_path):
    fake.create_handler = lambda kwargs: text_response("", stop_reason="refusal")
    run_dir = run_folder(tmp_path)
    assert translate_report(run_dir, "Russian", TEST_GLOSSARIES)["status"] == "error"
    assert not (run_dir / "report.ru.md").exists()


def test_the_cli_translates_a_saved_run(fake, tmp_path, monkeypatch):
    import main
    import translate.__main__ as cli
    from translate import glossary as glossary_module

    monkeypatch.setattr(glossary_module, "GLOSSARY_DIR", TEST_GLOSSARIES)
    monkeypatch.setattr(main, "setup_logging", lambda stamp: tmp_path / "log")
    fake.create_handler = translator()
    run_dir = run_folder(tmp_path)
    assert cli.main([str(run_dir), "--language", "ru"]) == 0
    assert (run_dir / "report.ru.md").exists()
    with pytest.raises(SystemExit):
        cli.main([str(run_dir), "--language", "Klingon"])


def test_languages_are_named_by_their_english_name_or_code():
    assert LANGUAGES[0][0] == "Russian"
    assert language_name("RU") == language_name(" russian ") == "Russian"
    assert language_name("Chinese") is None


def test_a_bracketed_note_at_the_end_of_the_english_field_is_not_matched():
    glossary = parse_glossary(
        "# Словарь\n\n| English | Термин | Пояснение |\n|---|---|---|\n"
        "| strong / weak (analyst verdicts) | сильно / слабо | Вердикты аналитиков. |\n"
    )
    assert glossary.entries[0].variants == ("strong", "weak")
    assert glossary.used_in("The Forensic verdict was weak.")


def test_the_russian_glossary_is_complete_and_titled():
    glossary = load_glossary("Russian")
    assert glossary.title == "Словарь" and len(glossary.entries) >= 50
    assert all(len(e.explanation) > 20 for e in glossary.entries)


# Structure: the two defects of the first real translations (2026-10-17).

TABLE_SECTION = (
    "### Valuation Analyst (assumptions)\n\n| Assumption | Reasoning |\n|---|---|\n"
    "| Revenue growth | Base growth of 4% sits above the 3-year CAGR of 3.69%. |\n"
)


def test_comments_and_a_repeated_heading_are_rejected():
    comment = "Заголовок остаётся на английском. Ошибка выше: вот перевод:"
    answer = f"### Valuation Analyst (assumptions)\n\n{comment}\n\n" + fake_russian(TABLE_SECTION)
    assert section_problem(TABLE_SECTION, answer, "Russian").startswith("structure changed: headings 1 -> 2")


def test_a_stub_table_before_the_real_one_is_rejected():
    stub = "| Оценщик | Утверждение |\n|---|---|\n| Valuation Analyst | Базовый сценарий... |\n\n"
    answer = fake_russian(TABLE_SECTION).replace("| текст", stub + "| текст", 1)
    assert "table rows 3 -> 6" in section_problem(TABLE_SECTION, answer, "Russian")


def test_a_faithful_translation_keeps_the_structure():
    assert structure_changed(TABLE_SECTION, fake_russian(TABLE_SECTION)) is None
    assert section_problem(TABLE_SECTION, fake_russian(TABLE_SECTION), "Russian") is None
