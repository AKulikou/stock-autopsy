# Glossary

English glossary for report.md and the English page (translate/glossary.py): the term as reports
write it, the term as the glossary shows it, and a plain explanation. The same terms as the Russian
and Lithuanian glossaries; written by Claude Code on 2026-10-22 from the Russian explanations,
for the owner's review. Only the terms a report uses are shown with it. The numbered headings
group the rows for review and are ignored by the code.

## 1. Filings and sources

| English | Term | Explanation |
|---|---|---|
| SEC | SEC (U.S. Securities and Exchange Commission) | The U.S. stock market regulator. Public companies file their reports with it, and it publishes them in the EDGAR system. |
| 10-K | annual report (10-K) | A U.S. company's detailed annual report to the SEC, with financial statements audited by an auditor. The main data source of this system. |
| 10-Q | quarterly report (10-Q) | A quarterly report to the SEC. The auditor only reviews it; it is not a full audit. |
| 8-K | current report (8-K) | A notice of an important event between scheduled reports: a change of auditor, a large deal, a departing executive, an admission of errors in the accounts. |
| 10-K/A / 10-Q/A | amended report (10-K/A, 10-Q/A) | A correction to a report already filed. Often harmless, for example adding executive pay details (Part III); sometimes it corrects errors, and then it matters. |
| 20-F | foreign issuer's annual report (20-F) | The annual report of a foreign company whose shares trade in the U.S. This version of the system does not read it. |
| NT 10-K / NT 10-Q / late filing | notice of a late filing | The company says it will not file a report on time. Not a violation in itself, but repeated delays are a warning sign. |
| XBRL / company facts | machine-readable filing data (XBRL) | The numbers of the filings in a format a program can read. The system takes its data from here, not from the model's memory. |
| fiscal year / FY | fiscal year (FY) | The company's reporting year. It may differ from the calendar year, for example ending in September or at the end of November. |
| TTM / last twelve months | last twelve months (TTM) | A figure for the last four quarters. The system computes it as the last annual report plus this year's quarters minus the same quarters of last year. |
| restatement / restated | restatement (correction of errors) | The company corrects numbers it published earlier because they were wrong. A serious sign when judging the quality of the accounts. |
| recast | recast of past figures | Past figures shown again because of new segments, a new accounting standard or the sale of part of the business. Not an error but normal practice; not to be confused with a restatement. |
| non-reliance / Item 4.02 | non-reliance notice (8-K, Item 4.02) | The company or its auditor says the financial statements published earlier can no longer be relied on and will be corrected. One of the strongest red flags. |
| material weakness | material weakness in internal control | An admission that the controls over the accounts could miss a material error. A reason to treat the numbers with more care. |
| going concern | going-concern doubt | The report says outright that there is substantial doubt the company will keep operating for another 12 months. One of the most serious signals. |
| auditor change / Item 4.01 | auditor change (8-K, Item 4.01) | Often routine. A concern when it comes with disagreements with the auditor. |
| GAAP / non-GAAP / adjusted | U.S. GAAP / adjusted (non-GAAP) figures | U.S. GAAP are the U.S. accounting standards. Adjusted figures are computed by the company itself, usually leaving out "one-off" costs, so they almost always look better than the GAAP figures. |

## 2. Revenue, profit and margins

| English | Term | Explanation |
|---|---|---|
| revenue | revenue | All the money from sales in a period, before any costs are deducted. |
| gross profit / gross margin | gross profit / gross margin | Revenue minus the cost of what was sold. The margin is its share of revenue: how much is left of each dollar of sales before other costs. |
| operating income / operating margin | operating income / operating margin | Profit from the main business after all operating costs, before interest and taxes. The margin is its share of revenue. |
| net income / net margin | net income / net margin | Profit after all costs, interest and taxes. The margin is its share of revenue. |
| EBIT | EBIT (earnings before interest and taxes) | Close to operating income. Used in the EV/EBIT multiple. |
| EBITDA | EBITDA (earnings before interest, taxes, depreciation and amortization) | Operating income plus depreciation and amortization. A rough measure of the cash from the main business; it ignores the cost of replacing equipment, so it can flatter the picture. |
| EPS / earnings per share | earnings per share (EPS) | Net income divided by the number of shares. |
| one-off / one-time | one-off items | Income or costs the company says will not recur. If "one-off" costs show up every year, be wary. |
| earnings quality | earnings quality | How far profit is backed by real cash rather than accounting estimates and one-off effects. |
| operating leverage | operating leverage | With high fixed costs, profit rises and falls faster than revenue. |
| segment | segment | A line of business the company reports separately (by product or region). |
| cyclical | cyclical business | A business whose revenue and profit depend strongly on the phase of the economic cycle (cars, commodities, construction). |

## 3. Cash flow and working capital

