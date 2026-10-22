"""
report.json: the same run as structured data, codes rather than display words.
Failed calls stay in with their error; nothing missing is filled in.
"""

from datetime import datetime, timezone

from analysis.runner import AutopsyRun
from reporting.markdown import DISCLAIMER

SCHEMA_VERSION = 1


def build_json(run: AutopsyRun) -> dict:
    pack = run.pack
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "ticker": pack["ticker"],
            "company_name": pack["company_name"],
            "found_as_related_to": run.related_to,
            "as_of": pack["as_of"],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": run.model,
            "pack_sha256": run.pack_hash,
            "prefix_sha256": run.prefix_hash,
            "sources": pack["sources"],
            "user_context": pack["user_context"],
            "disclaimer": DISCLAIMER,
        },
        "synthesis": run.synthesis,
        "evaluators": {result["key"]: result for result in run.results},
        "valuation_math": run.valuation_math,
        "valuation_multiples": pack["derived"]["valuation"],
        "number_check": run.number_check,
        "data_quality": pack["data_quality"],
        "cost_usd": run.total_cost,
        "duration_s": round(run.duration_s, 1),
    }
