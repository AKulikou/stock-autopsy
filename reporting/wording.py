"""
Plain words for the report a person reads. The pipeline works with codes
(verdict enums, field names, pack paths, tickers); report.md shows their meaning
instead. report.json keeps the codes: it is data for programs.

`humanize()` is the last pass over the whole report. It also catches codes that
reach the report through the model's own text ("Valuation=WEAK", "business_model
vs pre_mortem", "[DATA]") and through data-quality notes ("accounts_receivable").
"""

import re

COMMITTEE_VERDICTS = {
    "STRONG_CASE": "Strong case: quality, price and risks all support further interest",
    "CONDITIONAL_CASE": "Conditional case: attractive only if specific conditions hold",
    "INSUFFICIENT_DATA": "Not enough data: the key questions cannot be answered with the available data",
    "WEAK_CASE": "Weak case: the evidence does not support the investment thesis",
    "RED_FLAGGED": "Red-flagged: unresolved severe red flags dominate everything else",
}
EVALUATOR_VERDICTS = {
    "STRONG": "strong",
    "ADEQUATE": "adequate",
    "WEAK": "weak",
    "RED_FLAG": "red flag",
    "INSUFFICIENT_DATA": "not enough data",
}
CONFIDENCE = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
STRONGER_SIDE = {"BULL": "the bull case", "BEAR": "the bear case", "BALANCED": "neither side clearly"}
CONFLICT_NATURE = {"REAL": "a real disagreement", "DIFFERENT_ANGLES": "different angles on the same facts"}
CLAIM_TAGS = {
    "DATA": "from the data",
    "DERIVED": "calculated",
    "ASSUMPTION": "assumption",
    "UNVERIFIED": "unverified",
}
EVALUATORS = {
    "business_model": "Business Model Analyst",
    "forensic": "Forensic Accountant",
    "valuation": "Valuation Analyst",
    "valuation_assumptions": "Valuation Analyst (assumptions)",
    "pre_mortem": "Pre-Mortem Analyst",
    "synthesis": "Investment Committee",
}
SOURCES = {
    "edgar_companyfacts": "SEC financial data",
    "edgar_submissions": "SEC filing history",
    "edgar_extensions": "company-specific SEC data",
    "yfinance": "price (Yahoo Finance)",
    "form4": "insider trades",
    "transcript": "earnings call transcript",
}
FETCH_STATUS = {
    "ok": "received",
    "failed": "failed",
    "not_fetched": "not collected in this version",
    "not_needed": "not needed",
    "absent": "not provided",
}
MISSING_REASONS = {
    "not_reported": "not reported in the filings",
    "tag_not_found": "not found in the filings' standard data",
    "provider_error": "the data source failed",
    "not_applicable": "not applicable",
    "not_fetched": "not collected in this version",
}
NUMBER_STATUS = {
    "match": "every number matches the cited data",
    "group_match": "the numbers appear only somewhere in a cited table (weak evidence)",
    "partial": "some numbers are not in the cited data",
    "mismatch": "the numbers are not in the cited data",
    "bad_path": "cites data that does not exist",
    "no_number": "no number to check",
}
FIELDS = {
    "ttm": "last twelve months",
    "capex": "capital expenditure",
    "shares_diluted": "diluted shares",
    "fcf_margin": "free cash flow margin",
    "sbc_to_revenue": "stock-based compensation to revenue",
    "pe": "P/E",
    "ev_revenue": "EV/revenue",
    "ev_ebit": "EV/EBIT",
    "ev_ebitda": "EV/EBITDA",
    "p_fcf": "P/FCF",
    "fcf_yield": "free cash flow yield",
    "financials_annual": "annual figures",
    "financials_quarterly": "quarterly figures",
    "balance_sheet_latest": "latest balance sheet",
    "derived": "calculated",
    "data_quality": "data quality",
    "valuation_math": "valuation math",
    "revenue_cagr_3y": "3-year revenue growth (CAGR)",
    "revenue_cagr_5y": "5-year revenue growth (CAGR)",
    "insider_transactions_12m": "insider transactions (12 months)",
    "as_of": "data date",
    **EVALUATORS,
}
PACK_ROOTS = (
    "financials_annual",
    "financials_quarterly",
    "derived",
    "ttm",
    "balance_sheet_latest",
    "data_quality",
    "filing_events",
    "annual_report_timing",
    "price",
    "shares_outstanding",
    "valuation_math",
    "valuation",
    "user_context",
    "sources",
)

_PATH = re.compile(r"\b(?:" + "|".join(PACK_ROOTS) + r")(?:\.[A-Za-z0-9_]+)+")
_TAG = re.compile(r"\[(DATA|DERIVED|ASSUMPTION|UNVERIFIED)\]")
_CODE = re.compile(
    r"\b(STRONG_CASE|CONDITIONAL_CASE|INSUFFICIENT_DATA|WEAK_CASE|RED_FLAGGED|RED_FLAG|DIFFERENT_ANGLES"
    r"|STRONG|ADEQUATE|WEAK|HIGH|MEDIUM|LOW|DATA|DERIVED|ASSUMPTION|UNVERIFIED)\b"
)
_UPPER_SNAKE = re.compile(r"\b[A-Z]+(?:_[A-Z]+)+\b")
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_YEAR = re.compile(r"^FY\d{4}$")
_QUARTER = re.compile(r"^FY(\d{4})Q([1-4])$")
_QUARTER_TOKEN = re.compile(r"\bFY(\d{4})Q([1-4])\b")

