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
from translate.glossary import Glossary, load_glossary, split_glossary
from translate.languages import CODES
from translate.numbers import missing_numbers

logger = logging.getLogger(__name__)

REPORT_FILENAME = "report.md"

TRANSLATION_PROMPT = """\
Translate the Markdown text below, a part of a stock analysis report, into {language}.
Translate all of its text, including headings, table headers, labels and bold lead-ins;
keep the Markdown markup and structure unchanged (heading levels, lists, tables,
emphasis, links). Do not translate link targets, code spans, hashes, file names, or the
names of companies, products, laws, regulators and filing forms (10-K, 10-Q, 8-K).
Translate the analyst names ({analysts}) into {language}, with the names the term list
gives when it gives them, the same name every time; add the English name in brackets
only in the heading of that analyst's own section, nowhere else.
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
# Put above a section kept in English, with the reason in words, so a reader of the
# copy (and the page, which reads it back with kept_sections()) sees why.
# The same sentence stands in the copy, on the page and in the CLI (E5): kept_sentence().
UNTRANSLATED_NOTE = "> {sentence} The English original follows.\n\n"
# Copies made before 2026-10-22 say "Kept in English: <reason>." instead; both are read back.
_KEPT = re.compile(
    r"(?m)^> (?:Kept in English|.+? stayed in English): (?P<reason>.+)\. The English original follows\.\n\n"
    r"#{2,3} (?P<heading>.+)$"
)


def kept_sentence(heading: str, reason: str) -> str:
    """'Forensic Accountant stayed in English: twice the translator returned the English text.'"""
    return f"{heading} stayed in English: {reason}."

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
# The analysts' names, listed for the translator; a glossary gives each one a
# translated name (owner's review of the first Russian copies, 2026-10-21).
ANALYST_NAMES = tuple(EVALUATORS.values())

# Put above the English glossary block in a copy whose language has no glossary file yet.
NO_GLOSSARY_NOTE = "> There is no {language} glossary yet; the English glossary follows.\n\n"

# Put above every translated copy, in English, so a reader of any language sees
# which file is the source of truth.
MACHINE_TRANSLATION_NOTE = (
    "> Machine translation into {language} of the English original ({original}). "
    "Numbers are checked against the original section by section; if the two differ, "
    "the English original is authoritative.\n\n"
)


def system_prompt(language: str, section: str, glossary: Glossary | None, retry: bool,
                  detail: str = "") -> str:
    prompt = TRANSLATION_PROMPT.format(language=language, analysts=", ".join(ANALYST_NAMES))
    terms = glossary.prompt_lines(section) if glossary else ""
    if terms:
        prompt += GLOSSARY_NOTE.format(language=language, terms=terms)
    if retry:
        prompt += RETRY_NOTE.format(language=language)
    if detail:
        prompt += detail + "\n"
    return prompt


def translate_markdown(markdown: str, language: str, glossary: Glossary | None = None,
                       retry: bool = False, detail: str = "") -> dict:
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
            system=system_prompt(language, markdown, glossary, retry, detail),
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


_WORD = re.compile(r"[^\W\d_]+")
_ALPHABETS = {"LATIN", "CYRILLIC", "GREEK"}


def mixed_script_words(text: str, language: str) -> list[str]:
    """
    Words a translation cannot hold: one word of two alphabets ("Vердикt", "Komitето" in a
    Lithuanian copy of 2026-10-22), or a Cyrillic or Greek word in a Latin-script language.
    The share checks of wrong_language() miss them: three words in a long section.
    """
    latin_target = language.strip().lower() in LATIN_ALPHABETS
    found = []
    for word in _WORD.findall(text):
        scripts = {_script(c) for c in word} & _ALPHABETS
        if len(scripts) > 1 or (latin_target and scripts - {"LATIN"}):
            found.append(word)
    return found


# Cyrillic letters that look like Latin ones. A Latin-script translation that holds one inside a
# Latin word ("paketе" with a Cyrillic "е", Lithuanian copy of 2026-10-22, rejected twice) means
# the Latin letter: code puts it right instead of paying for a retry that repeats it.
LOOK_ALIKES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k", "і": "i", "ј": "j",
    "ѕ": "s", "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "Х": "X", "У": "Y", "І": "I", "Ј": "J", "Ѕ": "S",
})


def fix_look_alikes(text: str, language: str) -> str:
    """
    In a Latin-script language, a word of Latin letters with a few Cyrillic look-alikes gets
    the Latin letters. A word that is mostly Cyrillic, or holds a Cyrillic letter with no
    Latin twin ("Vердикt"), is left as it is for the check to reject.
    """
    if language.strip().lower() not in LATIN_ALPHABETS:
        return text

    def fix(match: re.Match) -> str:
        word = match.group(0)
        cyrillic = [c for c in word if _script(c) == "CYRILLIC"]
        latin = [c for c in word if _script(c) == "LATIN"]
        if not cyrillic or len(latin) < len(cyrillic):
            return word
        fixed = word.translate(LOOK_ALIKES)
        return fixed if all(_script(c) != "CYRILLIC" for c in fixed) else word

    return _WORD.sub(fix, text)


def _mixed_words(problem: str) -> list[str]:
    """The words of a "words mixing alphabets (a, b)" problem, each once, ignoring case."""
    match = re.search(r"words mixing alphabets \((.*)\)$", problem)
    words, seen = [], set()
    for word in (match.group(1).split(", ") if match else []):
        if word.casefold() not in seen:
            seen.add(word.casefold())
            words.append(word)
    return words


def retry_detail(problem: str) -> str:
    """What exactly was wrong, for the retry: each mixed word and its letters from the other alphabet."""
    lines = []
    for word in _mixed_words(problem):
        scripts = [_script(c) for c in word if c.isalpha()]
        main = max(set(scripts), key=scripts.count)
        foreign = ", ".join(f"{c} ({_script(c).title()}, U+{ord(c):04X})"
                            for c in dict.fromkeys(word) if c.isalpha() and _script(c) != main)
        lines.append(f'The word "{word}" mixes alphabets: {foreign}.')
    if not lines:
        return ""
    return "In your previous answer: " + " ".join(lines) + " Write every word in one alphabet only."


def _heading(text: str) -> str:
    return text.strip().split("\n", 1)[0].strip()


def heading_untranslated(source: str, translation: str) -> bool:
    """True when a section heading of two or more words comes back unchanged (analyst names too)."""
    heading = _heading(source)
    if not re.match(r"#{2,3} ", heading) or len(_words(heading)) < 2:
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
    mixed = list(dict.fromkeys(mixed_script_words(translation, language)))
    if mixed:
        return f"not in {language}: words mixing alphabets ({', '.join(mixed[:3])})"
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
    if first["status"] == "success":
        first["text"] = fix_look_alikes(first["text"], language)
    if first["status"] != "success":
        return {**first, "calls": 1, "untranslated": False, "number_rejections": 0}
    first_problem = section_problem(section, first["text"], language)
    if first_problem is None:
        return {**first, "calls": 1, "untranslated": False, "number_rejections": 0}
    heading = _heading(section)
    _log_rejected(heading, first_problem, first["text"])
    second = translate_markdown(section, language, glossary, retry=True, detail=retry_detail(first_problem))
    if second["status"] == "success":
        second["text"] = fix_look_alikes(second["text"], language)
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
    reason = kept_reason([problem for _, problem in attempts])
    name = heading.lstrip("#").strip()
    logger.warning(f"[Translation] {kept_sentence(name, reason)}")
    note = UNTRANSLATED_NOTE.format(sentence=kept_sentence(name, reason))
    return {"status": "success", "text": note + section,
            "model": TRANSLATION_MODEL, **billed, "calls": 2, "untranslated": True,
            "kept": {"heading": name, "reason": reason},
            "number_rejections": rejections}


def _problem_words(problem: str) -> tuple[str, list[str]]:
    """A rejected answer's problem as a short phrase and its details (numbers, words)."""
    head, _, rest = problem.partition(": ")
    if problem == "left in English":
        return "the translator returned the English text", []
    if problem == HEADING_LEFT:
        return "the heading stayed in English", []
    if problem.startswith(NUMBERS_CHANGED):
        return "a number came back changed", [x for x in rest.split(", ") if x]
    if problem.startswith("structure changed"):
        return "headings, table rows or list items came back changed", [rest] if rest else []
    if "words mixing alphabets" in problem:
        return "the translation mixed Latin and Cyrillic letters", _mixed_words(problem)
    language = head.removeprefix("not in ")
    return f"the translation was not in {language}", [rest] if rest else []


