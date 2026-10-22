"""
The Markdown tables of a translated section against the English ones.

A translator can break a table without changing a number or the count of lines
that start with "|": a Russian copy of 2026-10-22 lost the closing "|" of a row of
the conflict map, and the page (like most Markdown renderers) then ends the table
there and prints the row as a paragraph with "|" in it. The English report.md had
the table intact.

table_problem() compares every table with the English one: the same number of
tables, of rows and of cells in each row, every row on one line that starts and
ends with "|", no blank line inside a table. repair_tables() puts right what code
can: a row split over several lines is joined, a blank line inside a table is
removed, a row that lost its closing "|" gets it back. Whatever still differs is
not guessed: the section is checked again and stays in English if it fails.
"""

import re
from dataclasses import dataclass

TABLE_BROKEN = "a table came back broken"
_DIVIDER = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|*\s*$")
_BORDER = re.compile(r"(?<!\\)\|")


@dataclass(frozen=True)
class Table:
    header: str
    rows: tuple[str, ...]   # the body: lines starting with "|" right after the divider
    end: int                # the index of the first line after the table


def _is_row(line: str) -> bool:
    return line.lstrip().startswith("|")


def _closed(line: str) -> bool:
    return _is_row(line) and line.rstrip().endswith("|") and len(line.strip()) > 1


def _cells(line: str) -> int:
    """Cells of a row that starts and ends with "|"."""
    return len(_BORDER.findall(line.strip())) - 1


def tables(text: str) -> list[Table]:
    """Each table as a renderer sees it: a header row, a divider, then consecutive rows."""
    lines = text.split("\n")
    found, i = [], 0
    while i < len(lines) - 1:
        if _is_row(lines[i]) and _DIVIDER.match(lines[i + 1]):
            j = i + 2
            while j < len(lines) and _is_row(lines[j]):
                j += 1
            found.append(Table(lines[i], tuple(lines[i + 2:j]), j))
            i = j
        else:
            i += 1
    return found


def _name(table: Table) -> str:
    columns = [c.strip() for c in _BORDER.split(table.header.strip())[1:-1]]
    return f'the table with the columns {", ".join(columns)}'


def _next_row_after_blank(lines: list[str], index: int) -> bool:
    """True when blank lines at `index` are followed by a table row that is not a new table's header."""
    j = index
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j == index or j >= len(lines) or not _is_row(lines[j]):
        return False
    return not (j + 1 < len(lines) and _DIVIDER.match(lines[j + 1]))


def table_problem(source: str, translation: str) -> str | None:
    """How the translation's tables differ from the English ones, naming the table and row, or None."""
    wanted, got = tables(source), tables(translation)
    lines = translation.split("\n")
    for k, english in enumerate(wanted):
        name = _name(english)
        if k >= len(got):
            return f"{TABLE_BROKEN}: {name} is missing"
        table, cells = got[k], _cells(english.header)
        if not _closed(table.header) or _cells(table.header) != cells:
            return f"{TABLE_BROKEN}: {name}, header row: not {cells} cells on one line"
        for r, row in enumerate(table.rows, 1):
            if not _closed(row):
                return f"{TABLE_BROKEN}: {name}, row {r}: a line break in the row or a lost | at its end"
            if _cells(row) != cells:
                return f"{TABLE_BROKEN}: {name}, row {r}: {_cells(row)} cells instead of {cells}"
        if len(table.rows) != len(english.rows):
            if len(table.rows) < len(english.rows) and _next_row_after_blank(lines, table.end):
                return f"{TABLE_BROKEN}: {name}, a blank line after row {len(table.rows)}"
            return f"{TABLE_BROKEN}: {name}, {len(table.rows)} rows instead of {len(english.rows)}"
    if len(got) > len(wanted):
        return f"{TABLE_BROKEN}: {len(got)} tables instead of {len(wanted)}"
    return None


def _cut(row: str, cells: int) -> bool:
    """Not closed, or closed with fewer cells than its header: the row goes on below."""
    return not row.rstrip().endswith("|") or _cells(row) < cells


def repair_tables(translation: str) -> str:
    """
    A row split over lines joined into one, blank lines between two rows of one table
    removed, and a lost closing "|" put back. Nothing else is changed.
    """
    lines = translation.split("\n")
    out, i, cells = [], 0, 0
    while i < len(lines):
        line = lines[i]
        if not _is_row(line):
            out.append(line)
            i += 1
            continue
        if i + 1 < len(lines) and _DIVIDER.match(lines[i + 1]):
            cells = _cells(line)  # a header: the rows below have its number of cells
        while (_cut(line, cells) and i + 1 < len(lines) and lines[i + 1].strip()
               and not _is_row(lines[i + 1]) and not lines[i + 1].lstrip().startswith("#")):
            i += 1
            line = f"{line.rstrip()} {lines[i].strip()}"
        if not _DIVIDER.match(line) and not line.rstrip().endswith("|"):
            line = f"{line.rstrip()} |"
        out.append(line)
        i += 1
        if _next_row_after_blank(lines, i):
            while not lines[i].strip():
                i += 1
    return "\n".join(out)
