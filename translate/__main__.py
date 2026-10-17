"""
Translate the report of a saved run (paid: one cheap call per report section,
about 0.02-0.03 USD for a long report; the English report.md is never changed).

    python -m translate results/KO_2026-10-17_090436 --language Russian

Writes report.<code>.md next to report.md (report.ru.md for Russian); an existing
translation is reused, not paid for again.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


def describe(outcome: dict, language: str, cost: float | None) -> str:
    """One line on what the translation did, in words."""
    from core.token_summary import format_cost

    if outcome["reused"]:
        return f"{outcome['path']} already exists; nothing was translated or paid for."
    if outcome["status"] != "success":
        return f"The translation into {language} failed ({outcome['error']}); no file was written."
    kept = outcome["untranslated_sections"]
    return (
        f"Translated into {language}: {outcome['path']}. {outcome['sections']} sections, "
        f"{kept} kept in English, {outcome['number_rejections']} answers rejected because a number changed, "
        f"{outcome['calls']} calls, {format_cost(cost)}, {outcome['duration_s']:.0f} s."
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=True)
    from core.token_summary import call_cost
    from main import setup_logging
    from translate.languages import DEFAULT_LANGUAGE, LANGUAGES, language_name
    from translate.translator import REPORT_FILENAME, translate_report

    parser = argparse.ArgumentParser(description="Translate the report of a saved run (paid, cheap).")
    parser.add_argument("run_dir", type=Path, help="a run folder in results/ holding report.md")
    offered = ", ".join(name for name, _, _ in LANGUAGES)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE,
                        help=f"one of: {offered} (default {DEFAULT_LANGUAGE})")
    args = parser.parse_args(argv)
    language = language_name(args.language)
    if language is None:
        parser.error(f"{args.language!r} is not offered; choose one of {offered}")
    if not (args.run_dir / REPORT_FILENAME).exists():
        parser.error(f"{args.run_dir} holds no {REPORT_FILENAME}")

    setup_logging(f"translate_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    outcome = translate_report(args.run_dir, language)
    cost = call_cost(outcome) if outcome.get("input_tokens") is not None else None
    logging.getLogger(__name__).info(describe(outcome, language, cost))
    return 0 if outcome["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
