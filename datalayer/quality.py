"""
The data_quality block of the DATA PACK: what is missing and why, what was
restated, where sources disagree, which values are partial, and notes about
periods. Evaluators read it before drawing conclusions from absent data.
"""

from dataclasses import dataclass, field

# Why a value is missing (source of truth, data_quality.missing). not_fetched is
# added for sources Phase 1 does not fetch yet (insider transactions, peers,
# news), so "not fetched" is never confused with "none".
NOT_REPORTED = "not_reported"
TAG_NOT_FOUND = "tag_not_found"
PROVIDER_ERROR = "provider_error"
NOT_APPLICABLE = "not_applicable"
NOT_FETCHED = "not_fetched"
MISSING_REASONS = (NOT_REPORTED, TAG_NOT_FOUND, PROVIDER_ERROR, NOT_APPLICABLE, NOT_FETCHED)


@dataclass
class DataQuality:
    fetch_status: dict[str, str] = field(default_factory=dict)
    _missing: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    restated: list[dict] = field(default_factory=list)
    source_conflicts: list[dict] = field(default_factory=list)
    partial: list[dict] = field(default_factory=list)
    period_notes: list[str] = field(default_factory=list)

    def missing(self, field_name: str, period: str, reason: str) -> None:
        if reason not in MISSING_REASONS:
            raise ValueError(f"Unknown missing reason {reason!r}")
        periods = self._missing.setdefault((field_name, reason), [])
        if period not in periods:
            periods.append(period)

    def add_partial(self, field_name: str, covers: str) -> None:
        entry = {"field": field_name, "covers": covers}
        if entry not in self.partial:
            self.partial.append(entry)

    def note(self, text: str) -> None:
        if text not in self.period_notes:
            self.period_notes.append(text)

    def missing_entries(self) -> list[dict]:
        """One entry per field and reason, listing its periods (keeps the pack short)."""
        return [
            {"field": name, "periods": periods, "reason": reason}
            for (name, reason), periods in self._missing.items()
        ]

    def as_dict(self) -> dict:
        return {
            "fetch_status": dict(self.fetch_status),
            "missing": self.missing_entries(),
            "restated": list(self.restated),
            "source_conflicts": list(self.source_conflicts),
            "partial": list(self.partial),
            "period_notes": list(self.period_notes),
        }