def kept_reason(problems: list[str]) -> str:
    """
    Why a section stayed in English, in one short phrase: the reason once, "twice" when both
    answers failed the same way, details in one pair of brackets, each word once (E5).
    """
    def phrase(text: str, details: list[str]) -> str:
        unique = list({d.casefold(): d for d in reversed(details)}.values())[::-1]
        return f"{text} ({', '.join(unique)})" if unique else text

    parts = [_problem_words(problem) for problem in problems]
    if len(parts) == 2 and parts[0][0] == parts[1][0]:
        return "twice " + phrase(parts[0][0], parts[0][1] + parts[1][1])
    return ", then ".join(phrase(text, details) for text, details in parts)


def analyst_heading(source: str, translation: str, glossary: Glossary | None) -> str:
    """
    The heading of an analyst's own section, set by code from the glossary: "### <name>
    (<English name>)". The translator does not always use the term list there (Coca-Cola,
    2026-10-21: "Криминалистический аналитик" for the glossary's "Аналитик-криминалист").
    """
    heading = _heading(source)
    title = heading.lstrip("#").strip()
    if glossary is None or title not in ANALYST_NAMES:
        return translation
    term = next((e.term for e in glossary.entries if title in e.variants), None)
    if term is None:
        return translation
    first, _, rest = translation.lstrip().partition("\n")
    if not first.startswith("#"):
        return translation
    english = f"[{title}]" if "(" in title else f"({title})"  # no "(... (assumptions))"
    return f"{heading.split(' ', 1)[0]} {term} {english}\n{rest}"


