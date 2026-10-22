"""
Banks and other financial companies, told by the SEC SIC code in the submissions file.

Their statements do not fit the general model: debt is the raw material of the business, so
enterprise value means little; operating cash flow swings with trading and lending; revenue is
reported net of interest expense. Such a company is flagged before a run (the lookup card, the
CLI) and in the data pack; EV-, DCF- and cash-flow-based numbers are marked as not meaningful.
P/B, ROE and capital ratios, which fit banks, are not implemented (README, known limitations).

Code ranges from the SEC SIC code list,
https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list
(checked 2026-10-22). Real estate (65xx), REITs (6798), blank checks (6770) and royalty traders
(6792, 6795) are not counted: their statements fit the general model better.
"""

FINANCIAL_SIC = (
    (6021, 6099, "bank"),  # national, state and other commercial banks, savings institutions
    (6111, 6199, "credit company"),  # credit agencies and institutions, mortgage bankers, lessors
    (6200, 6282, "broker-dealer or investment adviser"),  # security and commodity brokers, advice
    (6311, 6411, "insurer"),  # life, health, property and casualty insurance, agents and brokers
)
NOT_MEANINGFUL = "not meaningful for a bank or other financial company"
FINANCIAL_NOTE = (
    "Bank or financial company: EV, DCF and cash-flow multiples do not fit how banks report; "
    "the analysis will say so."
)


def financial_kind(sic: str | int | None) -> str | None:
    """'bank', 'credit company', 'broker-dealer or investment adviser', 'insurer', or None."""
    try:
        code = int(str(sic).strip())
    except (TypeError, ValueError):
        return None
    return next((kind for low, high, kind in FINANCIAL_SIC if low <= code <= high), None)
