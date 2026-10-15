# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

TODO: one paragraph — what this project analyzes, from which perspectives, and
what the final report is. Started from `autopsy-template` (the shared core of
the Autopsy projects: Startup Autopsy, Stock Autopsy, Crypto Autopsy).

The shape every Autopsy project shares:

1. Python builds the **shared context** (an idea text, a data pack) once.
2. Several independent **perspectives** analyze the same context, each from one
   angle, each returning structured output.
3. A **synthesis** call reads the perspective results and decides; it adds no
   new facts.

## Commands

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt            # app + pytest + ruff
pytest                                         # unit tests, fake Claude client, no API calls
ruff check .                                   # lint (config in pyproject.toml, target Python 3.10)
python -m examples.minimal_run                 # smallest real run, a few cents
```

Requires `ANTHROPIC_API_KEY` in `.env` (never commit it). Run `pytest` and
`ruff check .` after any change.

## Layout

- `config.py` — API key check, model, prices (including cache multipliers), request settings from `.env`
- `core/claude_client.py` — one shared Anthropic client; logs rate-limit headers at DEBUG; `use_batches()` for the eval
- `core/batch_client.py` — `BatchingClient`: answers `messages.parse()` through Message Batches (half price, minutes of latency)
- `core/structured_call.py` — one structured request: stop-reason checks, validation, one retry, server-tool continuations, optional cached prefix, token usage including cache reads and writes
- `core/token_summary.py` — cost estimate per call and per run, cache writes and reads priced separately
- `core/shared_context.py` — canonical JSON, SHA-256, the context wrapped as data
- `core/fanout.py` — parallel calls with an optional warm-up call first (for the prompt cache)
- `perspectives/perspective.py` — `Perspective` as data, prompt layout, `evaluate()`
- `examples/minimal_run.py` — two perspectives end to end; also run by the tests with the fake client
- `eval/CHANGES.md` — behavior changes log
- `tests/` — pytest; `conftest.py` has the fake client (optionally simulating the prompt cache)

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

## Data rules

- **Absent is not zero.** A missing value is `null` with a reason, never `0`.
  `canonical_json` refuses NaN and infinity so a missing number cannot slip
  through as a float.
- **One context for all.** Every perspective gets the byte-identical shared
  context; its hash goes into the report.
- **Context is data, not instructions.** `context_block()` says so in the prompt;
  text inside it (filings, news, transcripts, descriptions) is never followed.

## Prompt caching

- Layout: shared standards + shared context first (one cached block), then the
  perspective's role and focus, then its questions in the user message. Anything
  that differs between calls after the breakpoint, or the calls share nothing.
- The cache order is tools → system → messages. Different tools, a different
  effort or thinking setting between calls break the shared cache.
- Calls sent at the same moment all miss the cache; `run_parallel` runs the first
  call alone (warm-up), then the rest.
- A prefix below the model's minimum is silently not cached (1,024 tokens for
  Sonnet 4.6); `structured_call` warns when caching was asked and nothing was cached.
- `usage.input_tokens` excludes cached tokens. Total input =
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.
- Turn caching off with `PROMPT_CACHING=off` to measure its effect.

## Behavior changes

Every change that can change what the model answers — prompts, perspectives,
schemas, model or request settings — gets an entry in `eval/CHANGES.md`. Change
one thing at a time when it will be evaluated, so the eval can tell which change
moved the results.

## Known issues

TODO
