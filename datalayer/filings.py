"""
Filing history events the forensic perspective needs, from SEC submissions:
amended reports, late-filing notices, auditor changes and non-reliance notices
(8-K items 4.01 and 4.02), and how long after each fiscal year end the annual
report was filed. A restatement usually leaves these traces before the restated
numbers appear.
"""

from datetime import date

EVENT_FORMS = {
    "10-K/A": "amended annual report",
    "10-Q/A": "amended quarterly report",
    "NT 10-K": "notice of late annual report",
    "NT 10-Q": "notice of late quarterly report",
}
EIGHT_K_ITEMS = {
    "4.01": "change in the company's certifying accountant (auditor)",
    "4.02": "non-reliance on previously issued financial statements",
}
ANNUAL_FORMS = ("10-K", "10-KT")


def filing_rows(submissions: dict, older: list[dict]) -> list[dict]:
    """All filings as rows, from the 'recent' block and any older submissions files."""
    blocks = [submissions.get("filings", {}).get("recent", {}), *older]
    rows = []
    for block in blocks:
        forms = block.get("form", [])
        for i, form in enumerate(forms):
            rows.append(
                {
                    "form": form,
                    "filed": block["filingDate"][i],
                    "report_date": (block.get("reportDate") or [""] * len(forms))[i] or None,
                    "items": (block.get("items") or [""] * len(forms))[i] or "",
                }
            )
    return rows


def coverage_start(rows: list[dict]) -> date | None:
    return min((date.fromisoformat(r["filed"]) for r in rows), default=None)


def filing_events(rows: list[dict], since: date, as_of: date) -> list[dict]:
    events = []
    for row in rows:
        filed = date.fromisoformat(row["filed"])
        if not since <= filed <= as_of:
            continue
        if row["form"] in EVENT_FORMS:
            events.append(
                {
                    "filed": row["filed"],
                    "form": row["form"],
                    "event": EVENT_FORMS[row["form"]],
                    "report_date": row["report_date"],
                }
            )
        elif row["form"] in ("8-K", "8-K/A"):
            for item in row["items"].split(","):
                item = item.strip()
                if item in EIGHT_K_ITEMS:
                    events.append(
                        {
                            "filed": row["filed"],
                            "form": row["form"],
                            "event": EIGHT_K_ITEMS[item],
                            "item": item,
                        }
                    )
    return sorted(events, key=lambda e: e["filed"])


def annual_report_timing(rows: list[dict], since: date, as_of: date) -> list[dict]:
    """Original annual reports with the days between the fiscal year end and the filing."""
    timing = []
    for row in rows:
        if row["form"] not in ANNUAL_FORMS or not row["report_date"]:
            continue
        filed = date.fromisoformat(row["filed"])
        period_end = date.fromisoformat(row["report_date"])
        if since <= period_end and filed <= as_of:
            timing.append(
                {
                    "period_end": row["report_date"],
                    "filed": row["filed"],
                    "days_after_period_end": (filed - period_end).days,
                }
            )
    return sorted(timing, key=lambda t: t["period_end"])
