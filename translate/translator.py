"""
A translated copy of a finished report, as a reading aid (decision D8, M13).

The analysis always runs in English and report.md stays the source of truth: the
translation is a separate step over a saved run folder, asked for on a finished
result, so it can never change a verdict. Ported from Startup Autopsy's translator
(one section at a time, checks for text left in English, in another language or
with an English heading, one stricter retry, the English section kept and marked
when the retry fails too), with two additions for a report full of numbers and
financial terms:

- a number check per section (translate/numbers.py): a section whose numbers do not
  come back with the same value and scale is asked again, then kept in English;
- a glossary per language (translate/glossary.py): the terms of a section go to the
  translator with it, and the terms of the report are appended as one section.
"""

import logging
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import MAX_TOKENS, TRANSLATION_EFFORT, TRANSLATION_MODEL, TRANSLATION_RETRY_EFFORT
from core.claude_client import get_client
from reporting.wording import EVALUATORS
from translate.glossary import Glossary, load_glossary
from translate.languages import CODES
from translate.numbers import missing_numbers

logger = logging.getLogger(__name__)

REPORT_FILENAME = "report.md"

TRANSLATION_PROMPT = """\
Translate the Markdown text below, a part of a stock analysis report, into {language}.
Translate all of its text, including headings, table headers, labels and bold lead-ins;
keep the Markdown markup and structure unchanged (heading levels, lists, tables,
emphasis, links). Do not translate link targets, code spans, hashes, file names, or the
names of companies, products, laws, regulators and filing forms (10-K, 10-Q, 8-K). Keep
the analyst names ({analysts}) in English.
Keep every number with its exact value and scale: you may write the decimal and
thousands separators and the scale words the way {language} writes them (for example
"1.5 billion" may become "1,5 млрд" in Russian), but never round, convert or drop a
number, and write dates and years exactly as in the original. A percentage stays a
percentage and percentage points stay percentage points.
Write the whole translation in {language}. Output only the translated text: no comments,
notes, corrections or placeholders of your own, and every heading, table row and list item
exactly once, as in the original.
"""

GLOSSARY_NOTE = """
Use these {language} terms for the English terms in this text, consistently:
{terms}
"""

# Added to the prompt when a section is asked again after a rejected answer.
RETRY_NOTE = """
Your answer must be written entirely in {language}: every heading, sentence, list
item and table cell, and it must contain every number of the original with the same
value and scale. Text left in English, written in any other language, or a number
changed, rounded or dropped is a wrong answer.
"""

# One part per level-2 or level-3 heading: the analysts' section of a report is
# about 45 KB, too long to translate and check as one answer; its subsections are
# 2-12 KB. Parts are short, run in parallel and are checked one by one.
SECTION_START = re.compile(r"(?m)^(?=#{2,3} )")
SECTION_WORKERS = 4
# A section counts as left untranslated when most of its words come back unchanged.
# Measured in Startup Autopsy on two real Russian translations: translated sections
# keep 4-35% of their words (names, file names, links), an untranslated one 100%.
UNTRANSLATED_SHARE = 0.6
MIN_WORDS_TO_CHECK = 25
UNTRANSLATED_NOTE = "> This section could not be translated; the English original follows.\n\n"

# The overlap check cannot see a section that comes back in a third language; the
# script of the letters tells Russian from Lithuanian, and letters outside a Latin
# alphabet tell one Latin-script language from another (Startup Autopsy).
SCRIPTS = {
    "russian": {"CYRILLIC"}, "ukrainian": {"CYRILLIC"}, "belarusian": {"CYRILLIC"},
    "bulgarian": {"CYRILLIC"}, "greek": {"GREEK"}, "japanese": {"CJK", "HIRAGANA", "KATAKANA"},
    "korean": {"HANGUL"}, "arabic": {"ARABIC"}, "hebrew": {"HEBREW"}, "hindi": {"DEVANAGARI"},
}
LATIN_ALPHABETS = {
    "lithuanian": "ąčęėįšųūž",
    "latvian": "āčēģīķļņšūž",
    "estonian": "äõöüšž",
    "polish": "ąćęłńóśźż",
    "german": "äöüß",
    "french": "àâæçéèêëîïôœùûüÿ",
    "spanish": "áéíñóúü",
    "italian": "àèéìíîòóù",
}
MIN_SCRIPT_SHARE = 0.3
FOREIGN_LETTER_SHARE = 0.02
MIN_FOREIGN_LETTERS = 10
HEADING_LEFT = "heading left in English"
NUMBERS_CHANGED = "numbers changed"
# Headings that stay English on purpose: the analysts' names.
KEPT_NAMES = tuple(EVALUATORS.values())

