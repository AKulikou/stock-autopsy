"""
The line items of the DATA PACK and the us-gaap concepts each is read from.

Concepts are listed in order of preference for one filing; across filings the
latest filing wins (see xbrl.preference). The lists come from the concepts the
golden tickers and other candidates actually use (KO, PG, SNOW, RIVN, KHC, MDXG,
PLUG; checked 2026-10-15), not from a generic taxonomy dump.
"""

from dataclasses import dataclass

USD = "USD"
SHARES = "shares"


@dataclass(frozen=True)
class LineItem:
    key: str
    concepts: tuple[str, ...]
    unit: str = USD
    # True when the concepts name the same figure and companies move between them
    # over the years (revenue moved to the ASC 606 concepts): the latest filing
    # wins across concepts, and a value change across concepts is a restatement.
    # False when the concepts differ in definition (cash with or without
    # restricted cash): the first concept reported for the period wins, and
    # values are compared within that concept only.
    concept_migrates: bool = False


# Flows: values over a period (income statement, cash flow statement).
REVENUE = LineItem(
    "revenue",
    (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
    ),
    concept_migrates=True,
)
# Banks and broker-dealers report "net revenues" (revenue after interest expense) under this
# concept (Goldman Sachs, company facts 2026-10-22). Read only for a company flagged by its SIC
# code as financial (datalayer/sector.py), after the general revenue concepts.
FINANCIAL_REVENUE_CONCEPT = "RevenuesNetOfInterestExpense"
REVENUE_FINANCIAL = LineItem(
    "revenue", REVENUE.concepts + (FINANCIAL_REVENUE_CONCEPT,), concept_migrates=True
)
COST_OF_REVENUE = LineItem(
    "cost_of_revenue",
    ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"),
    concept_migrates=True,
)
GROSS_PROFIT = LineItem("gross_profit", ("GrossProfit",))
OPERATING_INCOME = LineItem("operating_income", ("OperatingIncomeLoss",))
NET_INCOME = LineItem("net_income", ("NetIncomeLoss",))
OPERATING_CASH_FLOW = LineItem(
    "operating_cash_flow",
    (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
)
CAPEX = LineItem("capex", ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"))
DEPRECIATION_AMORTIZATION = LineItem(
    "depreciation_amortization",
    (
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
    ),
)
STOCK_BASED_COMPENSATION = LineItem(
    "stock_based_compensation", ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense")
)
INTEREST_EXPENSE = LineItem(
    "interest_expense", ("InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt")
)
DIVIDENDS_PAID = LineItem("dividends_paid", ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"))
SHARE_REPURCHASES = LineItem("share_repurchases", ("PaymentsForRepurchaseOfCommonStock",))
SHARES_DILUTED = LineItem("shares_diluted", ("WeightedAverageNumberOfDilutedSharesOutstanding",), SHARES)

FLOW_ITEMS = (
    REVENUE,
    GROSS_PROFIT,
    OPERATING_INCOME,
    NET_INCOME,
    OPERATING_CASH_FLOW,
    CAPEX,
    DEPRECIATION_AMORTIZATION,
    STOCK_BASED_COMPENSATION,
    INTEREST_EXPENSE,
    DIVIDENDS_PAID,
    SHARE_REPURCHASES,
    SHARES_DILUTED,
)
QUARTERLY_ITEMS = (REVENUE, GROSS_PROFIT, OPERATING_INCOME, NET_INCOME, OPERATING_CASH_FLOW, CAPEX)

# Instants: balances at a date (balance sheet).
CASH = LineItem(
    "cash",
    (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
)
SHORT_TERM_INVESTMENTS = LineItem(
    "short_term_investments",
    (
        "ShortTermInvestments",
        "OtherShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ),
)
ACCOUNTS_RECEIVABLE = LineItem(
    "accounts_receivable", ("AccountsReceivableNetCurrent", "ReceivablesNetCurrent")
)
TOTAL_ASSETS = LineItem("total_assets", ("Assets",))
TOTAL_EQUITY = LineItem(
    "total_equity",
    ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
)

INSTANT_ITEMS = (CASH, SHORT_TERM_INVESTMENTS, ACCOUNTS_RECEIVABLE, TOTAL_ASSETS, TOTAL_EQUITY)

# Debt is reported in many shapes. Each component lists alternatives in order; an
# alternative counts only when every concept in it is reported at that date, and
# the first such alternative is used. Convertible debt counts only when no
# long-term debt alternative is reported (a long-term total usually includes it).
# An alternative marked partial covers only the non-current part.
LONG_TERM_DEBT_ALTERNATIVES: tuple[tuple[tuple[str, ...], bool], ...] = (
    (("LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",), False),
    (("LongTermDebt",), False),
    (("LongTermDebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligationsCurrent"), False),
    (("LongTermDebtNoncurrent", "LongTermDebtCurrent"), False),
    (("LongTermDebtAndCapitalLeaseObligations",), True),
    (("LongTermDebtNoncurrent",), True),
)
CONVERTIBLE_DEBT_ALTERNATIVES: tuple[tuple[tuple[str, ...], bool], ...] = (
    (("ConvertibleDebtNoncurrent", "ConvertibleDebtCurrent"), False),
    (("ConvertibleDebt",), False),
    (("ConvertibleNotesPayable",), False),
    (("ConvertibleDebtNoncurrent",), True),
)
SHORT_TERM_DEBT_ALTERNATIVES: tuple[tuple[tuple[str, ...], bool], ...] = (
    (("ShortTermBorrowings",), False),
    (("CommercialPaper", "OtherShortTermBorrowings"), False),
    (("LoansAndNotesPayable",), False),
    (("CommercialPaper",), False),
    (("OtherShortTermBorrowings",), False),
)
DEBT_CONCEPTS = {
    concept
    for alternatives in (
        LONG_TERM_DEBT_ALTERNATIVES,
        CONVERTIBLE_DEBT_ALTERNATIVES,
        SHORT_TERM_DEBT_ALTERNATIVES,
    )
    for concepts, _ in alternatives
    for concept in concepts
}

SHARES_OUTSTANDING_CONCEPT = "EntityCommonStockSharesOutstanding"  # dei, from the cover page

ALL_CONCEPTS = {
    c for item in (*FLOW_ITEMS, COST_OF_REVENUE, *INSTANT_ITEMS) for c in item.concepts
} | DEBT_CONCEPTS