| English | Term | Explanation |
|---|---|---|
| operating cash flow | operating cash flow | The cash the main business actually brought in during the period. If profit stays above it for years, find out why. |
| capital expenditure / capex | capital expenditure (capex) | Money spent on buildings, equipment and other long-lived assets. |
| free cash flow / FCF | free cash flow (FCF) | Operating cash flow minus capital expenditure: the cash that can go to dividends, buybacks or paying down debt. |
| working capital | working capital | Money tied up in day-to-day operations: inventories and customers' debts minus debts to suppliers. When it grows, it temporarily "eats" cash flow. |
| receivables / accounts receivable | receivables | Money customers owe the company for goods already sold. If receivables grow faster than revenue, sales may be recognised aggressively. |
| inventories | inventories | Goods and materials in stock. A sharp rise while sales are slow is a warning sign. |
| deferred revenue | deferred revenue | Money received from customers in advance for what has not been delivered yet. Usually a good sign of demand. |

## 4. Debt and liquidity

| English | Term | Explanation |
|---|---|---|
| net debt | net debt | Debt minus cash: what the company would still owe if it used all its cash to repay debt. |
| leverage | leverage | How large debt is compared with profit. Often measured as net debt / EBITDA: how many years of such profit it would take to repay the debt. |
| interest expense | interest expense | How much interest the company pays on its debt in a year. |
| interest coverage | interest coverage | How many times operating income covers the interest expense. The higher, the safer. |
| maturities / refinancing | maturities / refinancing | When debt must be repaid, and whether the company can borrow again on acceptable terms. Maturities are not loaded into the system's data. |
| liquidity / cash runway | liquidity / cash runway | Whether there is enough cash for current payments. The runway is how many months the cash lasts at the current losses. |
| cash burn | cash burn | How much more cash the company spends than it earns. Typical of growing, loss-making companies. |

## 5. Shares and shareholders

| English | Term | Explanation |
|---|---|---|
| market cap / market value | market capitalization | The share price times the number of shares: what the market values all the equity at. |
| shares outstanding / share count | shares outstanding | How many of the company's shares the shareholders hold. |
| diluted shares | diluted share count | The number of shares including options and other securities that can become shares. |
| dilution | dilution | The company issues new shares and each shareholder's stake shrinks. Repeated dilution usually means the company lives on selling shares. |
| stock-based compensation / SBC | stock-based compensation (SBC) | Paying staff in shares or options. No cash leaves, but it is a real cost to shareholders: their stake is diluted. |
| buyback / repurchase | share buyback | The company buys its own shares on the market, and the remaining shareholders' stake grows. Useful when the price is sensible. |
| dividend / payout ratio | dividend / payout ratio | A payment to shareholders out of profit. The payout ratio is the share of profit paid as dividends; above 100% the dividend is not paid out of current profit. |
| stock split / reverse split | stock split / reverse split | A split turns one share into several without changing the value of a stake. A reverse split turns several shares into one, often done by companies whose price fell very low. |
| spin-off | spin-off | Part of the company becomes a separate company and its shares go to the shareholders. The share price then drops by the value of that part, but it is not a split. |

## 6. Valuation

