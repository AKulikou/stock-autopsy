# Test companies

Companies used to develop and check Stock Autopsy, and what each one tests. The golden
tickers have frozen fixtures in `tests/fixtures/golden/`; the candidates were looked at
while choosing them (data checked on 2026-10-15) and are useful for one-off checks.

Personal research tickers go into `private/companies.md`, which git ignores.

## Golden tickers (decision D2)

| Ticker | Company | Category | What it tests |
|--------|---------|----------|---------------|
| KO | Coca-Cola | Boring quality | 2:1 split in 2012 (share counts); 8-K recasts that changed revenue without any warning sign — the forensic false-positive case; company facts lagging the latest 10-Q |
| SNOW | Snowflake | Fast-growing, loss-making | Fiscal year ending in January; no debt concept before 2024 (unknown, not zero), then convertible notes; heavy stock-based compensation; P/E and EV/EBIT not meaningful on a loss; rounded figures in proxy statements |
| KHC | Kraft Heinz | Accounting scandal | 2019 restatement of 2016-2017 visible in the numbers; 8-K item 4.02 notices, a late-filing notice and a 10-K filed 160 days after year end; 52/53-week years |

## Candidates

| Ticker | Company | Category | What it would test |
|--------|---------|----------|--------------------|
| PG | Procter & Gamble | Boring quality | Fiscal year ending in June; many 8-K recasts and a 10-K/A; cash reported only with restricted cash since 2019 |
| RIVN | Rivian | Fast-growing, loss-making | Heavy capital expenditure; convertible and long-term debt |
| PLUG | Plug Power | Accounting scandal | 10-K/A in 2022 restating 2018-2019; also loss-making |
| MDXG | MiMedx | Accounting scandal | 2016 restatement under a changed revenue concept (found only when concepts are compared together) |
