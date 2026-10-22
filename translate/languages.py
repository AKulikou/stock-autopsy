"""
Languages offered for a translated copy of the report: the same list as Startup
Autopsy's web page (no Chinese), Lithuanian first as the default.

The page shows each language by its own name; the English name goes to the
translator (prompt, glossary file) and the code into the file name
(report.ru.md). English is not offered: the original is English.

Each language also says how it writes numbers. Every language offered writes a
decimal comma, so the English thousands form "11,080" reads there as 11.08: code
writes such numbers "11 080" (a no-break space) in a translated copy.
"""

from typing import NamedTuple


class NumberFormat(NamedTuple):
    decimal: str    # "17.79" / "17,79"
    thousands: str  # "11,080" / "11 080"


ENGLISH_NUMBERS = NumberFormat(".", ",")
DECIMAL_COMMA = NumberFormat(",", " ")  # a no-break space


class Language(NamedTuple):
    name: str               # English name, for the translator
    native: str             # the language's own name, for the page
    code: str               # file code: report.<code>.md
    numbers: NumberFormat


LANGUAGES: tuple[Language, ...] = (
    Language("Lithuanian", "Lietuvių", "lt", DECIMAL_COMMA),
    Language("Russian", "Русский", "ru", DECIMAL_COMMA),
    Language("German", "Deutsch", "de", DECIMAL_COMMA),
    Language("Estonian", "Eesti", "et", DECIMAL_COMMA),
    Language("Spanish", "Español", "es", DECIMAL_COMMA),
    Language("French", "Français", "fr", DECIMAL_COMMA),
    Language("Italian", "Italiano", "it", DECIMAL_COMMA),
    Language("Latvian", "Latviešu", "lv", DECIMAL_COMMA),
    Language("Polish", "Polski", "pl", DECIMAL_COMMA),
    Language("Ukrainian", "Українська", "uk", DECIMAL_COMMA),
)
DEFAULT_LANGUAGE = LANGUAGES[0][0]
CODES = {lang.name: lang.code for lang in LANGUAGES}
NATIVE_NAMES = {lang.name: lang.native for lang in LANGUAGES}


def language_name(value: str) -> str | None:
    """The English name of an offered language, from its name or code in any case; else None."""
    wanted = value.strip().lower()
    for lang in LANGUAGES:
        if wanted in (lang.name.lower(), lang.code):
            return lang.name
    return None


def number_format(language: str) -> NumberFormat:
    """How a language writes numbers; English (the original) and any language not offered: the English way."""
    return next((lang.numbers for lang in LANGUAGES if lang.name == language), ENGLISH_NUMBERS)


def languages_for_page() -> list[dict]:
    return [{"name": lang.name, "label": lang.native} for lang in LANGUAGES]
