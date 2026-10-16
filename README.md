# Stock Autopsy

Analyzes one US public company from several independent perspectives (business
model, forensic accounting, valuation, pre-mortem) and reconciles them in an
"Investment Committee" synthesis that looks for productive conflicts instead of
averaging opinions.

**Not investment advice.** Stock Autopsy is a research-structuring and learning tool.
It never says buy, sell or hold; its verdicts describe how strong the evidence is.

> Status: Phase 1 works end to end (data layer, four evaluators, committee, number
> check, eval on five golden companies, a local web page). Not published as a product;
> see the honest limits below.

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
| Evaluators | Business Model, Forensic (accounting warning signs, restatements), Valuation (the model proposes DCF assumptions, Python computes bear / base / bull, reverse DCF, the yearly return a buyer at today's price gets if the base case comes true, and sensitivities; the model interprets what the price assumes), Pre-Mortem |
| Committee | One call that reads the evaluators, names the conflicts and decides the verdict, with a headline and three reasons for and against in plain words; code lowers its confidence when too much rests on unverified claims or a perspective is missing |
| Number check | Every number in a data claim is compared with the pack value at the path the claim cites (with its sign where the wording states one); calculated claims, numbers in prose and unknowns stated as zero are checked too |
| Reports | `report.md` in plain words (no codes, tickers or field names), `report.json` with the codes, the exact pack and its provenance |
| Eval | Five golden companies with labels written before any run, a judge for "must find" / "must not say" statements (majority of three votes, verbatim evidence), constant-answer baselines, stability between reps, and a free regrade of stored runs when a check changes |

## Quick start

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
copy .env.example .env                          # then set ANTHROPIC_API_KEY and SEC_USER_AGENT
pytest && ruff check .                          # no network, no API calls
python -m datalayer.pack KO                     # build the data pack only (free, no model)
python main.py KO                               # full analysis (paid, see below)
python -m web                                   # the same in a local web page: http://127.0.0.1:8001
```

The web page takes a company, a brand or a ticker (a name or brand is looked up with one
cheap call and checked against the SEC list), shows the data being gathered and each
analyst finishing, then the answer in plain words with what the price assumes, and every
quoted number coloured by what the number check found. Design: [docs/web_ui.md](docs/web_ui.md).

SEC EDGAR asks every client to declare a `User-Agent` with a contact email and to
stay under 10 requests per second; set `SEC_USER_AGENT` in `.env`.

**Cost and time.** A full run makes six Claude calls (Sonnet 5.5 at its default
effort) and costs about 0.60 USD and three minutes (measured on Kraft Heinz,
2026-10-15). Through the Message Batches API, as the eval runs it, an attempt costs
about 0.26-0.30 USD and takes longer.

## Testing and its honest limits

Unit tests use a scripted fake Claude client and frozen fixtures, so they never
touch the network. The behaviour eval runs the real pipeline on frozen packs of
five golden companies: Coca-Cola (boring quality), Snowflake (fast-growing,
loss-making), Kraft Heinz (the 2019 restatement), Comcast (cheap and flat, where
"weak case" is a wrong answer) and Plug Power (red flags dominate). Every measurement
is logged in [eval/CHANGES.md](eval/CHANGES.md).

What the eval showed (two reps per company on the first three; one rep per company
on all five after the valuation change):

- Forensic found Kraft Heinz's restatement trail (restated cash flow, non-reliance
  notices, the late annual report) in every attempt and never red-flagged Coca-Cola's
  routine recasts.
- The committee said "weak case" for all three original companies in the baseline,
  scoring exactly like a constant answer, so two companies were added where "weak case"
  is wrong. Comcast came out a conditional case and Plug Power red-flagged in the first
  run; after the valuation change Plug Power fell to "weak case" once, because the
  Forensic analyst did not raise its red flag that time. One rep per company is too few
  to call that a trend.
- Grounding is checked by code, not trusted: a mutation test quotes the golden packs'
  real values with deliberate errors (+10%, x10, a flipped "loss"/"profit") and requires
  the number check to catch at least 90% of them. Calculated claims are reproduced from
  the formula they cite, numbers in prose without a source are listed, and a sentence
  that turns an unknown value into zero ("no debt" where the filings report none) is
  flagged. In the M5 runs: 8 and 5 wrong numbers (all partial) in about 270 data claims
  per variant, one calculation off by about 5%, and the one "no debt" sentence the judge
  also found.
- Valuation is judged by what the price assumes rather than by a DCF value at one
  chosen discount rate: Python solves the yearly return a buyer at today's price gets if
  the base case comes true. At the eval's prices that was about 5% a year for Coca-Cola
  (read as expensive) and about 12% for Comcast (a case under conditions).

## Roadmap

| Phase | Scope |
|-------|-------|
| 1 — MVP | Data layer (EDGAR + prices), four evaluators, Claude-based synthesis, number check, eval (done) |
| 2 | The remaining four evaluators, DCF sensitivity grid, earnings transcript input |
| 3 | Web search for catalysts, peer comparison runs, "what changed since the last autopsy" |

## License

MIT
