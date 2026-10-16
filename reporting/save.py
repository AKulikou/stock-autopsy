"""
Writes a finished run into results/<TICKER>_<as_of>_<time>/: report.md, report.json,
the exact pack the evaluators saw and the provenance of its values. Used by the
CLI and the web UI.
"""

import json
from datetime import date, datetime
from pathlib import Path

from analysis.runner import AutopsyRun
from reporting.json_export import build_json
from reporting.markdown import build_report


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def save_run(run: AutopsyRun, ticker: str, as_of: date, results_dir: Path, started: datetime) -> Path:
    """Write the run's files and return its directory."""
    out = results_dir / f"{ticker}_{as_of.isoformat()}_{started.strftime('%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(build_report(run), encoding="utf-8")
    write_json(out / "report.json", build_json(run))
    write_json(out / "pack.json", run.pack)
    write_json(out / "provenance.json", run.provenance)
    return out
