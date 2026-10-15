"""
Minimal end-to-end run: two perspectives on one shared context, then a token
summary. Costs a few cents with a real API key:

    python -m examples.minimal_run

Replace the context, the standards, the perspectives and the result schema with
your project's own. The shape stays: build the shared prefix once, hash it, run
the perspectives (the first one warms the cache), report what each call cost.
"""

import logging

from pydantic import BaseModel, Field

from core.fanout import run_parallel
from core.shared_context import context_block, sha256_of
from core.token_summary import log_token_summary
from perspectives.perspective import Perspective, evaluate, shared_prefix

STANDARDS = """\
You are one of several independent analysts. Stay inside your own perspective.
Use only facts from the shared context; when something you need is missing, say
what is missing instead of guessing. A missing value means unknown, never zero.
"""

# A tiny context keeps the example cheap, but it is below the minimum cacheable
# length, so the run will warn that nothing was cached. A real data pack is larger.
CONTEXT = {
    "subject": "Example Coffee Roasters",
    "as_of": "2026-10-14",
    "revenue_eur": {"2024": 410000, "2025": 465000},
    "gross_margin": {"2024": 0.41, "2025": None},
    "notes": "2025 gross margin not yet reported.",
}

PERSPECTIVES = (
    Perspective(
        key="growth",
        name="Growth Analyst",
        role="an analyst of small consumer businesses",
        focus="Is revenue growth real and repeatable?",
        questions=("How fast did revenue grow, and what does the context not tell you about why?",),
    ),
    Perspective(
        key="margins",
        name="Margin Analyst",
        role="a cost accountant",
        focus="Are margins known and stable?",
        questions=("What do the margins show, and which values are missing?",),
    ),
)


class Finding(BaseModel):
    summary: str = Field(description="Two or three sentences.")
    missing_data: list[str] = Field(description="Facts the analysis needed but the context lacks.")


def validate_finding(finding: Finding) -> list[str]:
    return [] if len(finding.summary.strip()) >= 20 else ["summary too short"]


def main() -> list[dict]:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    context = context_block("shared_context", CONTEXT)
    prefix = shared_prefix(STANDARDS, context)
    context_hash = sha256_of(prefix)
    logging.info(f"Shared prefix sha256 {context_hash[:12]}, {len(prefix)} chars")
    results = run_parallel([
        (p.name, lambda p=p: evaluate(p, prefix, Finding, validate_finding)) for p in PERSPECTIVES
    ])
    for result in results:
        result["prefix_sha256"] = context_hash
        logging.info(f"{result['label']}: {result['status']} {result.get('summary', result.get('error'))}")
    log_token_summary(results)
    return results


if __name__ == "__main__":
    main()
