"""
Company extension concepts: line items a company reports under its own XBRL
names instead of a us-gaap concept.

SEC company facts carry the standard taxonomies only (us-gaap, dei, srt, ...),
so an extension concept never shows up there. Some companies report their
receivables as their own "TradeReceivablesAndContractAssetsAfterAllowanceFor
CreditLossCurrent", for example, which also includes contract assets. The only
source is the filing itself: each 10-K and 10-Q comes with an XBRL instance
document holding every fact.

This module fetches those instances only when needed (a us-gaap line item stops
before the latest annual report), keeps the facts of non-standard namespaces
that have no dimensions (the consolidated figures), and returns them in the
company-facts shape under the taxonomy "ext". Choosing which extension concept
stands for a line item is strict (see matching_concepts): a wrong match would be
worse than an honest "unknown".
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date

from datalayer.cache import DailyCache
from datalayer.sec import SecClient

logger = logging.getLogger(__name__)

ARCHIVES = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/"
EXTENSION_TAXONOMY = "ext"
XBRLI = "{http://www.xbrl.org/2003/instance}"
STANDARD_NAMESPACE = re.compile(
    r"fasb\.org/us-gaap|xbrl\.sec\.gov/|fasb\.org/srt|xbrl\.org/|w3\.org/|xbrl\.ifrs\.org", re.IGNORECASE
)
ANNUAL_FORMS = ("10-K", "10-KT")
QUARTERLY_FORMS = ("10-Q",)
UNIT_NAMES = {"iso4217:USD": "USD", "xbrli:shares": "shares"}

# Line items that may come from an extension concept, with the rule that picks it.
RECEIVABLE_NAME = re.compile(r"Receivable", re.IGNORECASE)
NOT_A_RECEIVABLE_BALANCE = re.compile(
    r"^IncreaseDecrease|Noncurrent|RelatedPart|Other|Unbilled|Financing|Loan|Note|Tax|Interest|Employee"
    r"|Allowance",
    re.IGNORECASE,
)


def is_receivable_balance(concept: str) -> bool:
    """
    A current trade receivable, net of allowance: 'Receivable' in the name, ending
    in 'Current', not a change, a non-current, related-party, tax or other
    receivable, and not the allowance itself (an 'After/NetOfAllowance...Current'
    name is the net balance and passes).
    """
    # Companies are not consistent about case: one wrote "...andContractAssetsafterAllowancefor..."
    # until 2024 and "...AndContractAssetsAfterAllowanceFor..." from 2025.
    if not RECEIVABLE_NAME.search(concept) or not concept.lower().endswith("current"):
        return False
    if re.search(r"(After|NetOf)Allowance", concept, re.IGNORECASE):
        stripped = re.sub(r"(After|NetOf)Allowance\w*Current$", "Current", concept, flags=re.IGNORECASE)
        return not NOT_A_RECEIVABLE_BALANCE.search(stripped)
    return not NOT_A_RECEIVABLE_BALANCE.search(concept)


EXTENSION_MATCHERS = {"accounts_receivable": is_receivable_balance}


def extension_gap(company_facts: dict, rows: list[dict], window_start: date) -> date | None:
    """
    The date after which extension facts are needed: the last us-gaap receivable
    balance (or the window start, if there is none) when it ends before the latest
    annual report; None when us-gaap covers the latest annual report.
    """
    from datalayer.line_items import ACCOUNTS_RECEIVABLE

    gaap = company_facts.get("facts", {}).get("us-gaap", {})
    ends = [
        date.fromisoformat(item["end"])
        for concept in ACCOUNTS_RECEIVABLE.concepts
        for items in gaap.get(concept, {}).get("units", {}).values()
        for item in items
        if "start" not in item
    ]
    annual_reports = [
        date.fromisoformat(r["report_date"]) for r in rows if r["form"] in ANNUAL_FORMS and r["report_date"]
    ]
    if not annual_reports:
        return None
    last = max(ends, default=window_start)
    if last >= max(annual_reports):
        return None
    return max(last, window_start)


def matching_concepts(extension_facts: dict, item_key: str) -> list[tuple[str, ...]]:
    """
    Candidate concepts for a line item, grouped: names that differ only in case are
    one concept spelled differently over the years. Within a group the spelling
    of the latest filing comes first. More than one group is ambiguous.
    """
    match = EXTENSION_MATCHERS[item_key]
    concepts = extension_facts.get("facts", {}).get(EXTENSION_TAXONOMY, {})
    groups: dict[str, list[str]] = {}
    for name in concepts:
        if match(name):
            groups.setdefault(name.lower(), []).append(name)

    def last_filed(name: str) -> str:
        return max(item["filed"] for items in concepts[name]["units"].values() for item in items)

    return [tuple(sorted(names, key=last_filed, reverse=True)) for _, names in sorted(groups.items())]


def parse_instance(xml: bytes, accn: str, form: str, filed: str) -> dict[str, dict]:
    """
    Facts of non-standard namespaces without dimensions, in the company-facts
    shape: {concept: {"units": {unit: [{start?, end, val, accn, form, filed}]}}}.
    """
    root = ET.fromstring(xml)
    contexts: dict[str, dict] = {}
    for context in root.iter(XBRLI + "context"):
        if (
            context.find(f"{XBRLI}entity/{XBRLI}segment") is not None
            or context.find(f"{XBRLI}scenario") is not None
        ):
            continue
        period = context.find(XBRLI + "period")
        instant = period.find(XBRLI + "instant")
        if instant is not None:
            contexts[context.get("id")] = {"end": instant.text.strip()}
        else:
            contexts[context.get("id")] = {
                "start": period.find(XBRLI + "startDate").text.strip(),
                "end": period.find(XBRLI + "endDate").text.strip(),
            }
    units: dict[str, str] = {}
    for unit in root.iter(XBRLI + "unit"):
        measure = unit.find(XBRLI + "measure")
        if measure is not None:
            units[unit.get("id")] = UNIT_NAMES.get(measure.text.strip(), measure.text.strip())
    facts: dict[str, dict] = {}
    for element in root:
        if not element.tag.startswith("{") or element.get("contextRef") not in contexts:
            continue
        namespace, concept = element.tag[1:].split("}", 1)
        unit = units.get(element.get("unitRef", ""))
        if STANDARD_NAMESPACE.search(namespace) or unit is None or element.text is None:
            continue
        try:
            value = float(element.text.strip())
        except ValueError:
            continue
        record = {
            **contexts[element.get("contextRef")],
            "val": int(value) if value.is_integer() else value,
            "accn": accn,
            "form": form,
            "filed": filed,
        }
        facts.setdefault(concept, {"units": {}})["units"].setdefault(unit, []).append(record)
    return facts


def instance_name(index: dict) -> str | None:
    """The XBRL instance in a filing folder: the extracted inline instance, or a plain instance."""
    names = [item["name"] for item in index.get("directory", {}).get("item", [])]
    inline = [n for n in names if n.endswith("_htm.xml")]
    if inline:
        return inline[0]
    plain = [
        n
        for n in names
        if n.endswith(".xml") and n != "FilingSummary.xml" and not re.search(r"_(cal|def|lab|pre)\.xml$", n)
    ]
    return plain[0] if plain else None


def filings_to_read(rows: list[dict], gap_start: date, as_of: date) -> list[dict]:
    """Original 10-Ks for periods after gap_start, and the latest 10-Q after the last of them."""
    periodic = [
        r
        for r in rows
        if r.get("accession")
        and r["report_date"]
        and date.fromisoformat(r["filed"]) <= as_of
        and date.fromisoformat(r["report_date"]) > gap_start
    ]
    annual = [r for r in periodic if r["form"] in ANNUAL_FORMS]
    quarterly = [r for r in periodic if r["form"] in QUARTERLY_FORMS]
    latest_annual = max((r["report_date"] for r in annual), default="")
    later = [r for r in quarterly if r["report_date"] > latest_annual]
    chosen = sorted(annual, key=lambda r: r["report_date"])
    if later:
        chosen.append(max(later, key=lambda r: r["report_date"]))
    return chosen


def fetch_extension_facts(
    sec: SecClient, cache: DailyCache, symbol: str, cik: int, rows: list[dict], gap_start: date, as_of: date
) -> dict:
    """Extension facts of the filings that cover the gap, merged in the company-facts shape."""
    merged: dict[str, dict] = {}
    for row in filings_to_read(rows, gap_start, as_of):
        folder = row["accession"].replace("-", "")
        base = ARCHIVES.format(cik=cik, folder=folder)

        def read(row=row, base=base) -> dict:
            name = instance_name(sec.get_json(base + "index.json"))
            if name is None:
                raise LookupError(f"no XBRL instance in {row['accession']}")
            return parse_instance(sec.get_bytes(base + name), row["accession"], row["form"], row["filed"])

        facts, _ = cache.load_or_fetch(symbol, f"ext_{folder}", fetch=read)
        for concept, body in facts.items():
            for unit, items in body["units"].items():
                merged.setdefault(concept, {"units": {}})["units"].setdefault(unit, []).extend(items)
    return {"facts": {EXTENSION_TAXONOMY: merged}}
