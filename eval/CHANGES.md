# Behavior changes log

Every change that can change what the model answers — prompts, evaluators,
schemas, model or request settings — gets an entry here, newest first. The full
eval runs when budget allows, not after every change, so this log is how its
results are read: which changes a pass covers, and what each was expected to do.

Entry format: date, commit, what changed, expected effect, risk to watch, how it
was checked so far, and the eval result once there is one.

## 2026-10-15 — report.md in plain words (display only)

- **Changed:** report.md and the CLI summary show meanings instead of codes: verdict and
  confidence words, analyst names, field names in words, pack paths as "annual figures ›
  FY2025 › revenue", the company name instead of its ticker. A last pass
  (`reporting/wording.py`) also rewrites codes inside the model's own text. report.json
  and the eval keep the codes.
- **Not changed during M5:** the prompts still let the model write codes; asking it for
  plain words is a prompt change, queued for after the M5 baseline.
- **Effect on the eval:** none; the judge reads the raw model text.

## 2026-10-15 — path hint for derived values (prompt change)

- **Changed:** `PATH_HELP` (in the shared rules) now says where Python's values live:
  `derived.valuation.*` for multiples, `derived.annual` / `derived.ttm` for margins and
  free cash flow. The number check also skips "year-1".
- **Why:** in two real runs evaluators cited `valuation.pe` and `ttm.free_cash_flow`
  (paths that do not exist) for correct numbers: 1-3 bad_path or partial per run.
- **Expected:** fewer bad_path results; no effect on the analysis.
- **Checked so far:** offline tests only.

## 2026-10-15 — receivables from company extension concepts (data pack change)

- **Changed:** when us-gaap receivables stop before the latest annual report, the data
  layer reads the company's own receivables concept from the filing XBRL instances;
  values from it are noted as a possible definition change, and receivables growth
  across the switch is None. A zero that another filing contradicts for the same period
  is treated as a tagging error. Golden packs (KO, SNOW, KHC) are unchanged: none of
  them needs extensions.
- **Expected:** Forensic can compare receivables with revenue for companies that moved
  to their own concept, without reading the switch year as a jump.
- **Risk to watch:** a matcher that picks the wrong concept (it refuses when two
  candidates remain); extension values that include contract assets.

## 2026-10-15 — second real run (KHC) and number-check parser fix

- **Run:** `results/KHC_2026-10-15_141321` (git-ignored). Sonnet 5.5, default effort, all six
  calls succeeded on the first attempt; 87,606 input / 43,726 output tokens, 0.61 USD,
  175 s. Committee: WEAK_CASE, confidence LOW (stronger side: bear). Forensic: WEAK,
  red flag score 6/10, flags of severity 4 for the 2017-2019 non-reliance / late-filing
  history and for repeated multi-billion operating losses; not RED_FLAG.
- **Number check:** 48 DATA claims, 40 match, 5 no number, 3 problems; all 3 cite a wrong
  path (`ttm.free_cash_flow` for `derived.ttm.free_cash_flow`, `valuation.*` for
  `derived.valuation.*`) while the numbers themselves are in the pack. No invented number.
  Before the parser fix it reported 37 matches: "year 1", "over 3 years" and "8-Ks" were
  read as quantities; now they are skipped (tests added).
- **Prompt caching does not carry across evaluators:** each output schema
  (`output_config.format`) invalidates the cache (structured outputs docs, checked
  2026-10-15), so three of four parallel calls wrote their own 11k-token entry (13% of input
  read from cache). One shared schema for all evaluators would save about 0.08 USD a run
  (13%); output tokens are 70% of the cost. Not changed: later-list.
- **Cost per run:** about 0.6 USD for KHC at the default effort (output ~5-11k tokens per
  evaluator, thinking included). The pre-run estimate of 0.30-0.55 was low.

## 2026-10-15 — claim contract after the first real run

- **First run (KHC, Sonnet 5.5, 0.91 USD, 116,824 input / 74,978 output tokens):** every
  evaluator rejected twice, no verdict. The analyses were substantive (the logs show
  Forensic citing the FY2016 restatement, both 8-K 4.02 notices and the 160-day 10-K), but
  DATA claims listed several paths in one basis ("a; b", "x (note)") and ran to 21-31
  claims; the validator demanded one path and at most 20, the prompt never said so, and the
  identical retry repeated the mistakes. Rejected answers were not kept.
- **Changed:** a basis may list several paths separated by ';' (notes after a path are
  ignored); the prompt asks for 8-15 claims and spells out the DATA basis format; up to 40
  claims pass; an answer is rejected only when more than 25% of its DATA claims name no
  existing path (fewer are reported by the number check as bad_path); the number check
  matches against every value under the cited paths and reports partial matches; a retry
  tells the model what was rejected; the last rejected answer is kept in the error
  result (report.json).
- **Expected:** a complete run; number-check counts become the measure of grounding.
- **Risk to watch:** groups as a basis (data_quality.restated) let a number match any
  value in the group: watch for matches that are coincidences.
- **Lesson:** check a new output contract with one call before a full run.

## 2026-10-15 — first prompts: Phase 1 evaluators and the Investment Committee

- **Changed:** `SHARED_RULES`, Business Model, Forensic, Valuation (step A assumptions,
  step B interpretation) and Pre-Mortem in `evaluators/definitions.py`; committee
  principles in `synthesis/committee.py`; schemas per D3 (confidence LOW/MEDIUM/HIGH);
  validators. Adapted from the source of truth where the Phase 1 pack has no data
  (peers, Form 4, transcripts): those questions ask for INSUFFICIENT DATA.
- **Expected:** every number traceable to the pack (DATA claims name a pack path; the
  number check compares them); Forensic separates KHC's restatement (4.02 notices,
  late 10-K) from KO's recasts.
- **Risk to watch:** too many UNVERIFIED claims (general knowledge about well-known
  companies) lowering confidence; DATA claims quoting rounded figures that the number
  check rejects; validators rejecting good answers twice (check the run log for
  "invalid result on attempt").
- **Checked so far:** offline only (fake client): prompt layout, identical cached
  prefix, step order, validators, number check, reports. No real run yet.

## 2026-10-15 — default model Sonnet 5.5 (decision D1)

- **Changed:** `DEFAULT_MODEL` from `claude-sonnet-4-6` (template default) to
  `claude-sonnet-5-5`. Prices 2 / 10 USD per MTok against 3 / 15; cache reads at
  0.05x; 512-token cache minimum (pricing and prompt caching pages, checked 2026-10-15).
- **Expected:** lower cost per run at comparable quality.
- **Risk to watch:** Sonnet 5.5 always thinks unless sent `between_tools`, and its
  default effort is `high`: output tokens (and cost) may be higher than expected, and
  long thinking may hit `MAX_TOKENS` (16,000). `THINKING=off` does not turn thinking
  off on this model.
- **Checked so far:** nothing model-dependent yet (no evaluators exist). Measure
  output tokens on the first real run (M4), and compare once with Sonnet 4.6 on the
  golden tickers.
