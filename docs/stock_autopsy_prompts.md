# STOCK AUTOPSY: ANALYTICAL PROMPTS FRAMEWORK

## Overview
Eight independent analytical perspectives + one synthesis agent for evaluating a single public company (ticker).
Each evaluator looks from ONE angle, gets the SAME verified data pack, and returns a structured report.
The synthesis agent (Investment Committee) is the main product — it reconciles conflicts and produces the final verdict.

**What this is:** a research-structuring and learning tool.
**What this is NOT:** a buy/sell signal generator or investment advice.

**Changelog**
- 2026-10-15 — Added "Deviations in the implementation (Phase 1)": owner decisions D3/D4 and the data pack extensions the code uses.
- 2026-10-15 — Data sources checked against SEC documentation (rate limit, User-Agent, CIK format, ticker map); Phase 1 starts from the core shared with Startup Autopsy.
- 2026-10-14 — Data quality rules: "absent is not zero", period and denominator checks. Added the `data_quality` block to the DATA PACK, shared rules 7–8, hooks in Evaluators 2, 3, 4, 5, and data layer tests in the usage notes.

---

## DEVIATIONS IN THE IMPLEMENTATION (PHASE 1, AS OF 2026-10-15)

The sections below stay the design. Where the Phase 1 code differs, this list is
what the code does; each item was decided by the owner or forced by the data.

| Area | This document | Implementation | Why |
|------|---------------|----------------|-----|
| VERDICT block (every evaluator) and committee confidence | `CONFIDENCE: 0-100`, free-text block at the end | Structured-output fields `verdict`, `confidence` LOW / MEDIUM / HIGH, `confidence_reason`, `key_finding`, `biggest_unknown`, `summary` (`evaluators/schemas.py`, `synthesis/committee.py`) | Decision D3: a 0-100 number suggests precision the model does not have; structured output instead of parsing text |
| Claims | Tags in the text | Each evaluator returns a list of `Claim` objects (statement, tag, basis); a DATA claim's basis names pack paths such as `financials_annual.FY2025.revenue`, several separated by `;` | Lets Python check every quoted number against the pack |
| Valuation scope | Peer multiples, sensitivity grid | Python multiples on TTM figures; DCF for bear / base / bull from step A; reverse DCF (implied revenue growth at base-case margins, or a reason it cannot be solved); one-at-a-time sensitivities; no peers, no grid | Decision D4; peers and the grid are Phase 2 |
| Evaluators run | 8 | 4 (Business Model, Forensic, Valuation in two steps, Pre-Mortem); questions that need peers, Form 4 or transcripts answer INSUFFICIENT DATA | Phase 1 scope |
| Committee input | "8 reports + data pack summary" | The four evaluator results, Python's valuation math and a pack summary (company, as_of, price, user context, multiples, `data_quality`); code lowers confidence when the unverified share is high or a perspective is missing | Phase 1 scope; the committee still adds no new facts |
| DATA PACK | Minimal schema above | Extra blocks: `shares_outstanding`, `ttm`, `balance_sheet_latest`, `derived` (Python math with its formulas), `filing_events` (amended reports, late notices, 8-K 4.01 / 4.02), `annual_report_timing`, `sources`, `units`, `schema_version` | Phase 1 evaluators need them; Python does the math |
| `data_quality.missing` | One entry per field and period | One entry per field and reason with a list of periods; extra reason `not_fetched` for insider transactions, peers, news and transcripts (never an empty list) | Shorter pack; "not fetched" is not "none" |
| Report | Not specified | `report.md` in plain words (no codes, tickers or field names) with a number-check section; `report.json` keeps the codes | Owner rule: people read meanings, programs read codes |

---

## WHAT CHANGED VS. THE ORIGINAL TWITTER PROMPTS

