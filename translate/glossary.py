"""
Glossaries for translated reports: one Markdown file per language in
translate/glossaries/<language>.md, version-controlled and reviewed by a person.

    # Словарь                                  <- the title of the appended section

    | English | Русский термин | Пояснение |  <- a header row (skipped)
    |---|---|---|
    | free cash flow / FCF | свободный денежный поток (FCF) | One or two sentences. |

Each row has three fields: the English term as reports write it (variants separated
by " / "), the term the translator must use, and an explanation. Other lines
(subheadings, notes for reviewers) are ignored. A glossary is used twice: the
entries whose English term occurs in a section go to the translator with that
section, and the entries that occur anywhere in the report are appended to the
translation as one section (static text, no tokens). A language without a file
simply has no glossary.
"""

import re
from dataclasses import dataclass
from pathlib import Path

GLOSSARY_DIR = Path(__file__).resolve().parent / "glossaries"
_SEPARATOR_CELL = re.compile(r"^:?-{2,}:?$")


class GlossaryError(ValueError):
    """A glossary file that does not have the expected shape."""


@dataclass(frozen=True)
class Entry:
    variants: tuple[str, ...]
    term: str
    explanation: str

    @property
    def english(self) -> str:
        return " / ".join(self.variants)

    def occurs_in(self, text: str) -> bool:
        """Any variant as a whole word, ignoring case; an English plural counts ("restatements")."""
        return any(
            re.search(rf"(?<!\w){re.escape(variant)}(?:e?s)?(?!\w)", text, re.IGNORECASE)
            for variant in self.variants
        )


@dataclass(frozen=True)
class Glossary:
    title: str
    entries: tuple[Entry, ...]

    def used_in(self, text: str) -> list[Entry]:
        return [entry for entry in self.entries if entry.occurs_in(text)]

    def prompt_lines(self, text: str) -> str:
        """The terms the translator must use for this text, or an empty string."""
        return "\n".join(f"- {entry.english} → {entry.term}" for entry in self.used_in(text))

    def section(self, report: str) -> str:
        """The glossary section for a translated report: only the terms the report uses."""
        used = self.used_in(report)
        if not used:
            return ""
        lines = [f"- **{entry.term}** ({entry.english}): {entry.explanation}" for entry in used]
        return f"## {self.title}\n\n" + "\n".join(lines) + "\n"


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_glossary(text: str, source: str = "glossary") -> Glossary:
    """
    Raises:
        GlossaryError: no title, a row without all three fields, or no entries
    """
    lines = text.splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), "")
    if not title:
        raise GlossaryError(f"{source}: no '# ' title line (the title of the appended section)")
    entries = []
    for number, line in enumerate(lines, start=1):
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if all(_SEPARATOR_CELL.match(cell) for cell in cells):
            continue
        following = lines[number] if number < len(lines) else ""
        if following.lstrip().startswith("|") and all(_SEPARATOR_CELL.match(c) for c in _cells(following)):
            continue  # a header row
        if len(cells) != 3 or not all(cells):
            raise GlossaryError(
                f"{source}, line {number}: a row needs English, term and explanation: {line!r}"
            )
        variants = tuple(v.strip() for v in cells[0].split(" / ") if v.strip())
        entries.append(Entry(variants, cells[1], cells[2]))
    if not entries:
        raise GlossaryError(f"{source}: no entries")
    return Glossary(title, tuple(entries))


def glossary_path(language: str, directory: Path = GLOSSARY_DIR) -> Path:
    return directory / f"{language.strip().lower().replace(' ', '_')}.md"


def load_glossary(language: str, directory: Path = GLOSSARY_DIR) -> Glossary | None:
    """The glossary for a language, or None when it has none."""
    path = glossary_path(language, directory)
    if not path.exists():
        return None
    return parse_glossary(path.read_text(encoding="utf-8"), source=str(path))
