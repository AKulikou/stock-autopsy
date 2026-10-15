# autopsy-template

The shared core of the Autopsy projects, extracted from
Startup Autopsy: several independent perspectives analyze
one shared context through the Claude API, each returning validated structured
output, and their results feed a synthesis.

Start a new project (Stock Autopsy, Crypto Autopsy) by copying this folder,
then add the project's own data layer, perspectives, result schemas and synthesis.

## What is in the box

| Piece | Why it exists |
|-------|---------------|
| `core/structured_call.py` | One structured request with stop-reason checks, a validator, one retry and server-tool continuations. A schema-valid answer can still be garbage; this catches it. |
| Prompt caching | The shared prefix (standards + context) is sent first as one cached block. For Stock Autopsy Phase 2 (9 calls on a ~27k-token data pack, Sonnet 4.6 prices) the estimated run cost drops from about 1.53 to 0.93 USD, −39% (a planning estimate: the data pack size is not measured yet). |
| `core/fanout.py` | Parallel calls; the first one runs alone so the others can read the cache it wrote. |
| `core/shared_context.py` | Canonical JSON and a hash, so every perspective provably sees the same context; NaN is refused (absent is not zero). |
| `core/token_summary.py` | Cost per call and per run, with cache writes (1.25x input price) and reads (0.1x, 0.05x on some models) priced separately. |
| `core/batch_client.py` | Message Batches at half price for evals. |
| `tests/` | 43 tests with a fake client that can simulate the prompt cache; no test reaches the API. |
| `CLAUDE.md`, `eval/CHANGES.md` | Working rules for Claude Code and the behavior-change log, ready to fill in. |

## Quick start

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
copy .env.example .env                          # then set ANTHROPIC_API_KEY
pytest && ruff check .
python -m examples.minimal_run                  # a real call, a few cents
```

The example context is deliberately tiny, so the run warns that nothing was
cached: below the model's minimum (1,024 tokens for Sonnet 4.6) the API skips
caching without an error. A real data pack is far larger.

## Starting a new project from it

1. Copy the folder (without `.git`, `venv` and `.env`), rename it, `git init`, and
   set the commit identity for this repository (`git config user.email ...`) before
   the first commit. CI comes with the template (`.github/workflows/ci.yml`: ruff +
   pytest on Python 3.10 and 3.14 with a placeholder key).
2. Fill in the `Project` and `Known issues` sections of `CLAUDE.md`.
3. Build the shared context in Python and pass it through `context_block()`.
4. Define the perspectives as data (`Perspective`) and a result schema with a validator.
5. Write the synthesis as one more `request_structured` call over the perspective results.
6. Log every prompt or model change in `eval/CHANGES.md`.

## Not investment advice

Projects built on this template that analyze companies or markets report the
data date and sources and are research tools, not trading recommendations.

## License

MIT
