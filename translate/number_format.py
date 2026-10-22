"""
Numbers of a translated copy in the target language's format (translate.languages).

The English original writes "11,080" and "17.79". In a language with a decimal comma
"11,080" reads as 11.08, and the number check cannot see it: it accepts both readings
(Russian and Lithuanian copies of 2026-10-22 kept "11,080" and "10,797" in the cost
table). Both rules below take the value from the English section, never from the
translator, so no value is guessed:

- localize_tables(): a table cell that holds nothing but a number in the English
  section (the cost table, the valuation tables, the restated values: tables code
  builds from numbers) is written by code in the target format, whatever the
  translator put there;
- english_thousands() finds a number the English section writes in the thousands
  form ("10,803") that the translation still writes that way; the section is asked
  once more, and rewrite_english_thousands() puts what is still left into the target
  format.

English, and a language that writes a decimal point, is left unchanged.
"""

import re
from collections.abc import Callable

from translate.languages import NumberFormat, number_format

# A table cell that is one number as code writes it: "11,551", "$402.24B", "-3.1%", "±1.0%", "29.36".
_NUMBER_CELL = re.compile(r"[-+±]?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?[TBMK]?%?")
# The English thousands form: one to three digits, then groups of a comma and exactly three
# digits ("10,803", "1,234,567", "1,234.5"); "17,79" and a date are not.
_THOUSANDS = re.compile(r"(?<![\w.,])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?!\d|[.,]\d)")
# Copied as they are, like the number check does: code spans and link targets.
_PROTECTED = re.compile(r"`[^`]*`|\]\([^)]*\)|https?://\S+")
_CELL_BORDER = re.compile(r"(?<!\\)\|")


def localize(number: str, fmt: NumberFormat) -> str:
    """'11,080' -> '11 080' (a no-break space), '$402.24B' -> '$402,24B' in a decimal-comma format."""
    return number.translate(str.maketrans({",": fmt.thousands, ".": fmt.decimal}))


def _decimal_comma(language: str) -> NumberFormat | None:
    fmt = number_format(language)
    return fmt if fmt.decimal == "," else None


def _outside_protected(text: str, change: Callable[[str], str]) -> str:
    """`change` applied to the text between code spans and link targets."""
    parts, start = [], 0
    for match in _PROTECTED.finditer(text):
        parts += [change(text[start:match.start()]), match.group(0)]
        start = match.end()
    return "".join([*parts, change(text[start:])])


def _table_lines(lines: list[str]) -> list[int]:
    return [i for i, line in enumerate(lines) if line.lstrip().startswith("|")]


def localize_tables(source: str, translation: str, language: str) -> str:
    """
    Every table cell that is a number in the English section, written by code in the
    language's format in the same cell of the translation. Rows pair up in order; a
    translation with another number of table rows or cells in a row is left as it is
    (the structure check rejects it).
    """
    fmt = _decimal_comma(language)
    if fmt is None:
        return translation
    source_lines, lines = source.split("\n"), translation.split("\n")
    source_rows, rows = _table_lines(source_lines), _table_lines(lines)
    if len(source_rows) != len(rows):
        return translation
    for source_row, row in zip(source_rows, rows, strict=True):
        source_cells = _CELL_BORDER.split(source_lines[source_row])
        cells = _CELL_BORDER.split(lines[row])
        if len(source_cells) != len(cells):
            continue
        for i, cell in enumerate(source_cells):
            if _NUMBER_CELL.fullmatch(cell.strip()):
                cells[i] = f" {localize(cell.strip(), fmt)} "
        lines[row] = "|".join(cells)
    return "\n".join(lines)


def _thousands_in(text: str) -> list[str]:
    found: list[str] = []
    _outside_protected(text, lambda part: found.extend(_THOUSANDS.findall(part)) or part)
    return found


def english_thousands(source: str, translation: str, language: str) -> list[str]:
    """
    The numbers the translation writes in the English thousands form, each once, for a
    language with a decimal comma; only numbers the English section writes so ("10,803"),
    and not one the English section also has as a decimal ("10.803"), which the
    translation may rightly write "10,803".
    """
    if _decimal_comma(language) is None:
        return []
    source_numbers = set(_thousands_in(source))
    decimals = set(re.findall(r"\d+\.\d+", source))
    wanted = {n for n in source_numbers if n.replace(",", ".") not in decimals}
    return list(dict.fromkeys(n for n in _thousands_in(translation) if n in wanted))


def rewrite_english_thousands(source: str, translation: str, language: str) -> str:
    """The numbers english_thousands() finds, written in the language's format; the rest unchanged."""
    fmt = _decimal_comma(language)
    left = set(english_thousands(source, translation, language))
    if fmt is None or not left:
        return translation

    def rewrite(part: str) -> str:
        return _THOUSANDS.sub(lambda m: localize(m.group(0), fmt) if m.group(0) in left else m.group(0), part)

    return _outside_protected(translation, rewrite)
