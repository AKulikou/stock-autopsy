"""
Financial statement tables built from XBRL facts: annual rows, discrete quarters,
trailing twelve months (TTM) and the latest balance sheet.

Rules applied here (source of truth, data quality rules and period checks):
- A missing value is None with a data_quality.missing entry, never 0.
- Several values for one period: the latest filing wins; a material difference
  from the first reported value is recorded in data_quality.restated.
- Share counts reported before a stock split are multiplied by the split ratio,
  so every share count is on today's basis.
- Periods are identified by dates. A 53-week year is flagged in period_notes.
- TTM = last fiscal year + current year-to-date - the same year-to-date a year
  earlier; it is labelled as TTM and never mixed with fiscal-year figures.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from datalayer import line_items as li
from datalayer.quality import NOT_REPORTED, TAG_NOT_FOUND, DataQuality
from datalayer.xbrl import (
    FIFTY_THREE_WEEK_MIN_DAYS,
    HALF_DAYS,
    NINE_MONTH_DAYS,
    QUARTER_DAYS,
    QUARTERLY_FORMS,
    Fact,
    fiscal_year_label,
    is_material_change,
    preference,
)

MAX_ANNUAL_YEARS = 10
MAX_QUARTERS = 8
DATE_TOLERANCE = timedelta(days=7)
# Ratios of a share count before and after a split that are explained by a split
# even when the split history is unknown.
SPLIT_LIKE_RATIOS = (2, 3, 4, 5, 8, 10, 20, 1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 8, 1 / 10, 1 / 20)

Match = Callable[[Fact], bool]


@dataclass(frozen=True)
class Split:
    day: date
    ratio: float


@dataclass
class Picked:
    value: float | int | None
    source: dict | None = None  # provenance: concept, form, filed, accn, or a formula


@dataclass
class Period:
    start: date
    end: date

    @property
    def label(self) -> str:
        return f"FY{fiscal_year_label(self.end)}"


@dataclass
class Financials:
    facts: dict[str, list[Fact]]
    as_of: date
    quality: DataQuality
    splits: list[Split] | None  # None: split history unknown (price source failed)
    provenance: dict[str, dict] = field(default_factory=dict)
    minor_changes: int = 0
    # Company extension concepts per line item key, used after the us-gaap concepts
    # (datalayer/extensions.py); their facts are keyed 'ext:<concept>'.
    extension_concepts: dict[str, tuple[str, ...]] = field(default_factory=dict)

    # ---- facts and values -------------------------------------------------

    def concepts_of(self, item: li.LineItem) -> tuple[str, ...]:
        return item.concepts + self.extension_concepts.get(item.key, ())

    def _facts(self, item: li.LineItem, match: Match, concepts: tuple[str, ...] | None = None) -> list[Fact]:
        return [
            f
            for concept in (concepts or self.concepts_of(item))
            for f in self.facts.get(concept, [])
            if f.unit == item.unit and match(f)
        ]

    def split_factor(self, filed: date) -> float:
        """Product of the ratios of splits after a filing, up to as_of."""
        factor = 1.0
        for split in self.splits or []:
            if filed < split.day <= self.as_of:
                factor *= split.ratio
        return factor

    def _value(self, item: li.LineItem, fact: Fact) -> float | int:
        if item.unit != li.SHARES:
            return fact.value
        factor = self.split_factor(fact.filed)
        return fact.value if factor == 1.0 else round(fact.value * factor)

    def _pick(self, item: li.LineItem, match: Match, label: str, check_restatement: bool) -> Picked:
        facts = self._facts(item, match)
        if not facts:
            return Picked(None)
        facts = self._without_contradicted_zeros(item, facts, label, check_restatement)
        if not item.concept_migrates:
            first = min(self.concepts_of(item).index(f.concept) for f in facts)
            facts = [f for f in facts if self.concepts_of(item).index(f.concept) == first]
        chosen = max(facts, key=lambda f: preference(f, self.concepts_of(item)))
        if check_restatement:
            self._check_restatement(item, label, facts, chosen)
        source = {
            "concept": chosen.concept,
            "form": chosen.form,
            "filed": chosen.filed.isoformat(),
            "accn": chosen.accn,
        }
        return Picked(self._value(item, chosen), source)

    def _without_contradicted_zeros(
        self, item: li.LineItem, facts: list[Fact], label: str, report: bool
    ) -> list[Fact]:
        """
        A zero for a period that other filings report as non-zero is a tagging
        artifact (a 10-K that moved receivables to the company's own concept left
        the prior year at 0 in us-gaap), not a restatement to zero: drop it.
        A zero that nothing contradicts is a reported zero and stays.
        """
        nonzero = [f for f in facts if f.value != 0]
        if not nonzero or len(nonzero) == len(facts):
            return facts
        if report:
            zero = max((f for f in facts if f.value == 0), key=lambda f: f.filed)
            same = [f for f in nonzero if f.concept == zero.concept] or nonzero
            other = max(same, key=lambda f: f.filed)
            self.quality.note(
                f"{item.key} {label}: {zero.form} filed {zero.filed} reports 0 where {other.form} filed "
                f"{other.filed} reports {other.value:,}; the zero is treated as a tagging error and not used"
            )
        return nonzero

    def _check_restatement(self, item: li.LineItem, label: str, facts: list[Fact], chosen: Fact) -> None:
        original = min(
            facts,
            key=lambda f: (f.filed, f.concept != chosen.concept, self.concepts_of(item).index(f.concept)),
        )
        if original is chosen:
            return
        before, after = self._value(item, original), self._value(item, chosen)
        if not is_material_change(before, after):
            if before != after:
                self.minor_changes += 1
            return
        if item.unit == li.SHARES and self.splits is None and _split_like(original.value, chosen.value):
            self.quality.note(
                f"{item.key} {label}: {original.value:,} -> {chosen.value:,} between filings looks like a "
                "stock split; split history unavailable, values not adjusted"
            )
            return
        entry = {
            "field": item.key,
            "period": label,
            "original": before,
            "restated": after,
            "original_filed": original.filed.isoformat(),
            "filed": chosen.filed.isoformat(),
            "form": chosen.form,
        }
        if original.concept != chosen.concept:
            entry["concept_change"] = f"{original.concept} -> {chosen.concept}"
        self.quality.restated.append(entry)

    def _record(self, key: str, row: dict, item_key: str, picked: Picked, label: str, ever_reported: bool):
        row[item_key] = picked.value
        if picked.value is None:
            self.quality.missing(item_key, label, NOT_REPORTED if ever_reported else TAG_NOT_FOUND)
        elif picked.source:
            self.provenance[f"{key}.{item_key}"] = picked.source

    def _ever_reported(self, item: li.LineItem) -> bool:
        return bool(self._facts(item, lambda f: True))

    # ---- periods ------------------------------------------------------------

    def fiscal_years(self) -> list[Period]:
        """Fiscal years with a reported annual net income or revenue, oldest first, last MAX_ANNUAL_YEARS."""
        starts: dict[date, Fact] = {}
        for item in (li.REVENUE, li.NET_INCOME):  # net income last: its period wins when both exist
            best: dict[date, Fact] = {}
            for f in self._facts(item, lambda f: f.is_annual and f.form not in QUARTERLY_FORMS):
                if f.end not in best or preference(f, item.concepts) > preference(best[f.end], item.concepts):
                    best[f.end] = f
            starts.update(best)
        periods = [Period(f.start, end) for end, f in sorted(starts.items())]
        return periods[-MAX_ANNUAL_YEARS:]

    # ---- annual rows ----------------------------------------------------------

    def _annual_flow(self, item: li.LineItem, period: Period, check: bool = True) -> Picked:
        return self._pick(item, lambda f: f.is_annual and f.end == period.end, period.label, check)

    def _instant(self, item: li.LineItem, day: date, label: str, check: bool = True) -> Picked:
        return self._pick(item, lambda f: f.start is None and f.end == day, label, check)

    def gross_profit(self, revenue: Picked, period_match: Match, label: str, check: bool) -> Picked:
        picked = self._pick(li.GROSS_PROFIT, period_match, label, check)
        if picked.value is not None or revenue.value is None:
            return picked
        cost = self._pick(li.COST_OF_REVENUE, period_match, label, False)
        if cost.value is None:
            return picked
        self.quality.note(
            f"gross_profit {label}: GrossProfit not reported; computed as revenue - cost of revenue"
        )
        return Picked(
            revenue.value - cost.value,
            {"formula": "revenue - cost_of_revenue", "cost_concept": cost.source["concept"]},
        )

    def annual_rows(self, periods: list[Period]) -> list[dict]:
        ever = {item.key: self._ever_reported(item) for item in (*li.FLOW_ITEMS, *li.INSTANT_ITEMS)}
        rows = []
        for period in periods:
            label = period.label
            row: dict = {
                "fiscal_year": fiscal_year_label(period.end),
                "period_start": period.start.isoformat(),
                "period_end": period.end.isoformat(),
            }
            if (period.end - period.start).days >= FIFTY_THREE_WEEK_MIN_DAYS:
                self.quality.note(f"{label} has 53 weeks: about 2% more revenue than a 52-week year")
            revenue = self._annual_flow(li.REVENUE, period)
            for item in li.FLOW_ITEMS:
                if item is li.REVENUE:
                    picked = revenue
                elif item is li.GROSS_PROFIT:
                    picked = self.gross_profit(
                        revenue, lambda f, p=period: f.is_annual and f.end == p.end, label, True
                    )
                else:
                    picked = self._annual_flow(item, period)
                self._record(label, row, item.key, picked, label, ever[item.key] or item is li.GROSS_PROFIT)
            for item in li.INSTANT_ITEMS:
                self._record(
                    label, row, item.key, self._instant(item, period.end, label), label, ever[item.key]
                )
            debt = self.total_debt(period.end, label)
            self._record(label, row, "total_debt", debt, label, debt.source is not None)
            rows.append(row)
        if self.minor_changes:
            self.quality.note(
                f"{self.minor_changes} smaller differences (under 0.5%) between filings for the same period "
                "(rounding, minor reclassifications) are not listed in restated"
            )
        return rows

    # ---- debt ---------------------------------------------------------------

    def _alternative(self, alternatives, day: date, label: str) -> tuple[float | None, list[str], bool]:
        for concepts, partial in alternatives:
            values = []
            for concept in concepts:
                item = li.LineItem("debt", (concept,))
                picked = self._instant(item, day, label, check=False)
                if picked.value is None:
                    break
                values.append(picked.value)
            else:
                return sum(values), list(concepts), partial
        return None, [], False

    def total_debt(self, day: date, label: str) -> Picked:
        """
        Long-term debt including current maturities (or convertible debt when no
        long-term debt is reported) plus short-term borrowings. Never 0 for
        "nothing found": None, with a missing entry from the caller.
        """
        long_term, long_concepts, long_partial = self._alternative(li.LONG_TERM_DEBT_ALTERNATIVES, day, label)
        if long_term is None:
            long_term, long_concepts, long_partial = self._alternative(
                li.CONVERTIBLE_DEBT_ALTERNATIVES, day, label
            )
        short_term, short_concepts, _ = self._alternative(li.SHORT_TERM_DEBT_ALTERNATIVES, day, label)
        if long_term is None and short_term is None:
            return Picked(None, None if not self._any_debt_concept() else {})
        if long_partial:
            self.quality.add_partial(
                "total_debt", "non-current debt only: the current portion is not reported"
            )
        if short_term is None:
            self.quality.add_partial(
                "total_debt", "no short-term borrowings reported (none, or reported under another concept)"
            )
        if long_term is None:
            self.quality.add_partial("total_debt", "short-term borrowings only: no long-term debt reported")
        total = (long_term or 0) + (short_term or 0)  # at least one is known here
        return Picked(total, {"formula": " + ".join(long_concepts + short_concepts)})

    def _any_debt_concept(self) -> bool:
        return any(self.facts.get(concept) for concept in li.DEBT_CONCEPTS)

    # ---- latest balance sheet -------------------------------------------------

    def latest_balance(self) -> dict | None:
        assets = self._facts(li.TOTAL_ASSETS, lambda f: f.start is None)
        if not assets:
            self.quality.missing("balance_sheet_latest", "latest", TAG_NOT_FOUND)
            return None
        day = max(f.end for f in assets)
        label = f"balance {day.isoformat()}"
        row: dict = {"period_end": day.isoformat()}
        for item in li.INSTANT_ITEMS:
            self._record(
                "balance",
                row,
                item.key,
                self._instant(item, day, label, False),
                label,
                self._ever_reported(item),
            )
        debt = self.total_debt(day, label)
        self._record("balance", row, "total_debt", debt, label, debt.source is not None)
        return row

    # ---- quarters and TTM -------------------------------------------------------

    def _ytd(self, item: li.LineItem, start: date, end: date | None, days: range) -> Picked:
        def match(f: Fact) -> bool:
            return (
                f.start is not None
                and abs(f.start - start) <= DATE_TOLERANCE
                and f.days in days
                # A year earlier, a 52/53-week calendar ends a few days off: match ends loosely.
                and (end is None or abs(f.end - end) <= DATE_TOLERANCE)
            )

        return self._pick(item, match, "ytd", False)

    def _quarter_ends(self, fiscal_start: date) -> dict[int, date]:
        """End dates of Q1-Q3 of the fiscal year starting on fiscal_start, from year-to-date facts."""
        ends: dict[int, date] = {}
        for quarter, days in ((1, QUARTER_DAYS), (2, HALF_DAYS), (3, NINE_MONTH_DAYS)):
            for item in (li.NET_INCOME, li.REVENUE):
                facts = self._facts(
                    item,
                    lambda f, d=days: (
                        f.start is not None and abs(f.start - fiscal_start) <= DATE_TOLERANCE and f.days in d
                    ),
                )
                if facts:
                    ends[quarter] = max(facts, key=lambda f: preference(f, item.concepts)).end
                    break
        return ends

    def _discrete(
        self,
        item: li.LineItem,
        fiscal_start: date,
        ends: dict[int, date],
        quarter: int,
        annual: Period | None,
    ) -> tuple[float | int | None, bool]:
        """(value, derived): a reported 3-month value, or a difference of year-to-date values."""
        days_by_quarter = {1: QUARTER_DAYS, 2: HALF_DAYS, 3: NINE_MONTH_DAYS}
        if quarter == 4:
            if annual is None or 3 not in ends:
                return None, False
            full = self._annual_flow(item, annual, check=False).value
            nine = self._ytd(item, fiscal_start, ends[3], NINE_MONTH_DAYS).value
            return (None if full is None or nine is None else full - nine), True
        end = ends[quarter]
        direct = self._pick(item, lambda f: f.end == end and f.days in QUARTER_DAYS, "quarter", False).value
        if direct is not None or quarter == 1:
            return direct, False
        current = self._ytd(item, fiscal_start, end, days_by_quarter[quarter]).value
        previous = self._ytd(item, fiscal_start, ends.get(quarter - 1), days_by_quarter[quarter - 1]).value
        if current is None or previous is None or quarter - 1 not in ends:
            return None, False
        return current - previous, True

    def quarterly_rows(self, periods: list[Period]) -> list[dict]:
        """Up to MAX_QUARTERS discrete quarters of the QUARTERLY_ITEMS, oldest first."""
        years: list[tuple[date, Period | None]] = [(p.start, p) for p in periods[-3:]]
        if periods:
            years.append((periods[-1].end + timedelta(days=1), None))  # the current, unfinished year
        rows = []
        for fiscal_start, annual in years:
            ends = self._quarter_ends(fiscal_start)
            if annual is not None:
                ends_with_q4 = {**ends, 4: annual.end}
            else:
                ends_with_q4 = ends
            for quarter, end in sorted(ends_with_q4.items()):
                if quarter > 1 and quarter - 1 not in ends_with_q4:
                    continue
                start = fiscal_start if quarter == 1 else ends_with_q4[quarter - 1] + timedelta(days=1)
                row: dict = {
                    "fiscal_year": fiscal_year_label(annual.end)
                    if annual
                    else fiscal_year_label(_add_year(periods[-1].end)),
                    "fiscal_quarter": quarter,
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                }
                derived = []
                for item in li.QUARTERLY_ITEMS:
                    value, is_derived = self._discrete(item, fiscal_start, ends, quarter, annual)
                    row[item.key] = value
                    if value is not None and is_derived:
                        derived.append(item.key)
                if derived:
                    row["computed_from_year_to_date"] = derived
                rows.append(row)
        return rows[-MAX_QUARTERS:]

    def ttm(self, periods: list[Period]) -> dict | None:
        """Trailing twelve months of every flow item, or None without a fiscal year."""
        if not periods:
            return None
        last = periods[-1]
        current_start = last.end + timedelta(days=1)
        ends = self._quarter_ends(current_start)
        if not ends:
            row: dict = {
                "basis": "last fiscal year (no later quarter reported)",
                "period_end": last.end.isoformat(),
            }
            for item in li.FLOW_ITEMS:
                row[item.key] = self._annual_flow(item, last, check=False).value
                if row[item.key] is None:
                    self.quality.missing(item.key, "TTM", NOT_REPORTED)
            return row
        quarter = max(ends)
        days = {1: QUARTER_DAYS, 2: HALF_DAYS, 3: NINE_MONTH_DAYS}[quarter]
        end = ends[quarter]
        quarters = "Q1" if quarter == 1 else f"Q1-Q{quarter}"
        row = {
            "basis": f"TTM: FY{fiscal_year_label(last.end)} + {quarters} of the current year "
            f"- the same {'quarter' if quarter == 1 else 'quarters'} a year earlier",
            "period_end": end.isoformat(),
        }
        for item in li.FLOW_ITEMS:
            if item is li.SHARES_DILUTED:
                # Share counts are averages, not sums: TTM uses the latest year-to-date average.
                value = self._ytd(item, current_start, end, days).value
            else:
                full = self._annual_flow(item, last, check=False).value
                current = self._ytd(item, current_start, end, days).value
                prior = self._ytd(item, last.start, _sub_year(end), days).value
                value = None if None in (full, current, prior) else full + current - prior
            row[item.key] = value
            if value is None:
                self.quality.missing(item.key, "TTM", NOT_REPORTED)
        return row

    # ---- shares outstanding ---------------------------------------------------------

    def shares_outstanding(self, dei_facts: list[Fact]) -> dict | None:
        if not dei_facts:
            self.quality.missing("shares_outstanding", "latest", TAG_NOT_FOUND)
            return None
        latest = max(dei_facts, key=lambda f: (f.end, f.filed))
        same = [f for f in dei_facts if f.end == latest.end and f.accn == latest.accn]
        value = sum(f.value for f in same)
        factor = self.split_factor(latest.filed)
        if factor != 1.0:
            value = round(value * factor)
            self.quality.note(f"shares_outstanding multiplied by {factor:g} for splits after {latest.filed}")
        if len(same) > 1:
            self.quality.note(f"shares_outstanding is the sum of {len(same)} share classes")
        return {
            "value": value,
            "date": latest.end.isoformat(),
            "source": "SEC cover page (dei:EntityCommonStockSharesOutstanding), "
            f"{latest.form} filed {latest.filed}",
        }


def _split_like(before: float, after: float) -> bool:
    if before == 0:
        return False
    ratio = after / before
    return any(abs(ratio / r - 1) < 0.01 for r in SPLIT_LIKE_RATIOS)


def _sub_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 February
        return day.replace(year=day.year - 1, day=28)


def _add_year(day: date) -> date:
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return day.replace(year=day.year + 1, day=28)
