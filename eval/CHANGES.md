# Behavior changes log

Every change that can change what the model answers — prompts, evaluators,
schemas, model or request settings — gets an entry here, newest first. The full
eval runs when budget allows, not after every change, so this log is how its
results are read: which changes a pass covers, and what each was expected to do.

Entry format: date, commit, what changed, expected effect, risk to watch, how it
was checked so far, and the eval result once there is one.

## 2026-10-15 — grounding checks (grading and reporting only; measured on stored traces, free)

- **Why:** a mutation test (real annual values of the golden packs quoted with deliberate
  errors, now `tests/test_grounding.py`) showed that the number check is strong on exact
  paths but lets a wrong number through when the basis names a whole table, ignores a
  flipped sign, and that "0 invented numbers" is weak evidence (a wrong number is almost
  always found somewhere in the pack). DERIVED claims, prose and free-text fields were not
  checked at all; the SNOW "no debt" sentence of the effort variant went unnoticed by code.
- **Changed (no prompt, schema or model change; model answers are the same):**
  - Signs count where the wording states a direction ("a loss of", "fell 5%", a minus sign).
  - A number that matches only inside a cited table or block is `group_match`, not `match`.
  - DERIVED claims: each number must follow from the values the basis cites, by the
    formula written in the basis (pure arithmetic, parsed with `ast`) or one step of
    arithmetic; reported as reproduced / not reproduced (not reproduced is not "wrong").
  - Numbers in prose (all free-text fields of the evaluators and the committee, except the
    model's own thresholds and plans) must appear in the pack, the valuation math, the
    model's structured numbers or a claim; the rest are listed as without a source.
  - Unknowns read as zero: a sentence saying "no debt", "dividends of 0" and the like where
    the pack has the value as not reported or not found (and, if the sentence names
    periods, one of them is unknown).
  - Eval: the headline is **wrong numbers on exact paths** (mismatch + partial); "invented"
    is renamed "found nowhere"; new binary metrics "no wrong number", "all numbers found",
    "no unknown as zero"; `--regrade` recomputes these on stored traces for free.
- **Mutation test (golden packs, 208 annual values):** +10% errors caught on exact paths
  at least 90% (the misses are small values written as "$0.3 billion", whose own precision
  covers 17%), x2 and x10 always; a flipped sign stated in words now always caught (was
  never); on a table basis a wrong number is never a full match any more.
- **Regrade of M5 (no API call):**

| | Baseline | effort=medium |
|---|---|---|
| Wrong numbers on exact paths (all partial) | 8 of 264 data claims | 5 of 284 |
| Matched only inside a table | 0 | 0 |
| Found nowhere | 0 | 0 |
| Calculated claims reproduced | 80 of 89 | 31 of 39 |
| Numbers in prose without a source | 48 of 1,716 | 29 of 1,408 |
| Unknowns read as zero | 1 (SNOW rep1: "There is no dividend") | 3 (SNOW rep1 Forensic: "had no debt then and pays no dividends" = the must_not; SNOW rep0: no dividend support) |

- **Reading:** no evaluator used a table as a basis in M5, so the group change moved
  nothing yet; it closes a hole for later runs. One not-reproduced claim is a real error
  (SNOW, effort variant: "roughly $75 billion" where the model's own formula gives about
  79 billion). The "no dividend" hits are true of the company but not known from the pack;
  the rule is the rule. The linter found the must_not the judge found, without a model call.

## 2026-10-15 — prompts: plain words in prose, DERIVED for in-sentence arithmetic (prompt change, NOT measured yet)

- **Changed:** `SHARED_RULES` rule 12 (every text field is read by a person: verdicts,
  analysts, data and the company in words; codes, paths and tickers only where a field asks
  for them) and a sharper DERIVED rule (a statement that computes any number itself is
  DERIVED even when it quotes its inputs); the same plain-words paragraph in
  `SYNTHESIS_PRINCIPLES`. Prefix 9,907 tokens on the KHC pack (count_tokens), about +150.
- **Why:** the M5 baseline: committee prose such as "Valuation=WEAK" and "business_model vs
  pre_mortem"; three in-sentence calculations tagged DATA on KO.
- **Expected:** fewer codes in model text (report.md already rewrites them in code), more
  DERIVED tags, number check unchanged or better; verdicts unaffected.
- **Risk to watch:** evaluators stop citing pack paths in DATA bases (rule 12 must not leak
  into the basis field); judge evidence quotes change wording.
- **Checked so far:** offline tests only. Made after the effort=medium variant started, so
  neither M5 run includes it. Needs one eval pass when budget allows.

## 2026-10-15 — M5 variant: ANALYSIS_EFFORT=medium (request setting change, measured)

- **Changed (variant only, default unchanged):** `ANALYSIS_EFFORT=medium` for every
  evaluator and the committee; same prompts, schemas, model and labels as the baseline.
  Run as `ANALYSIS_EFFORT=medium python -m eval.run_eval --reps 2 --batch --variant effort_medium`.
- **Expected:** fewer output tokens (thinking) and a lower cost per run; the question is
  whether verdicts, Forensic findings and grounding hold.
- **Risk to watch:** shallower Forensic work (missed restatement trail), more bad paths.
- **Ran:** all six attempts started at 18:06 (trace time minus latency), before 67404ad
  (18:08), so they used the same prompts as the baseline: a clean comparison.
- **Cost:** 1.03 USD for 6 attempts (0.14-0.21 each) against 1.67 (0.26-0.30): **-38%**.
  Output tokens per attempt 18.0k on average against 39.4k. M5 total: probe 0.66 +
  baseline 1.67 + this variant 1.03 = 3.36 of 4 USD (plus about 0.02 of judge regrades).

| Ticker | Rep | Committee | Confidence | Forensic | Score | Max severity | Numbers matched | Cost |
|--------|-----|-----------|------------|----------|-------|--------------|-----------------|------|
| KO | 0 | WEAK_CASE | MEDIUM | WEAK | 4 | 4 | 45/46 | 0.21 |
| KO | 1 | WEAK_CASE | MEDIUM | WEAK | 4 | 4 | 43/47 | 0.18 |
| SNOW | 0 | WEAK_CASE | MEDIUM | WEAK | 5 | 4 | 45/49 | 0.17 |
| SNOW | 1 | WEAK_CASE | MEDIUM | WEAK | 4 | 4 | 44/48 | 0.14 |
| KHC | 0 | CONDITIONAL_CASE | LOW | RED_FLAG | 7 | 5 | 43/48 | 0.18 |
| KHC | 1 | WEAK_CASE | MEDIUM | RED_FLAG | 6 | 5 | 41/46 | 0.16 |

- **Verdicts:** acceptable 6/6, primary 3/6 (baseline 4/6), error cost 0.67 (0.33): KHC
  rep0 said CONDITIONAL_CASE (acceptable, error cost 2), so the committee verdict changed
  within KHC. Forensic was harsher: RED_FLAG on both KHC attempts (baseline WEAK at
  severity 4), WEAK on both KO attempts (baseline ADEQUATE); KO is still not red-flagged.
- **must_find 6/6; must_not violated once (SNOW rep1, 3/3 votes):** Forensic's
  `innocent_explanation` says "The company had no debt then and pays no dividends", while
  the pack has `total_debt` null with reason `not_reported` for FY2019-FY2023. "Absent is
  not zero" broken in a free-text field, which no check reads today.
- **Numbers:** 284 DATA claims, 261 match, 5 partial, 0 mismatch, 0 bad_path, 18 without
  a number, 0 invented.
- **Reading:** medium effort is much cheaper and found the restatement trail every time,
  but produced the one grounding failure of M5 and moved KHC's committee verdict. Two reps
  per ticker cannot separate that from noise.
- **Decision:** pending the owner (suggested: keep the default effort).

## 2026-10-15 — eval instrument: judge by majority of 3, substance-only must_find (no system change)

- **Changed:** the judge answers three times and each statement is decided by majority
  (`JUDGE_VOTES`); the SNOW must_find "losses in every year" now reads "loss-making on a GAAP
  basis" (owner-approved), as the owner first asked.
- **Why:** one judge answer flipped borderline statements between passes on identical text
  (must_find 6/6 -> 4/6; a must_not on SNOW rep1 judged present from "debt of 2.28B appeared
  after FY2024", which does not claim zero debt before; checked by hand).
- **Baseline regraded:** must_find 6/6, must_not clean 6/6; votes unanimous except one
  1/3 must_not on KO rep1 (outvoted). Judge cost about 0.003 USD per attempt.

## 2026-10-15 — M5 baseline: golden tickers, 2 reps each (no prompt, schema or model change)

- **Setup:** Sonnet 5.5, default effort, `--batch`; variant `baseline` in
  `.claude/hillclimb/stock/` (git-ignored). Labels in `eval/cases.json` (owner-approved;
  KHC's restatement must_find reworded after the probe, before the regrade). Judge
  Haiku 5.5 at effort low.
- **Cost:** baseline 1.65 USD for 6 attempts (0.26-0.30 each at batch prices, 498k input /
  236k output tokens); probe 0.66 USD (direct); regrades about 0.01 USD. M5 total about
  2.33 of 4 USD. Wall time 29 minutes (each stage waits for its batch).

| Ticker | Rep | Committee | Confidence | Forensic | Score | Max severity | Numbers matched | Invented | Cache read |
|--------|-----|-----------|------------|----------|-------|--------------|-----------------|----------|------------|
| KO | 0 | WEAK_CASE | MEDIUM | ADEQUATE | 3 | 3 | 34/37 | 0 | 26% |
| KO | 1 | WEAK_CASE | MEDIUM | ADEQUATE | 4 | 4 | 41/45 | 0 | 26% |
| SNOW | 0 | WEAK_CASE | MEDIUM | ADEQUATE | 4 | 4 | 40/42 | 0 | 0% |
| SNOW | 1 | WEAK_CASE | MEDIUM | WEAK | 5 | 4 | 43/44 | 0 | 25% |
| KHC | 0 | WEAK_CASE | LOW | WEAK | 6 | 4 | 44/49 | 0 | 13% |
| KHC | 1 | WEAK_CASE | LOW | WEAK | 6 | 4 | 40/47 | 0 | 26% |

- **Verdicts:** primary hit 4/6, acceptable 6/6, error cost 0.33. The committee said
  WEAK_CASE for every attempt, so it scores exactly like the constant "always WEAK_CASE"
  (primary 4/6, error cost 0.33): on three tickers the verdict metric cannot tell the system
  from a constant. KO (labelled CONDITIONAL_CASE) got WEAK_CASE twice: either the label is
  generous or the committee leans bearish; three tickers cannot say which.
- **Stability:** committee verdict unchanged within every ticker (pair disagreement 0.00);
  Forensic verdict changed for SNOW (ADEQUATE / WEAK), stable for KO and KHC.
- **Forensic found:** KHC 2/2 found the FY2016 restatement (operating cash flow 5.24 ->
  2.65 billion, "10-K filed 2019-06-07") and the 4.02 / NT 10-K trail, at severity 4, not
  RED_FLAG; KO 2/2 not red-flagged, recasts not read as manipulation; SNOW 2/2 named
  stock-based compensation (about 34% of revenue) as the gap between losses and cash flow.
  SNOW rep0's Forensic found "no accounting-integrity warning signs", which fits.
- **Forensic missed / got wrong:** the probe's Forensic wrote the KHC restatement in the
  wrong direction ("restated from 2.648 billion to... original 5.238 billion"); the number
  check cannot see it (both numbers exist). No must_not was triggered in any attempt.
- **Numbers:** 264 DATA claims, 242 match, 8 partial, 14 without a number, 0 bad_path (the
  path hint of 85e42b2 worked: 1-3 per run before), 0 invented. The first grading counted
  3 "invented" numbers for KO; all three were correct arithmetic in the sentence (a 38%
  rise between two cited figures, a 7.5-point margin change) tagged DATA instead of
  DERIVED. The metric now accepts differences, ratios and changes of the cited values;
  the tagging slip remains a prompt point for after M5.
- **Judge, checked by hand on every attempt:** KHC and KO decisions correct, quotes
  verbatim and decisive. SNOW "losses in every year": both reports state large GAAP losses
  (net loss 1.33 billion FY2026, 1.09 billion TTM) but never "every year"; the judge said
  present on the first pass and absent on the regrade of the same text. Verdict by hand:
  the substance is there, the label is over-specific (the owner asked for "losses").
  **The judge is not deterministic on borderline statements** (must_find 6/6 then 4/6 on
  identical input): read must_find rates with that in mind, and word statements by their
  substance.
- **Cache:** 19% of input read from cache on average (batch caching is best effort, and
  each output schema has its own cache; see the earlier entry).

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
