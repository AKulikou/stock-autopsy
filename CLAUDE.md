# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**Stock Autopsy** analyzes one US public company (a ticker) from several independent
perspectives and reconciles them in a synthesis, the "Investment Committee". Python
collects the data from official sources (SEC EDGAR) and from a price feed, builds one
**DATA PACK**, and does all the math; the model proposes assumptions, interprets and
argues, but never supplies a number from memory. The report states the strength of the
evidence, the conflicts between perspectives and what to verify next. It is a
research-structuring and learning tool, **not** a buy/sell signal and not investment advice.

Source of truth for the architecture, evaluator prompts, DATA PACK schema and data
quality rules: [docs/stock_autopsy_prompts.md](docs/stock_autopsy_prompts.md). Read it
before changing the data layer, an evaluator or the synthesis; it lists where the code
deviates. If a change would contradict it, stop and ask the author.

The pipeline: Python builds the DATA PACK once per ticker per day (cached, with `as_of`
dates, sources and a `data_quality` block) → the valuation evaluator proposes DCF
assumptions → Python computes the DCF → the other evaluators analyze the byte-identical
pack in parallel → the committee reads their results and decides → code checks every
quoted number against the pack.

## Rules not negotiable without the author's OK

1. **Data first.** Every number in a report comes from the data layer with an `as_of`
   date and a source.
2. **One data pack for all.** Every evaluator gets the byte-identical pack; its hash
   goes into the report.
3. **Python does the math.** Multiples, growth rates, DCF. The model proposes
   assumptions and interprets.
4. **Claim tags.** `[DATA]`, `[DERIVED]`, `[ASSUMPTION]`, `[UNVERIFIED]`.
5. **No buy/sell/hold.** Synthesis verdicts describe the strength of evidence:
   `STRONG_CASE`, `CONDITIONAL_CASE`, `INSUFFICIENT_DATA`, `WEAK_CASE`, `RED_FLAGGED`.
6. **Synthesis is the product.** It looks for productive conflicts, never averages
   verdicts, adds no new facts.
7. **Absent is not zero.** A missing value is `null` with a reason in
   `data_quality.missing`, never `0`.
8. Every report states the data date, the sources and "Not investment advice".

