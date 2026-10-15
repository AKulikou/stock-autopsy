"""
Keep personal research tickers out of the repository.

Tickers listed in private/companies.md (git-ignored) must not appear in the list
of test companies, in any tracked file (gzipped fixtures included), in a commit
message or in commit authors. The tickers themselves are read from the private
file, so this script names none of them.

    python -m scripts.check_private_tickers                     # files, test list, history
    python -m scripts.check_private_tickers --commit-msg FILE   # a commit message (commit-msg hook)

Exit code 1 and a list of findings on a leak; 0 otherwise, also when there is no
private file (as in CI). tests/test_private_tickers.py runs the same checks.
"""

import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

PRIVATE_LIST = Path("private/companies.md")
TEST_COMPANIES = Path("docs/test_companies.md")
GOLDEN = Path("tests/fixtures/golden")
EVAL_CASES = Path("eval/cases.json")
TICKER_CELL = re.compile(r"^\|\s*([A-Z][A-Z0-9.\-]{0,9})\s*\|")


def tickers_in_table(text: str) -> set[str]:
    """First-column tickers of the Markdown tables in a document (the header 'Ticker' excluded)."""
    found = set()
    for line in text.splitlines():
        match = TICKER_CELL.match(line.strip())
        if match and match.group(1) != "TICKER":
            found.add(match.group(1))
    return found


def private_tickers(path: Path = PRIVATE_LIST) -> set[str]:
    return tickers_in_table(path.read_text(encoding="utf-8")) if path.exists() else set()


def test_company_tickers() -> set[str]:
    listed = (
        tickers_in_table(TEST_COMPANIES.read_text(encoding="utf-8")) if TEST_COMPANIES.exists() else set()
    )
    golden = {p.name for p in GOLDEN.iterdir() if p.is_dir()} if GOLDEN.exists() else set()
    eval_cases = (
        {c["id"] for c in json.loads(EVAL_CASES.read_text(encoding="utf-8"))}
        if EVAL_CASES.exists()
        else set()
    )
    return listed | golden | eval_cases


def pattern(ticker: str) -> re.Pattern:
    """The ticker as a whole word; case-insensitive when it is long enough not to match ordinary words."""
    flags = re.IGNORECASE if len(ticker) >= 3 else 0
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])", flags)


def leaks_in_text(tickers: set[str], text: str) -> set[str]:
    return {t for t in tickers if pattern(t).search(text)}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def file_text(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix == ".gz":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="ignore")


def leaks_in_tracked_files(tickers: set[str]) -> list[str]:
    findings = []
    for name in git("ls-files").splitlines():
        path = Path(name)
        if path.is_file():
            for ticker in leaks_in_text(tickers, file_text(path)):
                findings.append(f"{ticker} in tracked file {name}")
    return findings


def leaks_in_history(tickers: set[str]) -> list[str]:
    findings = []
    for line in git("log", "--all", "--format=%h%x09%an %ae %cn %ce%x09%B%x00").split("\x00"):
        if not line.strip():
            continue
        short = line.strip().split("\t", 1)[0]
        for ticker in leaks_in_text(tickers, line):
            findings.append(f"{ticker} in commit {short} (message or author)")
    return findings


def leaks_in_test_list(tickers: set[str]) -> list[str]:
    return [f"{t} is a private ticker and a test company" for t in sorted(tickers & test_company_tickers())]


def check_all() -> list[str]:
    tickers = private_tickers()
    if not tickers:
        return []
    return leaks_in_test_list(tickers) + leaks_in_tracked_files(tickers) + leaks_in_history(tickers)


def main(argv: list[str]) -> int:
    if argv[:1] == ["--commit-msg"]:
        findings = [
            f"{t} in the commit message"
            for t in leaks_in_text(private_tickers(), Path(argv[1]).read_text(encoding="utf-8"))
        ]
    else:
        findings = check_all()
    for finding in findings:
        print(f"private ticker leak: {finding}", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
