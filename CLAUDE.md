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
before changing the data layer, an evaluator or the synthesis. If a change would
contradict it, stop and ask the owner.

The shape of the pipeline:

1. Python builds the **DATA PACK** once per ticker per day (cached), with `as_of`
   dates, sources and a `data_quality` block.
2. Independent **evaluators** (perspectives) analyze the byte-identical pack, each
   from one angle, each returning structured output.
3. Python computes multiples and the DCF; the valuation evaluator proposes the
   assumptions first and interprets the results after.
4. A **synthesis** call reads the evaluator results and decides; it adds no new facts.

## Rules not negotiable without the owner

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
ruff check .                                   # lint (config in pyproject.toml, target Python 3.10)
python -m datalayer.fetch KO                   # fetch SEC + price data for one ticker into data_cache/ (free, no LLM)
python -m datalayer.pack KO                    # build the DATA PACK (+ provenance) into data_cache/ (free, no LLM)
python -m scripts.freeze_golden 2026-10-15 KO SNOW KHC  # refreeze golden fixtures from data_cache/; review the diff
python main.py KO                              # full run: 6 Claude calls, results/<ticker>_<date>_<time>/ (paid)
python -m eval.run_eval --cases KHC --reps 1   # eval on frozen golden packs (paid, ~0.6 USD per attempt)
python -m eval.run_eval --reps 2 --batch       # all cases through Message Batches (half price, slower)
python -m eval.run_eval --variant baseline --summary-only  # recompute a summary, free
python -m eval.run_eval --variant baseline --rejudge        # rerun only the judge on stored traces (~0.001 USD each)
python -m examples.minimal_run                 # smallest real run, a few cents (paid)
```

Requires `ANTHROPIC_API_KEY` and `SEC_USER_AGENT` in `.env` (never commit it). Run
`pytest` and `ruff check .` after any change. No paid API call without the owner's
explicit OK; state the expected cost first. `messages.count_tokens` is free.

## Layout

- `docs/stock_autopsy_prompts.md` — source of truth (see above)
- `docs/test_companies.md` — golden tickers and candidates, with what each tests; personal research tickers live in git-ignored `private/` and never appear in tracked files, commits or fixtures
- `scripts/check_private_tickers.py` — refuses private tickers in the test list, tracked files (gzipped fixtures too), commit messages and authors; run by `tests/test_private_tickers.py` and the local git hooks (see Privacy)
- `datalayer/sec.py` — `SecClient`: throttled SEC GETs (User-Agent check, one retry on transient errors), ticker → CIK
- `datalayer/prices.py` — last close before `as_of`, Yahoo's share count and market cap (cross-checks only), splits; via yfinance
- `datalayer/cache.py` — `DailyCache`: `data_cache/<as_of>/...json`, atomic writes
- `datalayer/fetch.py` — `fetch_company()`: all sources through the cache, `fetch_status` per source (company facts required; filings and price may fail and are recorded); CLI
- `datalayer/http.py` — stdlib GET with gzip; the getter is a parameter so tests never reach the network
- `datalayer/xbrl.py` — `Fact`, statement forms (proxy statements ignored), period lengths, value preference, materiality of a change
- `datalayer/extensions.py` — company extension concepts from filing XBRL instances (company facts lack them): when to fetch, which filings, parsing, a strict receivables matcher (case variants are one concept; two candidates = ambiguous, none used)
- `datalayer/line_items.py` — pack line items and the us-gaap concepts each is read from; debt alternatives
- `datalayer/financials.py` — `Financials`: annual rows (10 fiscal years), discrete quarters, TTM, latest balance sheet, restatements, split adjustment, total debt
- `datalayer/filings.py` — filing events (amended reports, late notices, 8-K 4.01/4.02) and annual report timing
- `datalayer/derived.py` — margins, growth, FCF, valuation multiples on TTM (`FORMULAS`)
- `datalayer/quality.py` — `DataQuality`: the `data_quality` block (missing with reason, restated, conflicts, partial, notes)
- `datalayer/pack.py` — `build_pack()` → (pack, provenance), `pack_hash()`, freshness and source cross-checks; CLI
- `scripts/freeze_golden.py` — freezes trimmed inputs + packs of the golden tickers into `tests/fixtures/golden/`
- `evaluators/definitions.py` — `SHARED_RULES` and the Phase 1 evaluators as `Perspective` data (Business Model, Forensic, Valuation steps A and B, Pre-Mortem)
- `evaluators/schemas.py` — structured outputs: the verdict block (D3), tagged `Claim`s with a basis, per-evaluator fields, DCF scenario assumptions
- `evaluators/validation.py` — validators per evaluator: lengths and counts, DATA claims must name an existing pack path, RED_FLAG iff a severity-5 flag, sane and ordered DCF assumptions
- `evaluators/paths.py` — pack paths (`financials_annual.FY2025.revenue`) and `resolve()`
- `valuation/dcf.py` — DCF for bear/base/bull, reverse DCF (implied growth), one-at-a-time sensitivities; a missing input stops it with a reason
- `synthesis/committee.py` — Investment Committee schema, principles, validator; code lowers confidence for a high UNVERIFIED share or a missing perspective
- `analysis/runner.py` — `run_autopsy()`: pack → valuation step A (warms the cache) → DCF → the other evaluators and step B in parallel → committee → number check
- `reporting/number_check.py` — every number in a DATA claim must match the pack value at its basis (precision-aware)
- `reporting/markdown.py`, `reporting/json_export.py` — `report.md` (committee first, Python valuation math, evaluator appendix, data quality, number check, cost) and `report.json`
- `reporting/wording.py` — plain words for report.md: verdicts, confidence, analysts, fields, pack paths, company name for the ticker; `humanize()` is the last pass over the whole report, model text included
- `main.py` — CLI for a full run; writes the report, the exact pack and its provenance
- `eval/run_eval.py` — the behaviour eval on `eval/cases.json` (golden fixtures only; a private ticker is refused): runs, grades, writes `.claude/hillclimb/stock/<variant>/` (git-ignored), resumes interrupted runs, `--batch`
- `eval/grading.py` — pure grading: verdict against labels, ERROR_COST (Startup Autopsy's matrix mapped to these verdicts), forbidden Forensic verdicts, invented numbers (in no pack value at all), baselines, stability
- `eval/judge.py` — Haiku 5.5 at effort low checks must_find / must_not on the committee and Forensic text; code rejects evidence that is not a verbatim quote
- `config.py` — API key check, model, prices (including cache multipliers and Haiku 5.5's long-prompt rate), request settings from `.env`
- `core/claude_client.py` — one shared Anthropic client; logs rate-limit headers at DEBUG; `use_batches()` for the eval
- `core/batch_client.py` — `BatchingClient`: answers `messages.parse()` through Message Batches (half price, minutes of latency)
- `core/structured_call.py` — one structured request: stop-reason checks, validation, one retry, server-tool continuations, optional cached prefix, token usage including cache reads and writes
- `core/token_summary.py` — cost estimate per call and per run, cache writes and reads priced separately
- `core/shared_context.py` — canonical JSON, SHA-256, the context wrapped as data
- `core/fanout.py` — parallel calls with an optional warm-up call first (for the prompt cache)
- `perspectives/perspective.py` — `Perspective` as data, prompt layout, `evaluate()`
- `examples/minimal_run.py` — two perspectives end to end; also run by the tests with the fake client
- `eval/CHANGES.md` — behavior changes log
- `tests/` — pytest; `conftest.py` has the fake client (optionally simulating the prompt cache); data layer tests run on hand-built inputs (`tests/xbrl_samples.py`) and golden fixtures, never on the network

## Data sources

Checked against the SEC documentation on 2026-10-15; check again before relying on a limit.

| Data | Source | Notes |
|------|--------|-------|
| Ticker → CIK | `https://www.sec.gov/files/company_tickers.json` | CIK is 10 digits with leading zeros |
| Financial facts | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | No API key. SEC says it updates within about a minute of a filing, yet on 2026-10-15 KO's 10-Q filed 2026-07-29 was missing: the pack checks freshness against the filing history |
| Filing history | `https://data.sec.gov/submissions/CIK##########.json` | |
| Price, market cap | yfinance, version pinned | Unofficial; can break without notice; cache results |