CODE_WORDS = {
    **{code: text.split(":")[0].lower() for code, text in COMMITTEE_VERDICTS.items()},
    **EVALUATOR_VERDICTS,
    **CONFIDENCE,
    "DIFFERENT_ANGLES": "different angles",
    "DATA": "data",
    "DERIVED": "calculated",
    "ASSUMPTION": "assumption",
    "UNVERIFIED": "unverified",
}


def field(name: str) -> str:
    """A field or key name as words: total_debt -> total debt."""
    return FIELDS.get(name, name.replace("_", " "))


def path_words(path: str) -> str:
    """A pack path as words: financials_annual.FY2025.revenue -> annual figures › FY2025 › revenue."""
    words = []
    for part in path.split("."):
        quarter = _QUARTER.match(part)
        if quarter:
            words.append(f"Q{quarter.group(2)} FY{quarter.group(1)}")
        elif _YEAR.match(part):
            words.append(part)
        elif part.isdigit():
            words.append(f"item {int(part) + 1}")
        elif part in EVALUATORS:
            # Inside a path "valuation" is a group of numbers, not the Valuation Analyst.
            words.append(part.replace("_", " "))
        else:
            words.append(field(part))
    return " › ".join(words)


# EDGAR adds a marker after a slash at the end of many names: a state or country code ("/DE/",
# "/MD", "/ CAN"), "/NEW", "/ADR", a place ("/Cayman Islands/"). Measured on the SEC list of
# 2026-10-22: 586 of 10,443 titles; a slash inside a name ("A/S", "M/I", "I/O", "Quad/Graphics")
# is followed by one letter or more name and is not touched. The data pack keeps the full name.
_EDGAR_SUFFIX = re.compile(r"\s*/\s*(?:[A-Za-z]{2,6}|[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)?\s*/?\s*$")


def company_display(name: str) -> str:
    """
    A company name as a person reads it: the EDGAR suffix removed ("COSTCO WHOLESALE CORP /NEW"
    -> "Costco Wholesale Corp"), names in capitals in title case.
    """
    name = _EDGAR_SUFFIX.sub("", name).strip() or name
    return name.title() if name.isupper() else name


def company_heading(name: str, related_to: str | None = None) -> str:
    """
    The company as a heading names it: "Microsoft Corp (found as a company related to
    OpenAI)" when the person picked it as a company related to what they typed.
    """
    company = company_display(name)
    return f"{company} (found as a company related to {related_to})" if related_to else company


# Tickers that are also ordinary words, abbreviations or codes in report text. Such a
# ticker is replaced only where it cannot be the word: "LOW's", "(T)", "IT shares".
# Single letters are always treated so ("A strong year").
TICKERS_THAT_ARE_WORDS = {
    "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF", "IN", "IS", "IT", "ME", "MY", "NO", "OF",
    "OK", "ON", "OR", "SO", "TO", "UP", "US", "WE", "AI", "EV", "PE", "CEO", "CFO", "USA", "GDP",
    "ALL", "ANY", "ARE", "BIG", "CAN", "CASH", "FAST", "FIVE", "FOR", "FUN", "GOOD", "HAS", "HOME",
    "KEY", "LIFE", "LOW", "MAIN", "NEW", "NOW", "ONE", "OPEN", "OUT", "PAY", "REAL", "SAFE", "SEE",
    "TRUE", "TWO", "WELL", "YOU", *CODE_WORDS,
}
_TICKER_CONTEXT = r"(?:'s\b|\s+(?:shares|stock|stockholders|shareholders|common\s+stock)\b)"
# Spans no pass may rewrite: URLs, file names, long hex hashes.
_PROTECTED = re.compile(
    r"https?://[^\s)>\]]+"
    r"|\b(?:[\w.-]+/)*[\w.-]+\.(?:json|md|csv|txt|html?|xml|pdf|zip|gz)\b"
    r"|\b[0-9a-f]{16,}\b"
)


def _replace_ticker(text: str, ticker: str, company: str) -> str:
    name = re.escape(ticker)
    if len(ticker) == 1 or ticker in TICKERS_THAT_ARE_WORDS:
        text = re.sub(rf"\b{name}(?={_TICKER_CONTEXT})", company, text)
        return re.sub(rf"(?<=\(){name}(?=\))", company, text)
    return re.sub(rf"(?<![\w.$]){name}\b(?![.-]\w)", company, text)


def humanize(text: str, ticker: str | None = None, company: str | None = None) -> str:
    """Replace codes with words in report text (see the module docstring)."""
    protected: list[str] = []

    def protect(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    text = _PROTECTED.sub(protect, text)
    # The ticker goes first, so a ticker that is also a code word (LOW) becomes the
    # company name before the code pass lowers it.
    if ticker and company:
        text = _replace_ticker(text, ticker, company)
    text = _TAG.sub(lambda m: f"({CLAIM_TAGS[m.group(1)]})", text)
    text = _PATH.sub(lambda m: path_words(m.group(0)), text)
    text = _CODE.sub(lambda m: CODE_WORDS[m.group(1)], text)
    text = _UPPER_SNAKE.sub(lambda m: m.group(0).lower().replace("_", " "), text)
    text = _SNAKE.sub(lambda m: field(m.group(0)), text)
    text = _QUARTER_TOKEN.sub(lambda m: f"Q{m.group(2)} FY{m.group(1)}", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], text)
