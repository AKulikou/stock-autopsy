"""
Languages offered for a translated copy of the report: the same list as Startup
Autopsy's web page (decision D8: no Chinese), Russian first as the default.

The page shows each language by its own name; the English name goes to the
translator (prompt, glossary file) and the code into the file name
(report.ru.md). English is not offered: the original is English.
"""

# (English name for the translator, the language's own name for the page, file code)
LANGUAGES: tuple[tuple[str, str, str], ...] = (
    ("Russian", "Русский", "ru"),
    ("German", "Deutsch", "de"),
    ("Estonian", "Eesti", "et"),
    ("Spanish", "Español", "es"),
    ("French", "Français", "fr"),
    ("Italian", "Italiano", "it"),
    ("Latvian", "Latviešu", "lv"),
    ("Lithuanian", "Lietuvių", "lt"),
    ("Polish", "Polski", "pl"),
    ("Ukrainian", "Українська", "uk"),
)
DEFAULT_LANGUAGE = LANGUAGES[0][0]
CODES = {name: code for name, _, code in LANGUAGES}
NATIVE_NAMES = {name: native for name, native, _ in LANGUAGES}


def language_name(value: str) -> str | None:
    """The English name of an offered language, from its name or code in any case; else None."""
    wanted = value.strip().lower()
    for name, _, code in LANGUAGES:
        if wanted in (name.lower(), code):
            return name
    return None


def languages_for_page() -> list[dict]:
    return [{"name": name, "label": native} for name, native, _ in LANGUAGES]