def report_title(source: str, translation: str) -> str:
    """
    The report's level-1 title ("# Stock Autopsy: Coca Cola Co") is the product's and the
    company's name, which are not translated; the translator once wrote "Разбор акций"
    (2026-10-21), so code puts the original back.
    """
    title = _heading(source)
    first, _, rest = translation.lstrip().partition("\n")
    if not re.match(r"# ", title) or not re.match(r"# ", first):
        return translation
    return f"{title}\n{rest}"


def kept_sections(markdown: str) -> list[dict]:
    """The sections a translated copy kept in English, with the reason: [{heading, reason}]."""
    return [{"heading": m["heading"].strip(), "reason": m["reason"]} for m in _KEPT.finditer(markdown)]


def _number_rejections(attempts: list[tuple[dict, str]]) -> int:
    return sum(problem.startswith(NUMBERS_CHANGED) for _, problem in attempts)


def _log_rejected(heading: str, problem: str, text: str) -> None:
    """Rejected answers go to the log: the problem at INFO, the start of the text at DEBUG."""
    logger.info(f"[Translation] '{heading}' rejected: {problem}")
    logger.debug(f"[Translation] '{heading}' rejected answer starts: {text[:300]!r}")


def translate_document(markdown: str, language: str, glossary: Glossary | None = None) -> dict:
    """
    Translate a report section by section, put it back together and append the
    target language's glossary block in place of the English one (the English block
    and a note when the language has no glossary file). Never raises.

    Returns the fields of translate_markdown with tokens summed over every call, plus
    "calls", "untranslated_sections" (kept in English after a retry) and
    "number_rejections" (answers rejected because a number changed). A failed call
    fails the whole document: a translation with holes is not offered.
    """
    started = time.monotonic()
    # The English glossary is not sent to the model: code puts the target language's in its place.
    markdown, english_glossary = split_glossary(markdown)
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
    texts = [o["text"] if o["untranslated"] else analyst_heading(section, o["text"], glossary)
             for section, o in zip(sections, outcomes, strict=True)]
    texts[0] = report_title(sections[0], texts[0])
    text = "\n\n".join(t.strip() for t in texts) + "\n"
    if glossary:
        appendix = glossary.section(markdown)
    else:
        appendix = NO_GLOSSARY_NOTE.format(language=language) + english_glossary if english_glossary else ""
    if appendix:
        text += "\n" + appendix
    return {
        "status": "success",
        "text": text,
        "untranslated_sections": sum(o["untranslated"] for o in outcomes),
        "kept_sections": [o["kept"] for o in outcomes if o["untranslated"]],
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
