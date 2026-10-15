# Stock Autopsy

Analyzes one US public company from several independent perspectives — business
model, forensic accounting, valuation, pre-mortem and more — and reconciles them in
an "Investment Committee" synthesis that looks for productive conflicts instead of
averaging opinions.

**Not investment advice.** Stock Autopsy is a research-structuring and learning tool.
It never says buy, sell or hold; its verdicts describe how strong the evidence is.

> Status: early development. The analysis core (structured calls, prompt caching,
> parallel evaluators, cost accounting) is in place; the data layer is next.

## The idea: data first, model second

Language models produce plausible numbers from memory, and a plausible but wrong
revenue or share count silently breaks an analysis. Here the model never supplies
numbers:

```
1. Python fetches official data (SEC EDGAR) and prices → one DATA PACK (as_of dates, sources, data quality)
2. Every evaluator gets the byte-identical pack → analyzes, tags every claim
3. Python does the math: multiples, growth rates, DCF
4. The synthesis reads all evaluator reports → verdict, conflicts, monitoring plan, next research steps
```

Every claim is tagged `[DATA]`, `[DERIVED]`, `[ASSUMPTION]` or `[UNVERIFIED]`, and
a missing figure is reported as unknown — never as zero. The full specification
(evaluator prompts, DATA PACK schema, data quality rules) is in
[docs/stock_autopsy_prompts.md](docs/stock_autopsy_prompts.md).

Synthesis verdicts: `STRONG_CASE`, `CONDITIONAL_CASE`, `INSUFFICIENT_DATA`,
`WEAK_CASE`, `RED_FLAGGED`.

## Roadmap

| Phase | Scope |
|-------|-------|
| 1 — MVP | Data layer (EDGAR + prices), four evaluators (Business Model, Forensic, Valuation, Pre-Mortem), Claude-based synthesis |
| 2 | The remaining four evaluators, DCF sensitivity grid, earnings transcript input |
| 3 | Web search for catalysts, peer comparison runs, "what changed since the last autopsy" |

Testing approach: unit tests with a fake Claude client and data-layer tests on
frozen fixtures (no network), then golden tickers — a boring quality company, a
fast-growing unprofitable one, and one with a known accounting scandal — to check
whether the forensic perspective finds the scandal from the numbers alone.

## Quick start

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
copy .env.example .env                          # then set ANTHROPIC_API_KEY and SEC_USER_AGENT
pytest && ruff check .
python -m examples.minimal_run                  # a real call, a few cents
```

SEC EDGAR asks every client to declare a `User-Agent` with a contact email and to
stay under 10 requests per second; set `SEC_USER_AGENT` in `.env`.

## License

MIT