# Put above every translated copy, in English, so a reader of any language sees
# which file is the source of truth.
MACHINE_TRANSLATION_NOTE = (
    "> Machine translation into {language} of the English original ({original}). "
    "Numbers are checked against the original section by section; if the two differ, "
    "the English original is authoritative.\n\n"
)


def system_prompt(language: str, section: str, glossary: Glossary | None, retry: bool) -> str:
    prompt = TRANSLATION_PROMPT.format(language=language, analysts=", ".join(KEPT_NAMES))
    terms = glossary.prompt_lines(section) if glossary else ""
    if terms:
        prompt += GLOSSARY_NOTE.format(language=language, terms=terms)
    if retry:
        prompt += RETRY_NOTE.format(language=language)
    return prompt


def translate_markdown(markdown: str, language: str, glossary: Glossary | None = None,
                       retry: bool = False) -> dict:
    """
    Translate one Markdown text. Never raises. A retry adds RETRY_NOTE and thinks more.

    Returns:
        {"status": "success", "text": str, "model", "input_tokens", "output_tokens", "duration_s"}
        or {"status": "error", "error": str, "model", "duration_s", and tokens when known}
    """
    started = time.monotonic()
    try:
        response = get_client().messages.create(
            model=TRANSLATION_MODEL,
            max_tokens=MAX_TOKENS,
            output_config={"effort": TRANSLATION_RETRY_EFFORT if retry else TRANSLATION_EFFORT},
            system=system_prompt(language, markdown, glossary, retry),
            messages=[{"role": "user", "content": markdown}],
        )
        usage = {
            "model": TRANSLATION_MODEL,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        if response.stop_reason != "end_turn":
            return {"status": "error", "error": f"translation stopped: {response.stop_reason}",
                    "duration_s": time.monotonic() - started, **usage}
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            return {"status": "error", "error": "empty translation",
                    "duration_s": time.monotonic() - started, **usage}
        return {"status": "success", "text": text + "\n",
                "duration_s": time.monotonic() - started, **usage}
    except Exception as e:
        logger.debug("Translation failed", exc_info=True)
        return {"status": "error", "error": f"{type(e).__name__}: {e}",
                "model": TRANSLATION_MODEL, "duration_s": time.monotonic() - started}


def split_sections(markdown: str) -> list[str]:
    """The text before the first level-2 heading, then one part per level-2 or level-3 heading."""
    return [part for part in SECTION_START.split(markdown) if part.strip()]


def _words(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[^\W\d_]{4,}", text)]


def looks_untranslated(source: str, translation: str) -> bool:
    """True when most words of the source come back unchanged (short parts are not judged)."""
    words = _words(source)
    if len(words) < MIN_WORDS_TO_CHECK:
        return False
    kept = set(_words(translation))
    return sum(word in kept for word in words) / len(words) >= UNTRANSLATED_SHARE


def _script(letter: str) -> str:
    """The script a letter belongs to: LATIN, CYRILLIC, CJK, ..."""
    return unicodedata.name(letter, "").split(" ", 1)[0]


def wrong_language(text: str, language: str) -> str | None:
    """Why the text is not in the language, or None (also when it cannot be told)."""
    key = language.strip().lower()
    scripts = SCRIPTS.get(key) or ({"LATIN"} if key in LATIN_ALPHABETS else None)
    letters = [c for c in text if c.isalpha()]
    if not scripts or not letters:
        return None
    if sum(_script(c) in scripts for c in letters) / len(letters) < MIN_SCRIPT_SHARE:
        return "written in another script"
    alphabet = LATIN_ALPHABETS.get(key)
    if alphabet is not None:
        foreign = [
            c for c in letters if not c.isascii() and _script(c) == "LATIN" and c.lower() not in alphabet
        ]
        if len(foreign) >= MIN_FOREIGN_LETTERS and len(foreign) / len(letters) >= FOREIGN_LETTER_SHARE:
            return "letters of another language"
    return None


def _heading(text: str) -> str:
    return text.strip().split("\n", 1)[0].strip()


def heading_untranslated(source: str, translation: str) -> bool:
    """True when a section heading of two or more words comes back unchanged (analyst names may)."""
    heading = _heading(source)
    title = heading.lstrip("#").strip()
    if not re.match(r"#{2,3} ", heading) or len(_words(heading)) < 2 or title.startswith(KEPT_NAMES):
        return False
    return _heading(translation).lower() == heading.lower()


def structure(text: str) -> tuple[int, int, int]:
    """(headings, table rows, list items): what a translation must not add or drop."""
    lines = [line.lstrip() for line in text.splitlines()]
    return (
        sum(line.startswith("#") for line in lines),
        sum(line.startswith("|") for line in lines),
        sum(bool(re.match(r"(?:[-*+]|\d+[.)])\s", line)) for line in lines),
    )


def structure_changed(source: str, translation: str) -> str | None:
    """
    How the Markdown structure differs, or None. Seen on the first real translations
    (2026-10-17): the translator added its own comments and repeated a heading, or put
    a stub table with "..." placeholders before the real one; numbers cannot see that.
    """
    names = ("headings", "table rows", "list items")
    changed = [
        f"{name} {before} -> {after}"
        for name, before, after in zip(names, structure(source), structure(translation), strict=True)
        if before != after
    ]
    return ", ".join(changed) or None


def section_problem(source: str, translation: str, language: str) -> str | None:
    """Why a translated section cannot be used as it is, or None."""
    if looks_untranslated(source, translation):
        return "left in English"
    if len(_words(source)) >= MIN_WORDS_TO_CHECK:
        wrong = wrong_language(translation, language)
        if wrong:
            return f"not in {language}: {wrong}"
    missing = missing_numbers(source, translation)
    if missing:
        return f"{NUMBERS_CHANGED}: {', '.join(missing[:5])}"
    changed = structure_changed(source, translation)
    if changed:
        return f"structure changed: {changed}"
    if heading_untranslated(source, translation):
        return HEADING_LEFT
    return None


def _translate_section(section: str, language: str, glossary: Glossary | None) -> dict:
    """
    One section; asked again once, with a stricter prompt, if the answer is rejected.
    Never raises. A translation whose only fault is an English heading beats the
    English original; anything worse keeps the English section, marked.
    """
    first = translate_markdown(section, language, glossary)
    if first["status"] != "success":
        return {**first, "calls": 1, "untranslated": False, "number_rejections": 0}
    first_problem = section_problem(section, first["text"], language)
    if first_problem is None:
        return {**first, "calls": 1, "untranslated": False, "number_rejections": 0}
    heading = _heading(section)
    _log_rejected(heading, first_problem, first["text"])
    second = translate_markdown(section, language, glossary, retry=True)
    billed = {key: first.get(key, 0) + second.get(key, 0) for key in ("input_tokens", "output_tokens")}
    attempts = [(first, first_problem)]
    if second["status"] == "success":
        second_problem = section_problem(section, second["text"], language)
        if second_problem is None:
            return {**second, **billed, "calls": 2, "untranslated": False,
                    "number_rejections": _number_rejections(attempts)}
        _log_rejected(heading, second_problem, second["text"])
        attempts.append((second, second_problem))
    rejections = _number_rejections(attempts)
    for attempt, problem in attempts:
        if problem == HEADING_LEFT:
            logger.warning(f"[Translation] '{heading}': the heading stayed English after a retry")
            return {**attempt, **billed, "calls": 2, "untranslated": False, "number_rejections": rejections}
    logger.warning(f"[Translation] '{heading}' kept in English after a retry ({attempts[-1][1]})")
    return {"status": "success", "text": UNTRANSLATED_NOTE + section, "model": TRANSLATION_MODEL,
            **billed, "calls": 2, "untranslated": True, "number_rejections": rejections}


def _number_rejections(attempts: list[tuple[dict, str]]) -> int:
    return sum(problem.startswith(NUMBERS_CHANGED) for _, problem in attempts)


def _log_rejected(heading: str, problem: str, text: str) -> None:
    """Rejected answers go to the log: the problem at INFO, the start of the text at DEBUG."""
    logger.info(f"[Translation] '{heading}' rejected: {problem}")
    logger.debug(f"[Translation] '{heading}' rejected answer starts: {text[:300]!r}")


def translate_document(markdown: str, language: str, glossary: Glossary | None = None) -> dict:
    """
    Translate a report section by section, put it back together and append the
    glossary section. Never raises.

    Returns the fields of translate_markdown with tokens summed over every call, plus
    "calls", "untranslated_sections" (kept in English after a retry) and
    "number_rejections" (answers rejected because a number changed). A failed call
    fails the whole document: a translation with holes is not offered.
    """
    started = time.monotonic()
    sections = split_sections(markdown)
    with ThreadPoolExecutor(max_workers=max(1, min(SECTION_WORKERS, len(sections)))) as pool:
        outcomes = list(pool.map(lambda section: _translate_section(section, language, glossary), sections))
    billed = {
        "model": TRANSLATION_MODEL,
        "input_tokens": sum(o.get("input_tokens", 0) for o in outcomes),
        "output_tokens": sum(o.get("output_tokens", 0) for o in outcomes),
        "calls": sum(o.get("calls", 0) for o in outcomes),
        "duration_s": time.monotonic() - started,
    }
    failed = [o for o in outcomes if o["status"] != "success"]
    if failed:
        return {"status": "error", "error": failed[0]["error"], **billed}
    text = "\n\n".join(o["text"].strip() for o in outcomes) + "\n"
    appendix = glossary.section(markdown) if glossary else ""
    if appendix:
        text += "\n" + appendix
    return {
        "status": "success",
        "text": text,
        "untranslated_sections": sum(o["untranslated"] for o in outcomes),
        "number_rejections": sum(o["number_rejections"] for o in outcomes),
        "sections": len(sections),
        **billed,
    }


def translated_path(run_dir: Path, language: str) -> Path:
    """results/<run>/report.md + 'Russian' -> results/<run>/report.ru.md."""
    return run_dir / f"report.{CODES[language]}.md"


def translate_report(run_dir: Path, language: str, glossary_dir: Path | None = None) -> dict:
    """
    Write report.<code>.md next to report.md of a finished run. Never raises for a
    failed translation (the outcome says why; nothing is written).

    An existing translation is kept and not paid for again: the outcome then has
    "reused": True and no tokens. `language` must be one of translate.languages.
    """
    target = translated_path(run_dir, language)
    if target.exists():
        logger.info(f"[Translation] {target.name} exists; not translated again")
        return {"status": "success", "reused": True, "path": target, "model": TRANSLATION_MODEL,
                "input_tokens": 0, "output_tokens": 0, "calls": 0, "duration_s": 0.0}
    source = run_dir / REPORT_FILENAME
    glossary = load_glossary(language) if glossary_dir is None else load_glossary(language, glossary_dir)
    logger.info(f"[Translation] {source} into {language} started"
                f"{'' if glossary else ' (no glossary for this language)'}")
    outcome = translate_document(source.read_text(encoding="utf-8"), language, glossary)
    if outcome["status"] == "success":
        note = MACHINE_TRANSLATION_NOTE.format(language=language, original=REPORT_FILENAME)
        target.write_text(note + outcome["text"], encoding="utf-8")
        outcome["path"] = target
    outcome["reused"] = False
    return outcome