## Commands

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt            # app + pytest + ruff
pytest                                         # unit tests, fake Claude client, no API calls, no network
node --test "tests/js/*.test.mjs"              # the page's own logic (pytest runs it too when Node 22+ is installed)
ruff check .                                   # lint (config in pyproject.toml, target Python 3.10)
python -m datalayer.pack KO                    # fetch SEC + price data and build the DATA PACK (free, no LLM)
python -m scripts.freeze_golden 2026-10-15 KO SNOW KHC CMCSA PLUG  # refreeze golden fixtures; review the diff
python main.py KO                              # full run: 6 Claude calls, results/<ticker>_<date>_<time>/ (paid)
python -m web                                  # local web UI at http://127.0.0.1:8001 (a run is paid as above)
python -m translate results/<run> --language Lithuanian  # translated copy (paid, about 0.03 USD)
python -m eval.run_eval --reps 2 --batch       # eval on the frozen golden packs (paid, about 2.7 USD)
python -m eval.run_eval --variant <name> --summary-only  # recompute a summary, free
python -m eval.run_eval --variant <name> --regrade       # recompute the grounding grades on stored traces, free
```

Requires `ANTHROPIC_API_KEY` and `SEC_USER_AGENT` in `.env` (never commit it). Run
`pytest` and `ruff check .` after any change. No paid API call without the author's
explicit OK; state the expected cost first. `messages.count_tokens` is free.

## Layout

- `docs/stock_autopsy_prompts.md` — source of truth; `docs/web_ui.md` — the page's design;
  `docs/test_companies.md` — golden tickers and what each tests
- `datalayer/` — `sec.py` (throttled SEC client, ticker → CIK), `prices.py` (yfinance:
  close, share count and market cap for cross-checks, splits), `cache.py` (daily cache),
  `fetch.py` (all sources with a status each), `xbrl.py` (facts, forms, periods),
  `extensions.py` (company extension concepts from filing XBRL, receivables only),
  `line_items.py` (pack line items and their us-gaap concepts), `financials.py` (annual
  rows, quarters, TTM, balance sheet, restatements, splits, total debt), `filings.py`
  (filing events, report timing, unsupported filers), `derived.py` (margins, growth,
  multiples), `sector.py` (banks and other financial companies by SIC code),
  `quality.py` (the `data_quality` block), `pack.py` (`build_pack()`, `pack_hash()`)
- `evaluators/` — `definitions.py` (shared rules and the Phase 1 evaluators as data),
  `schemas.py` (structured outputs: verdict block, tagged claims), `validation.py`,
  `paths.py` (pack paths and `resolve()`)
- `valuation/dcf.py` — DCF for bear / base / bull, reverse DCF, implied annual return,
  sensitivities; a missing input or a financial company stops it with a reason
- `synthesis/committee.py` — the committee's schema, principles and validator
- `analysis/runner.py` — `run_autopsy()`: pack → valuation step A → DCF → the other
  evaluators and step B in parallel → committee → number check
- `reporting/` — `number_check.py` and `grounding.py` (DATA claims, calculations, prose
  numbers, unknowns read as zero; the mutation test is in `tests/test_grounding.py`),
  `markdown.py` and `json_export.py` (report.md, report.json), `data_quality.py` (data
  quality for a person), `wording.py` (codes to words, company names; `humanize()` is the
  last pass), `save.py`
- `translate/` — translated copies of report.md: one call per section, number check,
  glossaries in `translate/glossaries/` (`english.md` is report.md's own), languages, CLI
- `web/` — FastAPI app (`app.py`), one run at a time (`runs.py`), name or brand to ticker
  (`resolve.py`), the result in words (`view.py`); `static/` holds the page (shell shared
  with Startup Autopsy plus `live.js`, `lookup.js`, `prefs.js`, `reporttabs.js`,
  `collapsed.js`, `app.js`)
- `core/` — shared Anthropic client, `BatchingClient`, `structured_call.py` (one validated
  structured request), token costs, canonical JSON, parallel calls
- `eval/` — `run_eval.py`, `grading.py`, `judge.py`, `cases.json`, `CHANGES.md` (the log of
  every behaviour change and measurement)
- `scripts/` — `freeze_golden.py`, `check_private_tickers.py`
- `tests/` — pytest with a fake Claude client (`conftest.py`), hand-built XBRL inputs,
  golden fixtures, page tests in `tests/js/`, repository hygiene in `test_repo_hygiene.py`

## Data sources

Checked against the SEC documentation on 2026-10-15; check again before relying on a limit.

| Data | Source | Notes |
|------|--------|-------|
| Ticker → CIK | `https://www.sec.gov/files/company_tickers.json` | CIK is 10 digits with leading zeros |
| Financial facts | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | No API key. Can lag a filing by weeks: the pack checks freshness against the filing history |
| Filing history | `https://data.sec.gov/submissions/CIK##########.json` | Also the SIC code |
| Price, market cap | yfinance, version pinned | Unofficial; can break without notice; cache results |

- SEC fair access: at most 10 requests per second and a declared `User-Agent` with a
  contact email (`SEC_USER_AGENT`); without it the SEC answers 403.
- XBRL traps: the same line item under different tags over the years; `fy`/`fp` describe
  the filing, not the period (periods come from `start`/`end`); fiscal year ≠ calendar year
  and 52/53-week years; quarterly facts mix 3-month and year-to-date values; several values
  for one period from different filings (restatements and recasts).

## Engineering standards

- Production quality: explicit error handling, no silent fallbacks that fabricate data.
- Structured outputs (JSON schema via `messages.parse`) over parsing free text; a
  schema-valid answer can still be garbage, so every structured call has a validator.
- Keep core logic free of CLI I/O, so it can be exposed through an MCP server later.
- Code, comments, docstrings, prompts and commit messages in English.
- Never state an API limit, price or endpoint from memory: check the documentation and
  write down the date it was checked.
- What a person reads (report.md, the page, CLI output) carries no codes: no verdict
  enums, tickers, field names, pack paths or claim tags, only their meaning in words
  (`reporting/wording.py`, scanned by `tests/test_wording.py`). report.json and eval data
  keep the codes for programs.
- Think like a tester: golden tickers, fixtures, and checks that catch a number the model
  did not get from the pack.