| Original | Decision | Why |
|----------|----------|-----|
| Full Stock Research Report (set 1 #1, set 3 #1) | → Evaluator 1 (Business Model) | Split: "report on everything" overlaps with every other prompt |
| Earnings Call Breakdown | → Evaluator 2 | Kept, but requires transcript as input |
| Red Flag Detector + Risk Analysis | → Evaluator 3 (Forensic) | Merged: same skeptical lens |
| Competitive Moat Analysis | → Evaluator 4 | Kept almost as is — strongest original prompt |
| Valuation Comparison + DCF Builder | → Evaluator 5 | Merged; DCF math moved to Python code |
| Management Quality Review | → Evaluator 6 | Kept + capital allocation focus |
| Stock Catalyst Calendar | → Evaluator 7 | Merged with "warning signals after buying" |
| Buy / Sell Decision prompts | → Evaluator 8 (Pre-Mortem) | Reframed: no "buy now", instead "what would prove the thesis wrong" |
| Long-Term Investment Prompt | → split into 4 + 8 | Durability = moat; failure = pre-mortem |
| Bull vs. Bear Debate | → SYNTHESIS agent | Perfect format for synthesis — it IS the aggregation |
| Beginner Stock Checklist | → output mode, not evaluator | "Explain simply" is a rendering style, not a perspective |
| Passive income set (10 prompts) | ❌ Dropped | Not stock analysis; variation of Startup Autopsy |
| Logo/branding (set 3 #7–10) | ❌ Dropped | Copy-paste error by the author; unrelated domain |

---

## CORE ARCHITECTURE PRINCIPLE: DATA FIRST, LLM SECOND

The single biggest weakness of the original prompts: they ask the model to "use recent public sources".
A model's training data is months old, and financial figures change every quarter.
A plausible-looking but wrong number (revenue, share count, debt) silently breaks the whole analysis.

**Rule:** the LLM never supplies numbers from memory. Numbers come from a data layer.

```
1. Data layer (Python) → fetches facts → builds DATA PACK (JSON, with as_of dates and sources)
2. 8 evaluators receive the SAME data pack → analyze, never invent figures
3. Python computes deterministic math (multiples, DCF, growth rates)
4. Synthesis agent receives 8 reports + data pack → final report
```

### Data sources (checked 2026-10-15)

| Data | Source | Notes |
|------|--------|-------|
| Financial statements (10-K/10-Q) | SEC EDGAR APIs: `data.sec.gov/api/xbrl/companyfacts/CIK##########.json`, `data.sec.gov/submissions/CIK##########.json` | Free, official, no API key, US filers only. CIK is 10 digits with leading zeros. Declare a User-Agent with a contact email (kept in `.env`, never committed). SEC fair access: at most 10 requests/second. XBRL data updates within about a minute of a filing |
| Ticker → CIK | `www.sec.gov/files/company_tickers.json` | Official SEC mapping file; cache it |
| Prices, market cap, basic multiples | yfinance | Unofficial, can break without notice — pin the version (1.7.0 is the latest on PyPI, 2026-08-26) and cache results |
| Insider transactions | SEC Form 4 via EDGAR | Free, raw — needs parsing; same rate limit and User-Agent |
| Earnings call transcripts | Usually paid APIs | MVP: user pastes transcript into `inputs/` folder |
| Recent news / catalysts | Claude API web search tool | Must return dated, cited items |

### DATA PACK schema (minimal)

```json
{
  "ticker": "XXXX",
  "as_of": "YYYY-MM-DD",
  "fiscal_year_end": "MM-DD",
  "price": {"value": 0, "source": "...", "date": "..."},
  "financials_annual": [ {"fiscal_year": 0, "revenue": 0, "gross_profit": 0,
                          "operating_income": 0, "net_income": 0, "operating_cash_flow": 0,
                          "capex": 0, "shares_diluted": 0, "total_debt": 0, "cash": 0} ],
  "financials_quarterly": [ ... ],
  "peers": ["AAA", "BBB", "CCC"],
  "peer_multiples": { "AAA": {"pe": 0, "ev_revenue": 0, "ev_ebitda": 0, "p_fcf": 0} },
  "insider_transactions_12m": [ ... ],
  "earnings_transcript": "optional text",
  "news_items": [ {"date": "...", "headline": "...", "source": "..."} ],
  "user_context": {"horizon": "1y|5y|10y", "risk_tolerance": "low|medium|high"},
  "data_quality": {
    "fetch_status": {"edgar_companyfacts": "ok|failed|not_fetched", "form4": "ok|failed|not_fetched",
                     "yfinance": "ok|failed|not_fetched", "transcript": "provided|absent"},
    "missing": [ {"field": "...", "period": "...",
                  "reason": "not_reported|tag_not_found|provider_error|not_applicable"} ],
    "restated": [ {"field": "...", "period": "...", "original": 0, "restated": 0, "filed": "YYYY-MM-DD"} ],
    "source_conflicts": [ {"field": "...", "values": {"edgar": 0, "yfinance": 0}, "used": "edgar"} ],
    "partial": [ {"field": "...", "covers": "..."} ],
    "period_notes": [ "..." ]
  }
}
```

A missing number is `null` with an entry in `data_quality.missing`, never `0`.

---

## DATA QUALITY RULES: ABSENT IS NOT ZERO

Adapted (rewritten, not copied) from Anthropic's knowledge-work-plugins:
`small-business/shared/absent-is-not-zero.md` and `data/skills/validate-data` (Apache 2.0).

**Why.** Test fixtures are complete by construction; real filings and APIs are full of holes.
A hole silently read as zero gives a confident answer that is wrong in the direction that hides
the problem: zero debt, no insider selling, no dilution. The data layer must tell "the company has
none" apart from "we have no figure".

### Rules for the data layer (Python, before the pack is built)

1. **Missing is `null`, never `0`.** Every missing value gets an entry in `data_quality.missing` with a reason.
2. **An implausible zero is unknown.** Revenue, shares outstanding or total assets of 0 for an operating
   company count as missing unless the filing reports the fact with the value 0 explicitly.
3. **An empty result is not a failed fetch.** `insider_transactions_12m: []` means "no transactions" only
   if `fetch_status.form4 == "ok"`; otherwise it is unknown.
4. **A slice is labelled as a slice.** A capped or paginated response (top N, last N filings) goes into
   `data_quality.partial`; totals never come from a slice.
5. **A future date is corrupt.** A period end or filing date after `as_of` is dropped and logged.
6. **Restatements are kept visible.** companyfacts can hold several values for the same period from
   different filings: use the latest filed value and record the earlier one in `data_quality.restated`.
7. **Disagreeing sources are both recorded.** Keep both values in `data_quality.source_conflicts` and state
   which one is used (EDGAR for financial statements, yfinance for price). A gap of an order of magnitude
   is a units or scale bug until proven otherwise.

### Period and denominator checks (Python computes, evaluators respect)

| Pitfall | Example in this project | Check |
|---------|-------------------------|-------|
| Incomplete vs. full period | TTM vs. last fiscal year; quarter-to-date vs. full quarter | Compare only periods of equal length; label TTM explicitly |
| Fiscal year ≠ calendar year | FY ending in June vs. a peer ending in December | Store `fiscal_year_end`; peer comparisons use TTM, not "FY2025" |
| 52/53-week years | An extra week adds ~2% to revenue | Flag 53-week years in `period_notes` |
| Denominator shift: shares | Splits, buybacks, basic vs. diluted | Per-share metrics on diluted, split-adjusted shares; share count and price from the same date |
| Denominator shift: definitions | A non-GAAP metric redefined; segments reorganized | Flag definition changes in `period_notes`; never trend a metric across a redefinition |
| Survivorship | Peers are today's survivors | Sector history excludes failed competitors; Moat and Valuation say so when comparing to peers |

---

## SHARED SYSTEM RULES (prepended to every evaluator)

```
You are one of 8 independent analysts evaluating a public company.
You receive a DATA PACK. Follow these rules strictly:

1. Use ONLY numbers present in the DATA PACK. Never use figures from memory.
2. Tag every claim:
   [DATA]        — directly from the data pack (cite the field)
   [DERIVED]     — calculated from data pack values (show the formula)
   [ASSUMPTION]  — your judgment; state why
   [UNVERIFIED]  — plausible but not in the data pack; must be checked by the user
3. If data needed for a question is missing, say "INSUFFICIENT DATA: <what is missing>".
   Do not guess to fill the gap.
4. State the as_of date of the data you rely on.
5. Never recommend buying, selling or holding. Evaluate the evidence, not the trade.
6. Stay inside your perspective. Other analysts cover other angles.
7. A null field or an entry in data_quality.missing means UNKNOWN, never zero.
   An empty list means "none" only if data_quality.fetch_status shows that fetch succeeded.
   Read data_quality before drawing any conclusion from absent data.
8. Compare like with like: same period length, same share basis, same metric definition.
   Where data_quality.period_notes, restated or source_conflicts affect your conclusion, say so.
9. End with the required VERDICT block exactly as specified.
```

### Standard VERDICT block (every evaluator)

```
VERDICT: [STRONG / ADEQUATE / WEAK / RED_FLAG / INSUFFICIENT_DATA]
CONFIDENCE: [0-100]
KEY_FINDING: <one sentence>
BIGGEST_UNKNOWN: <one sentence — what data would most change this verdict>
SUMMARY: <2-3 sentences>
```

`VERDICT` describes the company **from this evaluator's angle** (e.g. "moat is STRONG"), not whether to buy.

---

## EVALUATOR 1: 🏢 Business Model Analyst

**Focus:** What the company actually does and how it makes money.

**Purpose:** Build the factual foundation all other evaluators implicitly rely on.

**Prompt:**
```
Explain [TICKER]'s business model using the data pack.

1. What does the company sell, to whom, and why do customers pay?
2. Revenue breakdown by segment/geography (if in data). Which segment drives growth,
   which drives profit?
3. Revenue quality: recurring vs. one-time, contract vs. transactional, cyclical exposure.
4. Unit economics: gross margin trend over available years, operating leverage
   (does margin expand as revenue grows?).
5. What are the 2-3 variables that the whole business depends on?
   (e.g. "ad pricing", "copper price", "enterprise IT budgets")
6. What would a reasonable person misunderstand about this business?
```

**Critical:** Describe the business as it is in the numbers, not as management's marketing describes it.

**Output:** Business summary, segment table, key dependency variables, verdict block.

---

## EVALUATOR 2: 📞 Earnings Analyst

**Focus:** Latest quarter — what changed and what management signals.

**Purpose:** Capture the most recent state, which older annual data misses.

**Prompt:**
```
Analyze [TICKER]'s latest reported quarter using the data pack and the earnings transcript.

1. Key metrics table: metric | latest | prior quarter | same quarter last year | change | why it matters.
   Compare complete quarters only; if data_quality.period_notes flag a comparability issue
   (53-week quarter, reorganized segments, redefined metric), mark the affected rows.
2. The 5 most important takeaways, ranked by impact on the investment case.
3. Guidance: raised / maintained / lowered / withdrawn? Compare to prior guidance.
4. Management tone: quote-level evidence of confidence or hedging
   (shift in vocabulary, avoided questions, new caveats).
5. What analysts pushed on during Q&A and whether answers were direct.
6. Positive and negative surprises vs. prior trend.
7. The 3 metrics to watch next quarter and what value would be a warning.

If no transcript is provided, analyze only reported numbers and mark tone analysis
as INSUFFICIENT DATA.
```

**Critical:** One quarter is noise-prone. Flag which changes are likely one-off vs. trend.

**Output:** Metrics table, ranked takeaways, guidance delta, watch-list, verdict block.

---

## EVALUATOR 3: 🔬 Forensic Accountant

**Focus:** Red flags in financial quality and governance.

**Purpose:** Find what the story hides. The skeptical counterweight to all other evaluators.

**Prompt:**
```
Act as a skeptical forensic analyst. Review [TICKER] for red flags:

- Revenue quality: receivables growing faster than revenue? one-off gains?
- Earnings vs. cash: net income vs. operating cash flow gap over years.
- Margins: unexplained jumps or declines.
- Debt: maturity walls, rising interest burden, covenant risk.
- Dilution: diluted share count trend; stock-based compensation as % of revenue.
- Insider activity: net selling/buying in last 12 months, cluster patterns.
- Customer / supplier concentration (if disclosed).
- Accounting: changes in policies, auditor changes, restatements, non-GAAP gap vs. GAAP.
- Restatements and source conflicts recorded in data_quality.restated and data_quality.source_conflicts.
- Denominator and definition shifts: share basis, splits, reorganized segments, redefined metrics
  (data_quality.period_notes).
- Disappearing disclosures: a metric or segment reported in earlier years and no longer reported.
- Legal and regulatory exposure.

For each flag:
| Flag | Evidence (tagged) | Severity 1-5 | Why it matters | Innocent explanation |

Always provide the innocent explanation — a red flag is a question, not a verdict.
Finish with an overall RED FLAG SCORE 1-10 (10 = severe) and justify it.
```

**Critical:** Distinguish "unusual" from "suspicious". Absence of evidence in the data pack ≠ absence of problem.

**Output:** Red flag table, overall score, verdict block (RED_FLAG if any severity-5 item).

---

## EVALUATOR 4: 🏰 Moat Analyst

**Focus:** Durability of competitive advantage.

**Purpose:** Answer "can profits persist for 5-10 years?"

**Prompt:**
```
Analyze the competitive moat of [TICKER] versus [PEERS from data pack].

Score each source 1-5 with evidence:
brand, network effects, switching costs, cost advantage, scale, IP/patents,
distribution, regulation/licenses, proprietary data, customer loyalty.

Then:
1. The 2 strongest advantages and the quantitative evidence for them
   (e.g. margins persistently above peers, stable market share).
2. The 2 most credible threats (technology shift, new entrant, regulation, customer power).
3. Moat trajectory: EXPANDING / STABLE / ERODING — and what evidence would change this.
4. Is high return on capital explained by the moat, or by a cyclical tailwind?
```

**Critical:** A moat must show up in the numbers (sustained excess margins/returns). A moat that exists only in narrative scores ≤2. Peers are today's survivors: when the company looks strong against them, remember that the competitors who failed are not in the comparison.

**Output:** Moat scorecard, peer comparison, trajectory, verdict block.

---

## EVALUATOR 5: 💰 Valuation Analyst

**Focus:** What the current price already assumes.

**Purpose:** Separate "good company" from "good price" — the most common beginner confusion.

**Division of labor:** Python calculates multiples and runs the DCF. The LLM proposes and justifies assumptions and interprets results. Python computes multiples on TTM figures and on diluted, split-adjusted shares dated with the price, and uses the same basis for the company and its peers.

**Prompt (step A — assumptions):**
```
Propose DCF assumptions for [TICKER] for bear / base / bull cases:
revenue growth (years 1-5), operating margin path, tax rate, capex % of revenue,
working capital change, discount rate, terminal growth.

For each assumption: value | reasoning | which historical data point anchors it.
Return as JSON for the calculation engine.
```

**Prompt (step B — interpretation, after Python runs the math):**
```
Given: peer multiples table, DCF results per scenario, sensitivity grid
(discount rate × terminal growth), and current price.

1. Relative valuation: cheap / fair / expensive vs. peers — and whether the premium
   or discount is justified by growth, margins or moat.
2. Reverse DCF: what revenue growth and margin does the CURRENT price imply?
   Is that historically achievable for this company?
3. Which single assumption moves the value the most?
4. What could expand or contract the multiple in the next 12 months?
```

**Critical:** A DCF is a tool for testing assumptions, not for producing a "true value". Always report a range, never a single target price.

**Output:** Multiples table, scenario values, implied expectations, sensitivity, verdict block
(STRONG = price implies modest expectations; WEAK = price requires exceptional execution).

---

## EVALUATOR 6: 👔 Management & Capital Allocation Reviewer

**Focus:** Do the people running the company act like owners?

**Purpose:** Evaluate the decision-makers behind the numbers.

**Prompt:**
```
Evaluate [TICKER]'s leadership. Score each 1-5 with evidence:

1. Guidance accuracy: past guidance vs. actual results.
2. Capital allocation: where did cash go over available years
   (reinvestment, M&A, buybacks, dividends, debt paydown)? Did it create value?
3. Buybacks: executed at reasonable valuations or at peaks? Offset by dilution?
4. Acquisitions: track record, write-downs.
5. Insider ownership and insider trading pattern.
6. Compensation: tied to per-share value creation or to size/adjusted metrics?
7. Communication: transparency on bad news, consistency of narrative across quarters.

Conclude: OWNER-ORIENTED / MIXED / EMPIRE-BUILDING, with the decisive evidence.
```

**Critical:** Judge actions, not statements. Mark CEO/CFO tenure and biography facts as [UNVERIFIED] unless in the data pack.

**Output:** Scorecard, capital allocation breakdown, verdict block.

---

## EVALUATOR 7: 📅 Catalyst & Risk Mapper

**Focus:** What events can move the thesis in the next 3 / 6 / 12 months.

**Purpose:** Turn a static analysis into a monitoring plan.

**Prompt:**
```
Using news_items and data pack, build a catalyst and risk map for [TICKER].

Catalyst table (next 3 / 6 / 12 months):
| Event | Expected timing | Type | Upside if positive | Downside if negative | Confidence | Source/date |

Types: earnings, product launch, investor day, regulatory decision, litigation,
contract, management change, capital return, macro/sector event.

Risk register:
| Risk | Category (company/sector/macro/regulatory/valuation/sentiment) |
  Probability L/M/H | Impact L/M/H | Early warning signal to monitor |

Only include dated events that have a source. Speculative events go into a separate
"UNCONFIRMED" section.
```

**Critical:** This is the most time-sensitive evaluator. Stale or undated items are worse than none.

**Output:** Catalyst calendar, risk register with warning signals, verdict block.

---

## EVALUATOR 8: 💀 Pre-Mortem Analyst (Reality Auditor)

**Focus:** How this investment case fails.

**Purpose:** The equivalent of Startup Autopsy's Reality Auditor. Replaces the original "Buy/Sell Decision" prompts with something honest: not "should I buy", but "what would prove me wrong".

**Prompt:**
```
Imagine it is 3 years from now and [TICKER] has fallen 50% while the market rose.
Write the most plausible explanation.

1. Top 3 failure scenarios, ranked by likelihood, each with the causal chain.
2. For the user's context (horizon: [HORIZON], risk tolerance: [RISK]):
   what makes this company a poor FIT, independent of its quality?
3. Thesis invalidation criteria: 3-5 concrete, measurable signals that would mean
   the investment thesis is broken (e.g. "gross margin below X% for 2 quarters").
4. Which parts of the other analyses are most likely built on shaky data?
5. Checklist of facts the user MUST verify personally before any decision,
   with where to find each (filing type, section).
```

**Critical:** Failure scenarios must be specific to THIS company. Generic risks ("recession", "competition") without a mechanism are not allowed.

**Output:** Failure scenarios, fit assessment, invalidation criteria, verification checklist, verdict block.

---

## SYNTHESIS: ⚖️ Investment Committee

**Focus:** Reconcile 8 perspectives into one honest conclusion.

**Purpose:** This is the product the user actually reads. Gets the largest token budget (3000-4000).

**Input:** All 8 reports + data pack summary + user context.

**Prompt:**
```
You chair an investment committee. You received 8 independent analyst reports on [TICKER].

1. COMMITTEE DEBATE
   - Bull case: the strongest argument, built only from evidence in the reports.
   - Bear case: the strongest counter-argument, same rule.
   - Each side must answer the other's best point.

2. CONFLICT MAP
   Where analysts disagree (e.g. Moat=STRONG vs. Valuation=WEAK) — explain whether
   the conflict is real or the result of different angles. Do not average verdicts.

3. JUDGE'S SUMMARY
   - Which side has stronger evidence and why.
   - What remains genuinely uncertain.
   - Which findings rest on [ASSUMPTION] / [UNVERIFIED] tags.

4. FINAL RESEARCH VERDICT (not a trade recommendation):
   STRONG_CASE        — quality, price and risks all support further interest
   CONDITIONAL_CASE   — attractive IF specific conditions hold (list them)
   INSUFFICIENT_DATA  — key questions cannot be answered with available data
   WEAK_CASE          — evidence does not support the investment thesis
   RED_FLAGGED        — unresolved severe red flags dominate everything else
   CONFIDENCE: 0-100

5. MONITORING PLAN
   Top 5 metrics/events to watch, with thresholds from Evaluators 2, 7, 8.

6. NEXT RESEARCH STEPS
   The 3 specific things to verify next, ordered by how much they could change the verdict.

7. BEGINNER EXPLANATION (optional output mode)
   Explain the conclusion in plain language: what the company does, why it may or may
   not be interesting, and what the reader does not yet know.
```

**Critical:** The synthesis must NOT invent new facts. It may only reason over what evaluators reported.

---

## EVALUATOR MATRIX (overlap control)

| # | Evaluator | Primary question | Time horizon | Most sensitive to stale data |
|---|-----------|------------------|--------------|------------------------------|
| 1 | Business Model | How does it make money? | Structural | Low |
| 2 | Earnings | What changed recently? | Last quarter | **High** |
| 3 | Forensic | What is hidden? | 3-5 years history | Medium |
| 4 | Moat | Will profits persist? | 5-10 years | Low |
| 5 | Valuation | What does the price assume? | Now | **High** |
| 6 | Management | Can we trust decision-makers? | Track record | Medium |
| 7 | Catalysts | What moves it next? | 3-12 months | **Very high** |
| 8 | Pre-Mortem | How does this fail? | 3 years | Low |

**Expected productive conflicts** (the synthesis should look for these):
- Moat STRONG ↔ Valuation WEAK — "great company, priced for perfection"
- Earnings STRONG ↔ Forensic RED_FLAG — "numbers look good, quality questionable"
- Management OWNER-ORIENTED ↔ Pre-Mortem high risk — "good jockey, bad track"

---

## IMPLEMENTATION PHASES (suggested)

**Phase 1 — MVP (start from the shared core extracted from Startup Autopsy):**
Data layer with EDGAR + yfinance, 4 evaluators (Business Model, Forensic, Valuation, Pre-Mortem), Claude-based synthesis from day one.
Parallel evaluator calls and prompt caching of the shared prefix come with the template, so Phase 1 already runs evaluators in parallel.

**Phase 2:**
Remaining 4 evaluators, DCF engine with sensitivity grid, transcript input.

**Phase 3:**
Web search for catalysts, peer comparison runs, re-run on new quarter with diff ("what changed since last autopsy").

---

## USAGE NOTES

- Every report header states: data as_of date, sources, and "Not investment advice".
- Cache the data pack per ticker per day — evaluators must see identical data.
- Log which claims were tagged [UNVERIFIED]; a high share lowers overall confidence automatically.
- Good test cases: one "boring quality" company, one high-growth unprofitable company, one company with a known accounting scandal in its history (tests whether Forensic catches it from numbers alone).
- Data layer tests run on fixtures, without network. Each data quality rule has at least one test:
  - a missing XBRL tag yields `null` plus a `data_quality.missing` entry, never `0`;
  - a failed Form 4 fetch yields `fetch_status.form4 == "failed"`, not an empty "no transactions" list;
  - a restated value keeps the latest filing and records the earlier one;
  - a stock split adjusts per-share history and share counts;
  - a fact dated after `as_of` is dropped;
  - a units mismatch between sources (thousands vs. units) is caught as a source conflict;
  - TTM and fiscal-year figures are never mixed in one multiple.
