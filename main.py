"""
Run a Stock Autopsy for one ticker (paid: several Claude calls).

    python main.py KO
    python main.py SNOW --horizon 10y --risk high

Writes results/<TICKER>_<as_of>_<time>/ with report.md, report.json, the exact
pack.json the evaluators saw and the provenance of its values. Logs go to the
console (INFO) and logs/ (DEBUG).
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

RESULTS = Path("results")
LOGS = Path("logs")


def setup_logging(stamp: str) -> Path:
    LOGS.mkdir(exist_ok=True)
    path = LOGS / f"run_{stamp}.log"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    file = logging.FileHandler(path, encoding="utf-8")
    file.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(console)
    root.addHandler(file)
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "anthropic", "yfinance", "urllib3", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return path


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=True)
    from analysis.runner import run_autopsy
    from core.token_summary import format_cost, log_token_summary
    from datalayer.cache import DailyCache
    from datalayer.fetch import fetch_company
    from datalayer.pack import HORIZONS, RISK_TOLERANCES
    from datalayer.sec import SecClient
    from reporting.json_export import build_json
    from reporting.markdown import build_report

    parser = argparse.ArgumentParser(description="Stock Autopsy: analyze one US public company (paid).")
    parser.add_argument("ticker")
    parser.add_argument("--horizon", choices=HORIZONS, default="5y")
    parser.add_argument("--risk", choices=RISK_TOLERANCES, default="medium")
    args = parser.parse_args(argv)

    as_of = date.today()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = setup_logging(stamp)
    raw = fetch_company(args.ticker, as_of, SecClient(os.getenv("SEC_USER_AGENT")), DailyCache(as_of))
    run = run_autopsy(raw, {"horizon": args.horizon, "risk_tolerance": args.risk})

    out = RESULTS / f"{raw.ticker}_{as_of.isoformat()}_{stamp[-6:]}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(build_report(run), encoding="utf-8")
    write_json(out / "report.json", build_json(run))
    write_json(out / "pack.json", run.pack)
    write_json(out / "provenance.json", run.provenance)
    log_token_summary(run.calls)
    synthesis = run.synthesis
    verdict = synthesis.get("verdict", f"no verdict ({synthesis.get('error')})")
    print(f"\n{raw.ticker}: {verdict}, confidence {synthesis.get('confidence', '-')}")
    print(f"Number check: {run.number_check['counts']}")
    print(f"{format_cost(run.total_cost)}; report {out / 'report.md'}; log {log_path}")
    return 0 if synthesis.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
