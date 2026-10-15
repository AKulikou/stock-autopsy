# Behavior changes log

Every change that can change what the model answers — prompts, evaluators,
schemas, model or request settings — gets an entry here, newest first. The full
eval runs when budget allows, not after every change, so this log is how its
results are read: which changes a pass covers, and what each was expected to do.

Entry format: date, commit, what changed, expected effect, risk to watch, how it
was checked so far, and the eval result once there is one.

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
