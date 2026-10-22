"""
Run a Stock Autopsy for one ticker (paid: several Claude calls).

    python main.py KO
    python main.py SNOW --horizon 10y --risk high

Writes results/<TICKER>_<as_of>_<time>/ with report.md, report.json, the exact
pack.json the evaluators saw and the provenance of its values. Logs go to the
console (INFO) and logs/ (DEBUG).
"""

import argparse
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


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=True)
    from analysis.runner import run_autopsy
    from core.token_summary import format_cost, log_token_summary
    from datalayer.cache import DailyCache
    from datalayer.fetch import DataUnavailableError, fetch_company
    from datalayer.pack import HORIZONS, RISK_TOLERANCES
    from datalayer.sec import SecAccessError, SecClient, UnknownTickerError
    from datalayer.sector import FINANCIAL_NOTE, financial_kind
    from reporting.save import save_run
    from reporting.wording import COMMITTEE_VERDICTS, CONFIDENCE, company_display

    parser = argparse.ArgumentParser(description="Stock Autopsy: analyze one US public company (paid).")
    parser.add_argument("ticker")
    parser.add_argument("--horizon", choices=HORIZONS, default="5y")
    parser.add_argument("--risk", choices=RISK_TOLERANCES, default="medium")
    args = parser.parse_args(argv)

    as_of = date.today()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = setup_logging(stamp)
    try:
        raw = fetch_company(args.ticker, as_of, SecClient(os.getenv("SEC_USER_AGENT")), DailyCache(as_of))
        if financial_kind((raw.submissions or {}).get("sic")):
            # Said before the paid calls; the run goes on: the analysis can still be useful.
            print(FINANCIAL_NOTE)
        run = run_autopsy(raw, {"horizon": args.horizon, "risk_tolerance": args.risk})
    except (UnknownTickerError, DataUnavailableError, SecAccessError) as e:
        print(f"\nNo analysis: {e}")
        return 2

    out = save_run(run, raw.ticker, as_of, RESULTS, datetime.strptime(stamp, "%Y%m%d_%H%M%S"))
    log_token_summary(run.calls)
    synthesis = run.synthesis
    company = company_display(raw.company_name)
    if synthesis.get("status") == "success":
        print(
            f"\n{company}: {COMMITTEE_VERDICTS[synthesis['verdict']]}. "
            f"Confidence {CONFIDENCE[synthesis['confidence']]}."
        )
    else:
        print(f"\n{company}: no conclusion ({synthesis.get('error')})")
    counts = run.number_check["counts"]
    to_check = sum(v for k, v in counts.items() if k in ("partial", "mismatch", "bad_path"))
    print(
        f"Number check: {counts.get('match', 0)} of {run.number_check['data_claims']} claims "
        f"quoting the data match it; {to_check} need a look."
    )
    print(f"{format_cost(run.total_cost)}; report {out / 'report.md'}; log {log_path}")
    return 0 if synthesis.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
