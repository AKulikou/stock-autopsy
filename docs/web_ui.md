# Web UI — agreed design

Recorded on 2026-10-16 from the proposal of 2026-10-15; the owner delegated decisions
D5-D9 and they were taken as proposed (see the decisions table in CLAUDE.md). Same
constraints as Startup Autopsy's v1.0 page: FastAPI plus plain HTML/JS, server-sent
events for progress, bound to `127.0.0.1`, no accounts, history or hosting.

## The point

An AI analysis you can check. The company's own SEC filings, four analysts and a
committee, and every number on the screen traced to a filing or to Python's arithmetic.
The reader is not an analyst: the answer comes first, in plain words, with the analysis
behind it for anyone who wants to look. The answer is a statement about the strength of
the evidence, never "buy" or "sell".

## The page

1. **Choose a company.** One field: company, brand or ticker. Example chips: Coca-Cola,
   Comcast, Kraft Heinz, Snowflake, Plug Power and one brand (KFC). A ticker in capitals
   that the SEC list knows goes straight through (free). Anything else goes to one cheap
   call (Haiku 5.5, a fraction of a cent) that proposes up to three US-listed companies;
   Python keeps only those in the SEC ticker list and shows their SEC names; the person
   picks one. The suggestion is shown as a suggestion and never enters the data pack.
   Honest stop in words when nothing matches ("not in the SEC filer list"). Each candidate's
   SEC filing history is checked for free: a company with no 10-K or 10-Q report (a foreign
   company on Form 20-F or 40-F, a fund) is shown with the reason and cannot be analyzed.
   If an empty data pack is reached any other way, the run stops before the first Claude call.
2. **Data.** Steps light up: filings and price received, the data pack with real counts
   (annual reports, quarters, filing events, price date), then Python's DCF with the
   sentence on what today's price assumes.
3. **Analysis (about 3 minutes).** One card per analyst: grey, then the verdict word,
   the confidence and the analyst's one-sentence key finding. The committee line last,
   then the number check.
4. **Result.** On top: the verdict in words, confidence and its reason, the committee's
   headline, "what the price assumes" (written by Python), and "not advice to buy or
   sell". Then for (3), against (3), what we do not know, what to watch, the conditions.
   Then the number check counter, the analysts (each opens with its claims, each claim
   coloured by what code found: matches the data pack, reproduced by code, found only in a
   table, not in the cited data), Python's valuation table, data quality in words, and
   "Save report" (report.md). report.json is still written to the run folder for programs,
   but the page does not offer it: it is not for the reader (as in Startup Autopsy).

Everything a person reads goes through `reporting/wording.py` (the same last pass as
report.md): no verdict codes, field names, pack paths or tickers.

## Not in this version (later list)

- Translation of the report (D8 allows it as an option; Stock Autopsy has no translator yet).
- A ten-year revenue and operating income chart, and hover details per number (form,
  period, filing date from the provenance).
- Demo resilience: analyzing the latest cached pack when SEC or the price feed fails.
- A shared shell (`tokens.css`, `events.js`, `cards.js`, the event shape) for both
  projects; for now it is a copy of Startup Autopsy's files.
