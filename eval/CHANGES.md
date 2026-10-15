# Behavior changes log

Every change that can change what the model answers — prompts, evaluators,
schemas, model or request settings — gets an entry here, newest first. The full
eval runs when budget allows, not after every change, so this log is how its
results are read: which changes a pass covers, and what each was expected to do.

Entry format: date, commit, what changed, expected effect, risk to watch, how it
was checked so far, and the eval result once there is one.

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
