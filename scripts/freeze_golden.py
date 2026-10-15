"""
Freeze the golden tickers into tests/fixtures/golden/: the raw inputs trimmed to
what the pack reads, and the pack built from them. The golden test rebuilds the
pack from the trimmed inputs and compares it with the frozen one, so any change
in the data layer shows up as a diff to review, without network.

    python -m scripts.freeze_golden 2026-10-15 KO SNOW KHC

Run it again after a deliberate change to the pack, then review the diff of the
frozen packs before committing.
"""

import gzip
import json
import sys
from datetime import date
from pathlib import Path

from datalayer.cache import DEFAULT_ROOT
from datalayer.fetch import RawCompanyData
from datalayer.line_items import ALL_CONCEPTS, SHARES_OUTSTANDING_CONCEPT
from datalayer.pack import build_pack

FIXTURES = Path("tests/fixtures/golden")
SUBMISSION_COLUMNS = ("form", "filingDate", "reportDate", "items")


def trim_facts(company_facts: dict) -> dict:
    keep = {"us-gaap": ALL_CONCEPTS, "dei": {SHARES_OUTSTANDING_CONCEPT}}
    facts = {
        taxonomy: {c: body for c, body in company_facts["facts"].get(taxonomy, {}).items() if c in concepts}
        for taxonomy, concepts in keep.items()
    }
    return {"cik": company_facts.get("cik"), "entityName": company_facts.get("entityName"), "facts": facts}


def trim_block(block: dict) -> dict:
    return {column: block.get(column, []) for column in SUBMISSION_COLUMNS}


def trim_submissions(submissions: dict) -> dict:
    keep = ("name", "sic", "sicDescription", "fiscalYearEnd", "tickers", "exchanges")
    return {
        **{key: submissions.get(key) for key in keep},
        "filings": {"recent": trim_block(submissions["filings"]["recent"]), "files": []},
    }


def write_json_gz(path: Path, data) -> None:
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    # mtime=0: the same data always gives the same bytes, so git sees no change.
    path.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))


def load_raw(directory: Path) -> dict:
    """The trimmed inputs of one golden ticker, as stored by freeze()."""

    def read(name):
        return json.loads(gzip.decompress((directory / f"{name}.json.gz").read_bytes()))

    return {
        name: read(name) for name in ("meta", "companyfacts", "submissions", "older_submissions", "price")
    }


def raw_from_fixture(directory: Path) -> RawCompanyData:
    data = load_raw(directory)
    meta = data["meta"]
    return RawCompanyData(
        ticker=meta["ticker"],
        cik=meta["cik"],
        company_name=meta["company_name"],
        as_of=date.fromisoformat(meta["as_of"]),
        company_facts=data["companyfacts"],
        submissions=data["submissions"],
        price=data["price"],
        older_submissions=data["older_submissions"],
        fetch_status=meta["fetch_status"],
    )


def freeze(day: str, ticker: str) -> None:
    source = DEFAULT_ROOT / day / ticker
    target = FIXTURES / ticker
    target.mkdir(parents=True, exist_ok=True)
    facts = json.loads((source / "companyfacts.json").read_text(encoding="utf-8"))
    submissions = json.loads((source / "submissions.json").read_text(encoding="utf-8"))
    older_files = sorted(source.glob("CIK*-submissions-*.json"))
    older = [trim_block(json.loads(p.read_text(encoding="utf-8"))) for p in older_files]
    price = json.loads((source / "price.json").read_text(encoding="utf-8"))
    meta = {
        "ticker": ticker,
        "cik": int(facts["cik"]),
        "company_name": facts.get("entityName"),
        "as_of": day,
        "fetch_status": {"edgar_companyfacts": "ok", "edgar_submissions": "ok", "yfinance": "ok"},
    }
    write_json_gz(target / "meta.json.gz", meta)
    write_json_gz(target / "companyfacts.json.gz", trim_facts(facts))
    write_json_gz(target / "submissions.json.gz", trim_submissions(submissions))
    write_json_gz(target / "older_submissions.json.gz", older)
    write_json_gz(target / "price.json.gz", price)
    pack, _ = build_pack(raw_from_fixture(target))
    (target / "pack.json").write_text(
        json.dumps(pack, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    size = sum(p.stat().st_size for p in target.iterdir())
    print(f"{ticker}: {size / 1024:.0f} KB in {target}")


if __name__ == "__main__":
    day, *tickers = sys.argv[1:]
    for symbol in tickers:
        freeze(day, symbol)
