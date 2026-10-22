"""
Glossaries for translated reports: one Markdown file per language in
translate/glossaries/<language>.md, version-controlled and reviewed by a person.

    # Словарь                                  <- the title of the appended section

    | English | Русский термин | Пояснение |  <- a header row (skipped)
    |---|---|---|
    | free cash flow / FCF | свободный денежный поток (FCF) | One or two sentences. |

Each row has three fields: the English term as reports write it (variants separated
by " / "; a note in brackets at its end is for reviewers and is not matched), the term
the translator must use, and an explanation. Other lines
(subheadings, notes for reviewers) are ignored. A glossary is used twice: the
entries whose English term occurs in a section go to the translator with that
section, and the entries that occur anywhere in the report are appended to the
translation as a collapsed <details> block (static text, never translated by the model,
no tokens). A language without a file simply has no glossary.

glossaries/english.md is the glossary of report.md itself: its block ends every English
report (only the terms the report uses). The translator takes that block off before
translating and puts the target language's block in its place; with no file for the
target language it keeps the English block and says so in one line (since 2026-10-22).
"""

import re
from dataclasses import dataclass
from pathlib import Path

GLOSSARY_DIR = Path(__file__).resolve().parent / "glossaries"
_SEPARATOR_CELL = re.compile(r"^:?-{2,}:?$")
_NOTE = re.compile(r"\s*\([^)]*\)\s*$")


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

    def section(self, report: str, english: bool = False) -> str:
        """
        The glossary at the end of a report: only the terms the report uses, as a collapsed
        <details> block (empty when it uses none). A translated glossary names the English
        term after its own; the English one has no need to.
        """
        used = self.used_in(report)
        if not used:
            return ""
        lines = [f"- **{entry.term}**{'' if english else f' ({entry.english})'}: {entry.explanation}"
                 for entry in used]
        return f"<details><summary>{self.title}</summary>\n\n" + "\n".join(lines) + "\n\n</details>\n"


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
        english = _NOTE.sub("", cells[0])  # "strong / weak (analyst verdicts)": the note is for reviewers
        variants = tuple(v.strip() for v in english.split(" / ") if v.strip())
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


# report.md ends with the English glossary (glossaries/english.md) in this block.
ENGLISH = "English"
_ENGLISH_BLOCK = re.compile(r"\n*<details><summary>Glossary</summary>\n.*?\n</details>\n*\Z", re.DOTALL)


def english_section(report: str, directory: Path = GLOSSARY_DIR) -> str:
    """The English glossary block for a report (the terms it uses), or an empty string."""
    glossary = load_glossary(ENGLISH, directory)
    return glossary.section(report, english=True) if glossary else ""


def split_glossary(report: str) -> tuple[str, str]:
    """A report without its trailing English glossary block, and that block ("" if none)."""
    match = _ENGLISH_BLOCK.search(report)
    if match is None:
        return report, ""
    return report[:match.start()].rstrip("\n") + "\n", match.group(0).strip("\n") + "\n"
