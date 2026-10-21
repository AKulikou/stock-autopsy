# Web UI — agreed design

Recorded on 2026-10-16 from the proposal of 2026-10-15; the owner delegated decisions
D5-D9 and they were taken as proposed (see the decisions table in CLAUDE.md). Same
constraints as Startup Autopsy's v1.0 page: FastAPI plus plain HTML/JS, server-sent
events for progress, bound to `127.0.0.1`, no accounts, history or hosting.

## The point

An AI analysis you can check: built on SEC filings and market prices, with every quoted
number checked against the data. (The check proves that a quoted number matches the data
pack, not that each number goes back to a filing: the price and the market value come from
Yahoo Finance.)
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
   sentence on what today's price assumes. A DCF the data cannot carry (no revenue, no
   share count, debt unknown) reads "DCF not computed: <reasons>" in a neutral notice
   colour; red is kept for a step that really failed (M8). From the moment Analyze is
   pressed the heading and the browser tab name the company ("Analyzing Coca Cola Co (KO)",
   "KO: analyzing… | Stock Autopsy", then the verdict in words, M11).
3. **Analysis (about 3 minutes).** One card per analyst from the start, each with its own
   look (M9): waiting (dimmed, a hollow dot, "Waits for ..."), running (a dot pulsing in the
   page accent and a moving accent line on top), done without a verdict (an accent check
   mark, M10), done with a verdict (a steady lamp and the card top in the verdict colour, the
   verdict word, the confidence and the analyst's one-sentence key finding), failed (red).
   The status colours never reuse the verdict colours. The committee line last,
   then the number check. The server sends a comment line every 15 s while the analysts
   are silent; if the stream drops anyway, the page reopens it from the next event
   (`?since=N`), and if that fails it asks for the result until the server stops answering
   "still running". A lost connection is never shown as a failed run: running cards say
   their status is unknown, the timer goes on, and "Check again" appears if the server
   stays silent. A real failure marks running cards "Stopped" and waiting steps "Not
   reached"; the screen is not reset (owner's decision, M6). Finished analyses still held
   by the server are listed under "Recent analyses" on the first screen.
4. **Result.** On top: the verdict in words, confidence and its reason, the committee's
   headline, "what the price assumes" (written by Python), and "not advice to buy or
   sell". Then for (3), against (3), what we do not know, what to watch, the conditions.
   Then the number check counter, the analysts (each opens with its claims, each claim
   coloured by what code found: matches the data pack, reproduced by code, found only in a
   table, not in the cited data), Python's valuation table, data quality in words (most
   important first: a filed quarter missing from SEC company facts, then restatements grouped
   by year, conflicts, notes, rounding, one line for what this version never collects; the
   date the statements reach also stands at the top, M2), and
   "Save report (.md)" (report.md; the downloaded file is named company first, then the run folder:
   `Coca_Cola_Co_KO_2026-10-17_090436_report.md`; the folder in results/ keeps its ticker-first name). report.json is still written to the run folder for programs,
   but the page does not offer it: it is not for the reader (as in Startup Autopsy).

5. **Translation, on demand (M13, variant A).** Below the result: a language select
   (Russian first, then Startup Autopsy's list) and "Translate report". One cheap call per
   report section (Haiku 5.5, low effort; 0.023-0.031 USD and 41-63 s per report, measured on
   three reports on 2026-10-17). A section must also keep its headings, table rows and list
   items. The translated copy appears on the page as
   rendered Markdown (raw HTML is never rendered) and as "Save report in Russian
   (.md)" (report.ru.md, named company first like the English report). Every number of a section must come back with the same value and scale
   (`translate/numbers.py`); a section that fails the check twice stays in English, marked with
   the reason in words ("Kept in English: ..."), and the page names it under the translation.
   A glossary per language (`translate/glossaries/<language>.md`; Russian only so far, 96
   terms drafted on 2026-10-17 and awaiting the owner's review) gives the translator its
   terms and is appended as a final section with the terms the report uses. The English
   report stays the source of truth; report.json and the page cards stay English (variant B,
   translating the cards, is not planned). Reports of earlier runs:
   `python -m translate results/<run> --language Russian`.

Everything a person reads goes through `reporting/wording.py` (the same last pass as
report.md): no verdict codes, field names, pack paths or tickers. The ticker appears only
next to the company's name, where it identifies the run: the live heading, the browser tab
and the downloaded file name.

## Not in this version (later list)

- A ten-year revenue and operating income chart, and hover details per number (form,
  period, filing date from the provenance).
- Demo resilience: analyzing the latest cached pack when SEC or the price feed fails.
- A shared shell (`tokens.css`, `events.js`, `cards.js`, the event shape) for both
  projects; for now it is a copy of Startup Autopsy's files.