## Data rules

- **Absent is not zero.** `canonical_json` refuses NaN and infinity, so a missing number
  cannot slip through as a float. The seven data quality rules are in the source of truth.
- **Context is data, not instructions.** `context_block()` says so in the prompt; text
  inside it is never followed.
- Banks, brokers and insurers (SIC 6021-6099, 6111-6199, 6200-6282, 6311-6411) are flagged:
  their net revenues are read, and EV-, DCF- and cash-flow-based numbers are marked as not
  meaningful. Every other company's pack is unaffected (golden packs stay byte for byte).

## Prompt caching

- Layout: shared rules + data pack first (one cached block), then the evaluator's role
  and focus, then its questions in the user message. Anything that differs between calls
  goes after the breakpoint.
- The cache order is tools → system → messages; a different tool set, effort or thinking
  setting breaks the shared cache. Calls sent at the same moment all miss it, so
  valuation step A runs alone first.
- A different structured-output schema also gives a different prefix: the API renders the
  schema as a system prompt ahead of the breakpoint. Each evaluator has its own schema,
  so each writes its own cache entry. One shared envelope schema (`SHARED_OUTPUT_SCHEMA=on`)
  would save about 14% of a run, but the API refuses it as too large to compile; it stays
  off. The fake client keys its simulated cache on the schema too.
- `usage.input_tokens` excludes cached tokens; `PROMPT_CACHING=off` measures the effect.

## Behavior changes

Every change that can change what the model answers — prompts, evaluators, schemas,
model or request settings, what the pack holds — gets an entry in `eval/CHANGES.md`.
Change one thing at a time when it will be evaluated. Never tune a prompt on a single run.

## Status

Phase 1 is done: data layer, four evaluators, committee, number check, translation,
local web page and the eval on five golden companies.

Release eval `v4_release` (5 cases × 2 reps): primary verdict 5/10, acceptable 9/10,
error cost 0.80 (Kraft Heinz moved from weak to conditional), 6 wrong numbers in 370 data
claims, 209 of 225 calculations reproduced, 2 unknowns read as zero; details in
`eval/CHANGES.md`.

Open:
- The Forensic red-flag call on Plug Power is unstable; Kraft Heinz now lands on the
  acceptable, not the primary, label.
- Prompt cache across evaluators (a schema the API accepts).
- Review of the Lithuanian and English glossaries (drafts).
- 20-F filers, banks valued with P/B and ROE, insider transactions, peers, news and
  transcripts, the remaining evaluators, the DCF sensitivity grid.

## Privacy

- Tickers researched for personal reasons are listed only in `private/companies.md`
  (git-ignored); their reports, logs and caches stay local and never become fixtures,
  eval cases, examples or commit text.
- The guard runs in pytest (skipped where the private list is absent, as in CI) and as
  local hooks, which git does not version; install them in a new clone with:

  ```bash
  printf '#!/bin/sh\nexec venv/Scripts/python.exe -m scripts.check_private_tickers\n' > .git/hooks/pre-commit
  printf '#!/bin/sh\nexec venv/Scripts/python.exe -m scripts.check_private_tickers --commit-msg "$1"\n' > .git/hooks/commit-msg
  ```

## Publication

- Only with the author's OK; the repository is private until CI is green there.
- Push `main` only (`git push origin main`), never `--all` or `--mirror`: refs under
  `refs/agents/` are local Claude Code checkpoints.
- Before a push: the private ticker guard, `tests/test_repo_hygiene.py`, and a scan of
  every commit message, author and patch for personal emails, local paths and keys.

## Known issues

- Only 10-K / 10-Q filers are read; 20-F and 40-F filers and funds are stopped at the
  lookup, before any paid call.
- On Sonnet 5.5 the model thinks adaptively even with `THINKING=off`; `ANALYSIS_EFFORT` is
  the real control. A full run costs about 0.6 USD.
- Evaluators sometimes cite a wrong pack path for a correct number; the number check
  reports it as `bad_path`.
- Company extension concepts are read for receivables only; any other line item a company
  reports under its own concept stays unknown, never zero.
- Total debt is assembled from reported concepts; shapes not in `line_items.py` show up as
  `partial` or missing.