| English | Term | Explanation |
|---|---|---|
| valuation | valuation | An attempt to work out what the company is worth and to compare it with the market price. |
| multiple / valuation multiple | valuation multiple | The ratio of the price (or the company's value) to a measure such as profit, revenue or cash flow. A quick way to compare how "expensive" companies are. |
| P/E / price to earnings | P/E (price to earnings) | Market capitalization divided by net income: how many years of current profit the company costs. |
| P/FCF | P/FCF (price to free cash flow) | Like P/E, but on free cash flow, which is harder to dress up with accounting. |
| FCF yield | free cash flow yield | Free cash flow divided by market capitalization: what percent of the price the company earns in free cash in a year. The inverse of P/FCF. |
| enterprise value / EV | enterprise value (EV) | Market capitalization plus debt minus cash: the price of the whole business including its debts. Lets companies with different debt be compared. |
| EV/Revenue / EV/EBIT / EV/EBITDA | EV/Revenue, EV/EBIT, EV/EBITDA | Multiples comparing enterprise value with revenue or profit. |
| equity value | equity value | Enterprise value minus debt plus cash: the part that belongs to shareholders. |
| value per share | value per share | Equity value divided by the number of shares. In the report it is a range for testing assumptions, not a price target. |
| DCF / discounted cash flow | discounted cash flow (DCF) | The company valued as the sum of its future free cash flows, brought back to today. Very sensitive to assumptions. Stock Autopsy calculates it in code, not the model. |
| discount rate | discount rate | The yearly return required, used to bring future money back to today. The higher the rate, the lower the value. |
| terminal value / terminal growth | terminal value / terminal growth | The value of all cash flows after the forecast years, assuming steady growth. Often most of the whole valuation, so it depends heavily on assumptions. |
| bear case / base case / bull case | bear / base / bull case | Three sets of assumptions (revenue growth, margin and so on) from which Stock Autopsy calculates three values. |
| implied annual return / implied return | implied annual return | The yearly return a buyer at today's price earns if the base case comes true: the rate at which the DCF value equals the price. The system's main valuation figure. |
| what the price assumes / price assumes | what the price assumes | A sentence Stock Autopsy writes: at what price, with which assumptions and for what return a buyer comes out ahead. |
| reverse DCF | reverse DCF | The inverse question: what revenue growth would make the DCF value equal today's price. If it is higher than anything the company has shown, the price asks too much. |
| sensitivity | sensitivity | How much the valuation changes when one assumption (rate, growth, margin) moves one step up or down. |
| CAGR | compound annual growth rate (CAGR) | The steady yearly growth that would give the same result over the period as the actual growth. |
| hurdle rate | hurdle rate | The return below which an investment is not worth making. |
| margin of safety | margin of safety | The gap between the estimated value and the price. It protects against mistakes in the assumptions. |
| priced in | priced in | Market expectations already reflected in today's share price. |

## 7. Business and competition

| English | Term | Explanation |
|---|---|---|
| moat | moat (a lasting competitive advantage) | What keeps competitors from taking the profit for years: brand, switching costs, network effect, scale, patents. |
| pricing power | pricing power | The ability to raise prices without losing customers. |
| switching costs | switching costs | How costly or hard it is for a customer to move to a competitor. |
| network effect | network effect | A product becomes more valuable as more people use it. |
| economies of scale | economies of scale | The larger the volume, the lower the cost per unit. |
| backlog | backlog | Orders already received but not yet fulfilled. |
| catalyst | catalyst | An event that can noticeably change how the market values the company: a report, a deal, a regulator's decision. |

## 8. Terms of the system itself

| English | Term | Explanation |
|---|---|---|
| Strong case | Strong case | The committee's highest verdict: the evidence supports the investment thesis well. It is not a recommendation to buy. |
| Conditional case | Conditional case | The thesis holds only if the named conditions are met. |
| Weak case | Weak case | The evidence does not support the thesis, for example a good business whose price leaves too little return. |
| Insufficient data | Insufficient data | The key questions cannot be settled with the data available. |
| Red-flagged | Red-flagged | Unresolved serious problems outweigh everything else. |
| strong / adequate / weak / red flag (analyst verdicts) | strong / adequate / weak / red flag | The verdicts of the single analysts on their narrow topic. |
| confidence | confidence | How sure the system is of its verdict, given the gaps in the data. Not the same as the strength of the case. |
| from the data / calculated / assumption / unverified | from the data / calculated / assumption / unverified | The label of each analyst's claim: a number from the data; a number calculated from the data; an assumption; a statement the data cannot confirm. |
| number check | number check | Code, not the model, compares the numbers in the claims with the data and recalculates the formulas. A match shows the claim agrees with the data pack, not that the data are right. |
| data pack | data pack | All the numbers about the company that Stock Autopsy collected from the SEC and Yahoo for one date. Every analyst gets the same pack. |
| red flag / severity | red flag / severity (1-5) | A suspicious point in the accounts or the management. Each flag has an innocent explanation too; severity 5 is the highest. |
| done / failed (call status in the cost table; added 2026-10-22) | done / failed | Whether a call to the model ended with a usable answer. A failed call is listed with its cost, because a rejected answer is billed too. |

## Analysts and committee

| English | Term | Explanation |
|---|---|---|
| Business Model Analyst | Business Model Analyst | Examines how the company makes money and how durable its income is. |
| Earnings Analyst | Earnings Analyst | Examines the quarterly report and its earnings call. Not part of this version: transcripts are not collected. |
| Forensic Accountant | Forensic Accountant | Looks for signs of trouble in the quality of the accounts and in how the company is run. |
| Moat Analyst | Moat Analyst | Judges what protects the business from competitors and how long that protection will last. Not part of this version. |
| Valuation Analyst | Valuation Analyst | Proposes the assumptions for three scenarios (Stock Autopsy calculates the DCF from them) and interprets the result. |
| Valuation Analyst (assumptions) (step A) | Valuation Analyst (assumptions) | The valuation analyst's first step: the assumptions for three scenarios from which Stock Autopsy calculates the DCF. |
| Management & Capital Allocation Reviewer | Management & Capital Allocation Reviewer | Judges the management and how the company spends money: investments, acquisitions, dividends, buybacks. Not part of this version. |
| Catalyst & Risk Mapper | Catalyst & Risk Mapper | Draws up a calendar of events that could move the price and of signals worth watching. Not part of this version. |
| Pre-Mortem Analyst | Pre-Mortem Analyst | Imagines the investment failed a few years from now and describes the most likely causes. |
| Investment Committee | Investment Committee | The synthesis: brings the analysts' findings together, looks for conflicts between them and gives the final verdict. Adds no new facts. |
