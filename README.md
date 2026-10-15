# Stock Autopsy

Analyzes one US public company from several independent perspectives (business
model, forensic accounting, valuation, pre-mortem) and reconciles them in an
"Investment Committee" synthesis that looks for productive conflicts instead of
averaging opinions.

**Not investment advice.** Stock Autopsy is a research-structuring and learning tool.
It never says buy, sell or hold; its verdicts describe how strong the evidence is.

> Status: Phase 1 works end to end (data layer, four evaluators, committee, number
> check, eval on three golden companies). Not published as a product; see the honest
> limits below.

## The idea: data first, model second

Language models produce plausible numbers from memory, and a plausible but wrong
revenue or share count silently breaks an analysis. Here the model never supplies
numbers:

```
1. Python fetches official data (SEC EDGAR) and prices → one DATA PACK (as_of dates, sources, data quality)
2. Every evaluator gets the byte-identical pack → analyzes, tags every claim
3. Python does the math: multiples, growth rates, DCF
4. The synthesis reads all evaluator reports → verdict, conflicts, monitoring plan, next research steps
5. Python checks every number the model quotes as data against the pack
```

Every claim is tagged as data (with the pack path it comes from), derived, an
assumption or unverified, and a missing figure is reported as unknown — never as
zero. The full specification (evaluator prompts, DATA PACK schema, data quality
rules) is in [docs/stock_autopsy_prompts.md](docs/stock_autopsy_prompts.md); where
the code deviates from it, that document says so.

The committee's verdict is one of: strong case, conditional case, insufficient data,
weak case, red-flagged.

## What works

| Part | What it does |
|------|--------------|
| Data layer | SEC company facts, filing history and 8-K items, extension concepts from filing XBRL where needed, prices via yfinance; daily cache; ten fiscal years, discrete quarters, trailing twelve months; restatements and late filings detected; every missing value carries a reason |
| Evaluators | Business Model, Forensic (accounting warning signs, restatements), Valuation (the model proposes DCF assumptions, Python computes bear / base / bull, reverse DCF and sensitivities, the model interprets), Pre-Mortem |
| Committee | One call that reads the evaluators, names the conflicts and decides the verdict; code lowers its confidence when too much rests on unverified claims or a perspective is missing |
| Number check | Every number in a data claim is compared with the pack value at the path the claim cites (with its sign where the wording states one); calculated claims, numbers in prose and unknowns stated as zero are checked too |
| Reports | `report.md` in plain words (no codes, tickers or field names), `report.json` with the codes, the exact pack and its provenance |
| Eval | Three golden companies with owner-approved labels, a judge for "must find" / "must not say" statements (majority of three votes, verbatim evidence), constant-answer baselines, stability between reps |

## Quick start

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
copy .env.example .env                          # then set ANTHROPIC_API_KEY and SEC_USER_AGENT
pytest && ruff check .                          # no network, no API calls
python -m datalayer.pack KO                     # build the data pack only (free, no model)
python main.py KO                               # full analysis (paid, see below)
```

SEC EDGAR asks every client to declare a `User-Agent` with a contact email and to
stay under 10 requests per second; set `SEC_USER_AGENT` in `.env`.

**Cost and time.** A full run makes six Claude calls (Sonnet 5.5 at its default
effort) and costs about 0.60 USD and three minutes (measured on Kraft Heinz,
2026-10-15). Through the Message Batches API, as the eval runs it, an attempt costs
about 0.26-0.30 USD and takes longer.

## Testing and its honest limits

Unit tests use a scripted fake Claude client and frozen fixtures, so they never
touch the network. The behaviour eval runs the real pipeline on frozen packs of
three golden companies: Coca-Cola (boring quality), Snowflake (fast-growing,
loss-making) and Kraft Heinz (the 2019 restatement). Every measurement is logged in
[eval/CHANGES.md](eval/CHANGES.md).

What the eval showed (two reps per company):

- Forensic found Kraft Heinz's restatement trail (restated cash flow, non-reliance
  notices, the late annual report) in every attempt and never red-flagged Coca-Cola's
  routine recasts.
- The committee said "weak case" for all three companies in the baseline, so on three
  companies its verdict scores exactly like a constant answer. More golden companies,
  including one where "weak case" is wrong, are needed before the verdict metric means
  anything.
- Grounding is checked by code, not trusted: a mutation test quotes the golden packs'
  real values with deliberate errors (+10%, x10, a flipped "loss"/"profit") and requires
  the number check to catch at least 90% of them. Calculated claims are reproduced from
  the formula they cite, numbers in prose without a source are listed, and a sentence
  that turns an unknown value into zero ("no debt" where the filings report none) is
  flagged. In the M5 runs: 8 and 5 wrong numbers (all partial) in about 270 data claims
  per variant, one calculation off by about 5%, and the one "no debt" sentence the judge
  also found.
- The valuation side tends to call mature and growth companies expensive: with the
  model's discount rates, the price sits above even the bull DCF for Coca-Cola and
  Snowflake. That is a hypothesis to test, not a finding.

## Roadmap

| Phase | Scope |
|-------|-------|
| 1 — MVP | Data layer (EDGAR + prices), four evaluators, Claude-based synthesis, number check, eval (done) |
| 2 | The remaining four evaluators, DCF sensitivity grid, earnings transcript input |
| 3 | Web search for catalysts, peer comparison runs, "what changed since the last autopsy" |

## License

MIT