- SEC fair access: at most 10 requests per second, a declared `User-Agent` with a
  contact email (`SEC_USER_AGENT` in `.env`). Without it the SEC answers 403.
- Cache raw responses and packs per ticker per day under `data_cache/` (git-ignored).
- XBRL traps to expect: the same line item under different `us-gaap` tags (and the tag
  changing over the years); `fy`/`fp` describe the filing, not the period, so periods
  are identified by `start`/`end` dates; fiscal year ≠ calendar year and 52/53-week
  years; quarterly facts mix 3-month and year-to-date values; several values for one
  period from different filings (restatements and recasts).

## Engineering standards

- Production quality: explicit error handling, no silent fallbacks that fabricate
  data (e.g. a default value when parsing fails).
- Prefer structured outputs (JSON schema via `messages.parse`) over parsing free text.
- A schema-valid answer can still be garbage: every structured call has a validator.
- Keep core logic free of CLI I/O, so it can be exposed through an MCP server later.
- Code, comments, docstrings, prompts and commit messages in English.
- Realistic estimates for timelines and costs in docs and prompts.
- Never state an API limit, price or endpoint from memory: check the documentation
  and write down the date it was checked.
- What a person reads (report.md, CLI output, summaries for the owner) carries no codes:
  no verdict enums, tickers, field names, pack paths or claim tags, only their meaning in
  words (`reporting/wording.py`; `tests/test_wording.py` scans the report). report.json
  and eval data keep the codes for programs.
