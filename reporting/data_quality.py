"""
The data_quality block of a pack, for a person to read (the page and report.md).

Presentation only: the pack's data_quality stays as it is, because the analysts
read it. For a person the same facts are grouped and ordered by impact (owner's
manual test, M2, 2026-10-17):

1. freshness first: a quarter that is filed but not yet in SEC company facts means
   the analysis runs a filing behind; its two "periods up to ... only" entries are
   folded into that one line;
2. restatements (periods with the same restated fields share one line) and source
   conflicts;
3. other notes, missing and partial values;
4. rounding differences between filings;
5. one fixed line for what this version never collects.
"""

from datalayer.pack import FRESHNESS_COVERS, parse_freshness_note
from reporting.wording import MISSING_REASONS, field

NOT_FETCHED = "not_fetched"
# What this version never collects, in words and in this order.
NOT_COLLECTED_WORDS = {
    "insider_transactions_12m": "insider transactions",
    "peers": "peers",
    "peer_multiples": "peer multiples",
    "news_items": "news",
    "earnings_transcript": "earnings call transcripts",
}
FRESHNESS_FIELDS = ("ttm", "balance_sheet_latest")
ROUNDING_MARK = "smaller differences (under 0.5%)"


def freshness(pack: dict) -> dict | None:
    """{form, period, filed, covers} when the latest filed quarter is not in the facts yet."""
    for note in pack["data_quality"]["period_notes"]:
        parsed = parse_freshness_note(note)
        if parsed:
            return parsed
    return None


def freshness_line(fresh: dict) -> str:
    quarter = "quarter" if fresh["form"].startswith("10-Q") else "period"
    return (
        f"Latest {quarter} missing: the {fresh['form']} for the {quarter} ending {fresh['period']} "
        f"(filed {fresh['filed']}) is not yet in SEC company facts, so the last twelve months, the "
        f"quarters and the balance sheet end at {fresh['covers']}."
    )


def statements_to(pack: dict) -> str | None:
    """The date the financial statements reach, with the freshness gap if there is one."""
    fresh = freshness(pack)
    if fresh:
        return f"{fresh['covers']} (the latest {fresh['form']} is not yet in SEC company facts)"
    end = (pack.get("ttm") or {}).get("period_end") or (pack.get("balance_sheet_latest") or {}).get("date")
    if end is None and pack["financials_annual"]:
        end = pack["financials_annual"][-1]["period_end"]
    return end


def restated_lines(pack: dict) -> list[str]:
    """One line per set of restated fields: "FY2017, FY2018: earlier figures were restated (...)"."""
    by_period: dict[str, list[str]] = {}
    for entry in pack["data_quality"]["restated"]:
        fields = by_period.setdefault(entry["period"], [])
        if field(entry["field"]) not in fields:
            fields.append(field(entry["field"]))
    by_fields: dict[tuple[str, ...], list[str]] = {}
    for period, fields in by_period.items():
        by_fields.setdefault(tuple(fields), []).append(period)
    return [
        f"{', '.join(periods)}: earlier figures were restated ({', '.join(fields)})"
        for fields, periods in by_fields.items()
    ]


def conflict_lines(pack: dict) -> list[str]:
    lines = []
    for c in pack["data_quality"]["source_conflicts"]:
        used = "the SEC figure is used" if c["used"] == "edgar" else (
            "the Yahoo Finance figure is used because the SEC one is out of date")
        sec, yahoo = (_whole(c["values"][source]) for source in ("edgar", "yfinance"))
        lines.append(f"{field(c['field'])}: SEC {sec}, Yahoo Finance {yahoo}; {used}")
    return lines


def _whole(value: float) -> str:
    """Large counts and amounts without float noise: 76,881,214,602.91882 -> 76,881,214,603."""
    return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:,}"


def _periods(periods: list[str]) -> str:
    return "" if periods == ["all"] else f" ({', '.join(periods)})"


def quality_lines(pack: dict, with_restated: bool = True) -> list[str]:
    """
    Every data quality fact as one plain line, most important first. With
    `with_restated=False` the restatements are left out (report.md shows them as a
    table with the amounts).
    """
    q = pack["data_quality"]
    fresh = freshness(pack)
    folded = FRESHNESS_COVERS.format(covers=fresh["covers"]) if fresh else None
    lines = [freshness_line(fresh)] if fresh else []
    if with_restated:
        lines += restated_lines(pack)
    lines += conflict_lines(pack)

    notes = [n for n in q["period_notes"] if not parse_freshness_note(n)]
    lines += [n for n in notes if ROUNDING_MARK not in n]
    lines += [
        f"{field(m['field'])}{_periods(m['periods'])}: {MISSING_REASONS.get(m['reason'], m['reason'])} "
        "(unknown, not zero)"
        for m in q["missing"]
        if m["reason"] != NOT_FETCHED or m["field"] not in NOT_COLLECTED_WORDS
    ]
    lines += [
        f"{field(p['field'])}: {p['covers']}"
        for p in q["partial"]
        if not (folded and p["field"] in FRESHNESS_FIELDS and p["covers"] == folded)
    ]
    lines += [n for n in notes if ROUNDING_MARK in n]

    never = {m["field"] for m in q["missing"] if m["reason"] == NOT_FETCHED}
    words = [NOT_COLLECTED_WORDS[name] for name in NOT_COLLECTED_WORDS if name in never]
    if words:
        lines.append(f"Not collected in this version (unknown, not zero): {_join(words)}.")
    return lines


def _join(words: list[str]) -> str:
    """insider transactions, peers and news: a list in words. Peers and their multiples read as one."""
    if "peers" in words and "peer multiples" in words:
        words = [w for w in words if w != "peer multiples"]
        words[words.index("peers")] = "peers and their multiples"
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])}, {words[-1]}"
