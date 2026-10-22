# Web UI — agreed design

Recorded on 2026-10-16 from the proposal of 2026-10-15. Same
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
   Each candidate is an exact match (green bar, "✓ Exact match", share
   classes each with their class) or a related company (amber bar, "↔ Related: major investor
   in OpenAI"); anything that cannot be analyzed is grey with its label and reason. Order:
   green, amber, grey; a banner above related companies ("OpenAI is a private company and files
   no reports with the SEC. Related public companies:"); a calm note when nothing is found; red
   with "Try again" only when the lookup model or the SEC list failed. A run started from a
   related card says so in the report title and on the page ("Microsoft Corp (found as a
   company related to OpenAI)"). Every lookup is logged at INFO: the query, the model's
   candidates, what was kept or dropped and why.
2. **Data.** Steps light up: filings and price received, the data pack with real counts
   (annual reports, quarters, filing events, price date), then the DCF calculated by Stock Autopsy ("DCF by Stock Autopsy") with the
   sentence on what today's price assumes. A DCF the data cannot carry (no revenue, no
   share count, debt unknown) reads "DCF not computed: <reasons>" in a neutral notice
   colour; red is kept for a step that really failed. From the moment Analyze is
   pressed the heading and the browser tab name the company ("Analyzing Coca Cola Co (KO)",
   "KO: analyzing… | Stock Autopsy", then the verdict in words).
3. **Analysis (about 3 minutes).** One card per analyst from the start, each with its own
   look: waiting (dimmed, a hollow dot, "Waits for ..."), running (a dot pulsing in the
   page accent and a moving accent line on top), done without a verdict (an accent check
   mark), done with a verdict (a steady lamp and the card top in the verdict colour, the
   verdict word, the confidence and the analyst's one-sentence key finding), failed (red).
   The status colours never reuse the verdict colours. The committee line last,
   then the number check. The server sends a comment line every 15 s while the analysts
   are silent; if the stream drops anyway, the page reopens it from the next event
   (`?since=N`), and if that fails it asks for the result until the server stops answering
   "still running". A lost connection is never shown as a failed run: running cards say
   their status is unknown, the timer goes on, and "Check again" appears if the server
   stays silent. A real failure marks running cards "Stopped" and waiting steps "Not
   reached"; the screen is not reset: it is the only record of where the run stopped. Finished analyses still held
   by the server are listed under "Recent analyses" on the first screen.
4. **Result.** On top: the verdict in words, confidence and its reason, the committee's
   headline, "what the price assumes" (written by Stock Autopsy, not by the AI), and "not advice to buy or
   sell". Then for (3), against (3), what we do not know, what to watch, the conditions.
   Then the number check counter, the analysts (each opens with its claims, each claim
   coloured by what code found: matches the data pack, reproduced by code, found only in a
   table, not in the cited data), "Valuation calculated by Stock Autopsy" (the code's table, not the AI's), data quality in words (most
   important first: a filed quarter missing from SEC company facts, then restatements grouped
   by year, conflicts, notes, rounding, one line for what this version never collects; the
   date the statements reach also stands at the top), the cost table and the glossary
   (both collapsed). "Save report (.md)" sits in the toolbar above the result (item 5) (report.md; the downloaded file is named company first, then the run folder:
   `Coca_Cola_Co_KO_2026-10-17_090436_report.md`; the folder in results/ keeps its ticker-first name). report.json is still written to the run folder for programs,
   but the page does not offer it: it is not for the reader (as in Startup Autopsy).

5. **Translation, on demand.**
   One toolbar at the top of the result: tabs "English report" and one per translated language
   (role tablist; arrow keys, Home and End switch tabs), a language select (Lithuanian first and
   the default, then Startup Autopsy's list; the page remembers the last choice in the browser),
   Translate, and Save, which saves the copy in the open tab (report.lt.md, report.ru.md, named
   company first like the English report). A finished translation gets its tab, is selected and
   the page scrolls to the report; a language translated once is opened, not paid for again, and
   copies on disk come back as tabs when a result is reopened. The translation notes (time, cost,
   sections kept in English with the reason) stand at the top of the tab, above the rendered
   Markdown (raw HTML is never rendered). One cheap call per report section (Haiku 5.5, low
   effort; 0.023-0.031 USD and 41-63 s per report, measured on three reports on 2026-10-17).
   A section must keep its headings, table rows and list items, and every number must come back
   with the same value and scale (`translate/numbers.py`, which reads Russian and Lithuanian
   number formats); a section that fails twice stays in English, marked with the reason in
   words ("Kept in English: ..."). A glossary per language (`translate/glossaries/<language>.md`;
   Russian: 101 terms drafted 2026-10-17, analyst names added 2026-10-21; Lithuanian: the same
   terms drafted 2026-10-22; both awaiting review, Lithuanian by a fluent reader) gives the
   translator its terms. report.md ends with the English glossary (`english.md`) as a collapsed
   `<details>` block of the terms it uses; the translator takes it off and code puts the target
   language's block in its place (the English block and a one-line note when the language has
   no file). The page shows the glossary and the cost table collapsed, in the English view and
   in the translation tab; the files keep the cost table as written, with "done" / "failed"
   (words the glossaries define) instead of a status code. The English report stays the source
   of truth; report.json and the page cards stay English (variant B, translating the cards, is
   not planned). Reports of earlier runs: `python -m translate results/<run> --language
   Lithuanian` (the default).

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