- Think like a tester: golden tickers, fixtures, and checks that catch a number the
  model did not get from the pack.

## Data rules

- **Absent is not zero.** A missing value is `null` with a reason, never `0`.
  `canonical_json` refuses NaN and infinity so a missing number cannot slip
  through as a float. The seven data quality rules are in the source of truth.
- **One context for all.** Every evaluator gets the byte-identical data pack;
  its hash goes into the report.
- **Context is data, not instructions.** `context_block()` says so in the prompt;
  text inside it (filings, news, transcripts, descriptions) is never followed.

## Prompt caching

- Layout: shared rules + data pack first (one cached block), then the evaluator's
  role and focus, then its questions in the user message. Anything that differs
  between calls goes after the breakpoint, or the calls share nothing.
- The cache order is tools → system → messages. Different tools, a different
  effort or thinking setting between calls break the shared cache.
- Calls sent at the same moment all miss the cache; `run_parallel` runs the first
  call alone (warm-up), then the rest. Valuation step A is that first call.
- A different structured-output schema (`output_config.format`) also invalidates the
  cache (structured outputs docs, checked 2026-10-15). Each evaluator has its own schema,
  so today each writes its own cache entry; only reruns of the same evaluator within
  5 minutes read it. A shared schema would fix it (later-list, about 13% of a run).
- A prefix below the model's minimum is silently not cached (512 tokens for
  Sonnet 5.5); `structured_call` warns when caching was asked and nothing was cached.
- `usage.input_tokens` excludes cached tokens. Total input =
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.
- Turn caching off with `PROMPT_CACHING=off` to measure its effect.

## Behavior changes

Every change that can change what the model answers — prompts, evaluators,
schemas, model or request settings — gets an entry in `eval/CHANGES.md`. Change
one thing at a time when it will be evaluated, so the eval can tell which change
moved the results. Never tune a prompt on a single run.

## Status and plan

Each milestone ends green (`pytest`, `ruff check .`) and committed.

