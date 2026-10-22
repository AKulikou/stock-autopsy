"""
The number check of a translated section: every number of the English source must
come back with the same value and the same scale.

A translator may write numbers the way its language does ("1.5 billion" becomes
"1,5 млрд" in Russian, "36,212,000,000" becomes "36 212 000 000"), so values are
compared after reading the separators and the scale words of both sides:

- the English source uses "," for thousands and "." for decimals, nothing else;
- a translation may use either convention or spaces for thousands; a token that can
  be read two ways ("1,234": a thousand-separated 1234 or a decimal 1.234) counts as
  either;
- scale words (thousand, million, billion, trillion and B / M / K / T after a number,
  тыс., млн, млрд, трлн, Lithuanian tūkst., mln., mlrd., trln.) multiply the value, so
  "1,5 млн" for "1.5 billion" is a different number;
- a percent, percentage points and a multiple ("x", "times", "раза") must not
  contradict each other: "4.5 points" written as "4,5 %" is rejected (Russian "п. п.",
  Lithuanian "procentinio punkto" or "proc. punkto" are points; "proc." alone is a percent). A number with
  no such word may stand for one with it ("21-25%" can come back as "21 %–25 %").

Signs are not compared ("-3 billion" may become "убыток 3 млрд"), and neither are
extra numbers in the translation. Code spans and link targets are left out on both
sides: they are copied as they are.

Labels and durations are not quantities, the same list as the DATA number check uses
(reporting.number_check.NOT_QUANTITIES): "Q4 2025" may become "четвёртый квартал
2025", "a 10-year record" "десятилетняя история", "10-K" stays. (Found on the first
real translation, 2026-10-17: all ten rejections were such words.) Dates are compared
as dates: 2024-05-30 may come back as written, as 30.05.2024 or as "30 мая 2024".
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

SCALES = (
    (r"трлн|триллион\w*|trln\.?|trilijon\w*|trillion", 12),
    (r"млрд|миллиард\w*|mlrd\.?|milijard\w*|billion|bn", 9),
    (r"млн|миллион\w*|mln\.?|milijon\w*|million|mn", 6),
    (r"тыс\.?|тысяч\w*|tūkst\.?|tūkstan\w*|tūkstanč\w*|thousand", 3),
)
# One capital letter right after the digits: "$9.99B", "$841.00M".
LETTER_SCALES = {"T": 12, "B": 9, "M": 6, "K": 3}
PERCENT, POINTS, MULTIPLE = "percent", "percentage points", "multiple"
KINDS = (
    (r"п\.\s?п\.|пп\b|процентн\w*\s+пункт\w*|пункт\w*|p\.\s?p\.|proc\.\s?punkt\w*|procentin\w*\s+punkt\w*"
     r"|punkt\w*|percentage\s+points?|pp\b|points?\b", POINTS),
    (r"%|процент\w*|proc\.|procent\w*|percent\b", PERCENT),
    (r"[xх×](?!\w)|times\b|раз\w*|kart\w*", MULTIPLE),
)
_SCALE = "|".join(f"(?:{pattern})" for pattern, _ in SCALES)
_KIND = "|".join(f"(?:{pattern})" for pattern, _ in KINDS)
_SPACE = "[   ]"
# Digits with thousands groups (commas or spaces) or one decimal part. Not preceded by
# a digit, point or comma, so "FY2024" gives 2024 and "1,5" is one token.
_NUMBER = re.compile(
    rf"(?<![\d.,])(?P<digits>\d{{1,3}}(?:(?:,\d{{3}})+|(?:{_SPACE}\d{{3}})+)(?!\d)(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    rf"(?P<letter>[TBMK](?![\w]))?"
    rf"(?:\s?(?P<scale>{_SCALE}))?"
    rf"(?:\s?(?P<kind>{_KIND}))?",
    re.IGNORECASE,
)
_CODE_SPAN = re.compile(r"`[^`]*`")
_LINK_TARGET = re.compile(r"\]\([^)]*\)|https?://\S+")


@dataclass(frozen=True)
class Number:
    text: str                       # as written, for messages
    values: frozenset[Decimal]      # every reading of it, scale applied
    kind: str | None                # PERCENT, POINTS, MULTIPLE or None


def _plain(text: str) -> str:
    return _LINK_TARGET.sub(" ", _CODE_SPAN.sub(" ", text))


def _english_readings(digits: str) -> set[Decimal]:
    return {Decimal(digits.replace(",", ""))}


def _any_readings(digits: str) -> set[Decimal]:
    """Every way a translation may have meant these digits."""
    if re.search(_SPACE, digits):
        grouped = re.sub(_SPACE, "", digits)
        return {Decimal(grouped.replace(",", "."))}
    if "," in digits and "." in digits:
        decimal_mark = max(digits.rfind(","), digits.rfind("."))
        whole, fraction = digits[:decimal_mark], digits[decimal_mark + 1:]
        return {Decimal(re.sub(r"[.,]", "", whole) + "." + fraction)}
    for mark in (",", "."):
        if mark in digits:
            parts = digits.split(mark)
            readings = set()
            if all(len(p) == 3 for p in parts[1:]):
                readings.add(Decimal("".join(parts)))  # thousands groups
            if len(parts) == 2:
                readings.add(Decimal(f"{parts[0]}.{parts[1]}"))  # a decimal mark
            return readings
    return {Decimal(digits)}


def _kind(word: str | None) -> str | None:
    if not word:
        return None
    for pattern, kind in KINDS:
        if re.fullmatch(pattern, word, re.IGNORECASE):
            return kind
    return None


def _power(match: re.Match) -> int:
    if match["letter"]:
        return LETTER_SCALES[match["letter"].upper()]
    if match["scale"]:
        for pattern, power in SCALES:
            if re.fullmatch(pattern, match["scale"], re.IGNORECASE):
                return power
    return 0


# Labels and durations in the English source that a translation may write in words:
# form names, 8-K items, quarter labels, "years 1-5", "a 10-year record", "over 3 years".
_NOT_COMPARED = re.compile(
    r"\b(?:NT\s+)?(?:10-K|10-Q|8-K|10-KT|20-F|40-F|S-1|S-4|DEF\s*14A)(?:/A)?s?\b"
    r"|\bItem\s+\d+(?:\.\d+)?"
    r"|\bQ[1-4]\b"
    r"|\b(?:years?|quarters?)(?:\s+|-)\d{1,2}(?:\s*(?:-|–|to|through)\s*\d{1,2})?\b"
    r"|\b\d{1,2}(?:-|\s+)(?:years?|quarters?|months?|weeks?|days?)\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
# (Russian, English, Lithuanian genitive) month names or stems.
MONTHS = (
    ("янв", "jan", "sausio"), ("фев", "feb", "vasario"), ("мар", "mar", "kovo"), ("апр", "apr", "balandžio"),
    ("ма[яй]", "may", "gegužės"), ("июн", "jun", "birželio"), ("июл", "jul", "liepos"),
    ("авг", "aug", "rugpjūčio"), ("сен", "sep", "rugsėjo"), ("окт", "oct", "spalio"),
    ("ноя", "nov", "lapkričio"), ("дек", "dec", "gruodžio"),
)


def _blank(pattern: re.Pattern, text: str) -> str:
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def date_found(year: str, month: str, day: str, translation: str) -> bool:
    """
    2024-05-30 as written, as 30.05.2024 or 30/05/2024, or as "30 мая 2024", "May 30, 2024"
    or "2024 m. gegužės 30 d.".
    """
    d, m = int(day), int(month)
    ru, en, lt = MONTHS[m - 1]
    forms = (
        rf"\b{year}-{month}-{day}\b",
        rf"\b0?{d}[./]0?{m}[./]{year}\b",
        rf"\b0?{d}\s+(?:{ru}|{en})\w*\.?\s+{year}\b",
        rf"\b{en}\w*\.?\s+0?{d},?\s+{year}\b",
        rf"\b{year}\s*m\.\s+{lt}\s+0?{d}\s*d\.",
    )
    return any(re.search(form, translation, re.IGNORECASE) for form in forms)


def numbers_in(text: str, english: bool) -> list[Number]:
    """
    The numbers of a text; `english` reads separators the English way only and leaves
    out labels, durations and dates (_NOT_COMPARED, dates are checked as dates).
    """
    plain = _plain(text)
    if english:
        plain = _blank(_NOT_COMPARED, _blank(_ISO_DATE, plain))
    found = []
    for match in _NUMBER.finditer(plain):
        readings = _english_readings(match["digits"]) if english else _any_readings(match["digits"])
        if english and re.search(_SPACE, match["digits"]):
            # "2 234" in English is two numbers, not a thousands group.
            found.extend(numbers_in(re.sub(_SPACE, "\n", match.group(0)), english=True))
            continue
        scale = Decimal(10) ** _power(match)
        values = frozenset((value * scale).normalize() for value in readings)
        found.append(Number(match.group(0).strip(), values, _kind(match["kind"])))
    return found


def _compatible(a: str | None, b: str | None) -> bool:
    return a is None or b is None or a == b


def missing_numbers(source: str, translation: str) -> list[str]:
    """
    The numbers of the English source that the translation does not have with the
    same value and scale, as written in the source (empty when all are there). Each
    number of the translation answers for at most one number of the source.
    """
    wanted = numbers_in(source, english=True)
    offered = numbers_in(translation, english=False)
    used = [False] * len(offered)

    def take(number: Number, candidates: Iterable[int]) -> bool:
        for i in candidates:
            fits = number.values & offered[i].values and _compatible(number.kind, offered[i].kind)
            if fits and not used[i]:
                used[i] = True
                return True
        return False

    missing = [
        date.group(0)
        for date in _ISO_DATE.finditer(_plain(source))
        if not date_found(*date.groups(), _plain(translation))
    ]
    # Numbers with a kind first, and a candidate of the same kind first, so a plain
    # number does not take the only "%" a percentage needs.
    for number in sorted(wanted, key=lambda n: n.kind is None):
        same = [i for i, o in enumerate(offered) if o.kind == number.kind]
        other = [i for i, o in enumerate(offered) if o.kind != number.kind]
        if not take(number, same) and not take(number, other):
            missing.append(number.text)
    return missing
