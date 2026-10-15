"""
XBRL facts from SEC companyfacts, and the rules for picking one value per period.

What the raw data looks like, and the traps it holds (checked on KO, PG, SNOW,
RIVN, KHC, MDXG and PLUG, 2026-09-27 and 2026-10-15):

- facts[taxonomy][concept]["units"][unit] is a list of
  {start?, end, val, accn, fy, fp, form, filed, frame?}. Instants have no start.
- The same period appears in many filings: as the current period, then as a
  comparative in the next filings, sometimes with a different value
  (restatement, recast, rounding, split adjustment).
- `fy` and `fp` describe the filing, not the period: periods are identified by
  their start and end dates only.
- Proxy statements (DEF 14A) carry rounded figures in "pay versus performance"
  tables; they are not financial statements and are ignored here.
- The same line item moves between concepts over the years, and a later filing
  may restate a period under a different concept than the original.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

# Filings that contain financial statements. 8-K recasts (prior years presented
# again after an accounting or segment change) and registration statements
# (audited statements before an IPO) count; proxy statements do not.
STATEMENT_FORMS = {
    "10-K",
    "10-K/A",
    "10-KT",
    "10-KT/A",
    "10-Q",
    "10-Q/A",
    "8-K",
    "8-K/A",
    "S-1",
    "S-1/A",
    "S-4",
    "S-4/A",
    "10-12B",
    "10-12B/A",
    "10-12G",
    "10-12G/A",
}
QUARTERLY_FORMS = {"10-Q", "10-Q/A"}

# Period lengths in days (end - start). A 52-week year is 363 days, a 53-week
# year 370, a calendar year 364 or 365.
ANNUAL_DAYS = range(350, 381)
QUARTER_DAYS = range(80, 101)
HALF_DAYS = range(170, 192)
NINE_MONTH_DAYS = range(260, 285)
FIFTY_THREE_WEEK_MIN_DAYS = 369

# Two values for one period that differ by less than this share of the larger
# one are rounding or a minor reclassification, not a restatement.
MATERIAL_CHANGE = 0.005


@dataclass(frozen=True)
class Fact:
    concept: str
    unit: str
    value: float
    start: date | None
    end: date
    filed: date
    form: str
    accn: str

    @property
    def days(self) -> int | None:
        return None if self.start is None else (self.end - self.start).days

    @property
    def is_annual(self) -> bool:
        return self.days is not None and self.days in ANNUAL_DAYS


def _number(value):
    """XBRL values are integers or decimals; keep integers as int."""
    if isinstance(value, bool):
        raise TypeError("boolean is not a number")
    number = float(value)
    return int(number) if number.is_integer() else number


def load_facts(
    company_facts: dict, as_of: date, concepts: set[str], taxonomy: str = "us-gaap"
) -> tuple[dict[str, list[Fact]], int]:
    """
    Facts of the given concepts from statement filings, keyed by concept, and
    the number of facts dropped because their period ended or they were filed
    after as_of (a future date is either corrupt or not yet knowable at as_of).
    """
    by_concept: dict[str, list[Fact]] = defaultdict(list)
    dropped = 0
    source = company_facts.get("facts", {}).get(taxonomy, {})
    for concept in concepts:
        for unit, items in source.get(concept, {}).get("units", {}).items():
            for item in items:
                if item.get("form") not in STATEMENT_FORMS:
                    continue
                end = date.fromisoformat(item["end"])
                filed = date.fromisoformat(item["filed"])
                if end > as_of or filed > as_of:
                    dropped += 1
                    continue
                start = date.fromisoformat(item["start"]) if item.get("start") else None
                by_concept[concept].append(
                    Fact(concept, unit, _number(item["val"]), start, end, filed, item["form"], item["accn"])
                )
    return dict(by_concept), dropped


def fiscal_year_label(period_end: date) -> int:
    """
    The fiscal year a period ending on this date is named after. Companies whose
    52/53-week year ends in the first days of January name it after the year
    before (Kraft Heinz: 2016-01-03 closes fiscal 2015); a year ending later in
    January is named after the year it ends in (Snowflake: 2026-01-31 is fiscal 2026).
    """
    if period_end.month == 1 and period_end.day <= 7:
        return period_end.year - 1
    return period_end.year


def preference(fact: Fact, concepts: tuple[str, ...]) -> tuple:
    """
    Sort key: the best fact for a period sorts last. A 10-Q only quotes an annual
    figure in a note, so any other statement filing wins for an annual period;
    then the latest filing wins (it holds restatements); then the concept listed
    first wins (a total such as Revenues over a narrower concept in the same filing).
    """
    quarterly_quote = fact.is_annual and fact.form in QUARTERLY_FORMS
    return (not quarterly_quote, fact.filed, -concepts.index(fact.concept))


def is_material_change(original: float, latest: float) -> bool:
    largest = max(abs(original), abs(latest))
    if largest == 0:
        return False
    return abs(original - latest) / largest >= MATERIAL_CHANGE