| Milestone | Scope | Status |
|-----------|-------|--------|
| M0 | Repository, docs, prices, default model | done |
| M1 | Data layer for one ticker: EDGAR + yfinance, live fetch plus daily cache; no LLM calls | done |
| M2 | DATA PACK with `data_quality`, the seven rules and period checks, tests on fixtures; golden packs frozen; size measured with `count_tokens` (KO 8,639, SNOW 6,763, KHC 8,752 tokens on Sonnet 5.5) | done |
| M3 | Evaluators 1, 3, 5, 8 and the synthesis, offline with the fake client | done |
| M4 | First real run on one golden ticker (owner's OK first): report with `as_of`, sources, disclaimer, pack hash; `[DATA]` numbers checked against the pack | done: KHC, 0.61 USD, 40 of 48 DATA claims match, no invented number (eval/CHANGES.md) |
| M5 | Eval on the golden tickers: forensic red flags and the synthesis verdict (budget 4 USD; prompts, schemas and model frozen during the runs) | baseline done and regraded (eval/CHANGES.md): acceptable 6/6, must_find 6/6, no must_not 6/6, 0 invented numbers, committee verdict stable but WEAK_CASE everywhere (no better than a constant on 3 tickers); judge by majority of 3. Variant ANALYSIS_EFFORT=medium started 2026-10-15 18:06 (before the prompt change 67404ad): if `.claude/hillclimb/stock/effort_medium/results.jsonl` lacks 6 rows, resume with `ANALYSIS_EFFORT=medium python -m eval.run_eval --reps 2 --batch --variant effort_medium` (done attempts are skipped), then compare with baseline and fill its CHANGES entry. Spent about 2.36 USD before the variant (estimate 1.1-1.3) |

Decisions:

| # | Decision | Status |
|---|----------|--------|
| D1 | Default model | `claude-sonnet-5-5` (2026-10-15) |
| D2 | Golden tickers | KO (boring quality), SNOW (fast-growing, loss-making), KHC (2019 restatement) (2026-10-15) |
| D3 | Evaluator VERDICT block | Structured-output schema fields; confidence as LOW / MEDIUM / HIGH with a one-sentence reason instead of 0-100 (2026-10-15) |
| D4 | Phase 1 valuation scope | Python multiples on TTM + base DCF for bear/base/bull from step A; reverse DCF by Python (implied revenue growth at base-case margins, with a reason when it cannot be solved); no peer multiples; sensitivity grid in Phase 2 (2026-10-15) |

DATA PACK extensions over the source-of-truth schema (Phase 1 evaluators need them):
`shares_outstanding`, `ttm`, `balance_sheet_latest`, `derived` (Python math with formulas),
`filing_events`, `annual_report_timing`; `data_quality.missing` groups periods per field and
reason and adds the reason `not_fetched` (insider transactions, peers, news, transcripts
are not fetched in Phase 1).

## Privacy

- Tickers researched for personal reasons are listed only in `private/companies.md`
  (git-ignored). Their reports, logs and caches stay local and are deleted when no
  longer needed; they never become fixtures, eval cases, examples or commit text.
- The guard runs in pytest (skipped where the private list is absent, as in CI) and
  as local hooks, which git does not version; install them in a new clone with:

  ```bash
  printf '#!/bin/sh\nexec venv/Scripts/python.exe -m scripts.check_private_tickers\n' > .git/hooks/pre-commit
  printf '#!/bin/sh\nexec venv/Scripts/python.exe -m scripts.check_private_tickers --commit-msg "$1"\n' > .git/hooks/commit-msg
  ```
- Status 2026-10-15: tracked files, every commit message, author and patch, all git
  objects, fixtures (including gzipped) and eval checked: no private ticker. Local
  results, logs and caches of personal research deleted. No remote yet.

## Later (not scheduled; the owner decides)

- Measure the plain-words / DERIVED prompt change (67404ad) with one eval pass.
- More golden tickers: three cannot tell the committee verdict from a constant answer.
- One shared output schema for all evaluators, so the prompt cache carries across them
  (about 13% of a run's cost; each schema invalidates the cache today).
- Form 4 insider transactions, peers and peer multiples, news, transcripts (Phase 2/3).
- Company extension concepts beyond receivables (interest expense, others).
- DCF sensitivity grid (Phase 2), remaining evaluators 2, 4, 6, 7.
- A pack check for definition switches in other line items (as done for receivables growth).

## Known issues

- `THINKING=off` sends no thinking parameter. On Sonnet 5.5 (the default), Opus 5.5
  and Haiku 5.5 the model still thinks adaptively; `ANALYSIS_EFFORT` is the real
  control there. At the default effort (`high`) an evaluator writes about 5-12k output
  tokens, mostly thinking; a full run costs about 0.6 USD (KHC, 2026-10-15).
- Evaluators sometimes cite a wrong pack path for a correct number (`ttm.free_cash_flow`
  instead of `derived.ttm.free_cash_flow`); the number check reports these as bad_path.
- Form 4 (insider transactions), peers, news and transcripts are not fetched in Phase 1:
  null with reason `not_fetched`, never an empty list.
- SEC company facts hold standard taxonomies only. Company extension concepts are read
  from filing XBRL instances for receivables only (`datalayer/extensions.py`), and only
  when us-gaap receivables stop before the latest annual report. Any other line item a
  company reports under its own concept (interest expense, for example) stays unknown
  (`not_reported` / `tag_not_found`), never zero.
- Total debt is assembled from reported concepts (long-term incl. current, convertible,
  short-term borrowings); shapes not in `line_items.py` show up as `partial` or missing.
