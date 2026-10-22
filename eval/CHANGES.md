# Behavior changes log

Every change that can change what the model answers — prompts, evaluators,
schemas, model or request settings — gets an entry here, newest first. The full
eval runs when budget allows, not after every change, so this log is how its
results are read: which changes a pass covers, and what each was expected to do.

Entry format: date, commit, what changed, expected effect, risk to watch, how it
was checked so far, and the eval result once there is one.

## 2026-10-22 — release eval `v4_release`: 5 golden cases x 2 reps on the code of 2026-10-22 (measured)

Setup: --reps 2 --batch, default configuration (shared output schema off: the API refuses it),
code bb7a02f; it measures everything since v3_release that the model sees: C2 (the reverse DCF
names its discount rate), C3 and M14 (the price sentence), the Coca-Cola pack refrozen (C1), and
the prompts of 67404ad, already in v3. Cost 2.75 USD, 32 minutes, cache read 21% on average.
Graded with the checks of 2026-10-22, v3_release regraded with the same checks:

| | v3_release | v4_release |
|---|---|---|
| Primary verdict | 7/10 | 5/10 |
| Acceptable | 9/10 | 9/10 |
| Error cost (0 = primary) | 0.40 | 0.80 |
| must_find / no must_not | 9/10 / 9/10 | 10/10 / 9/10 |
| Data numbers matched | 338 of 379 | 327 of 370 |
| Wrong numbers on exact paths | 7 | 6 |
| Calculations reproduced | 198 of 211 | 209 of 225 |
| Prose numbers without a source | 51 of 2,696 | 36 of 2,606 |
| Unknowns read as zero | 4 | 2 |

Per case: Comcast conditional 2/2 both runs; Coca-Cola weak 2/2 both (acceptable); Snowflake weak
2/2 both; Plug Power red-flagged in one of two attempts in both runs (the least stable call);
**Kraft Heinz weak 2/2 -> conditional 2/2** (acceptable, not primary). The whole drop of the
primary score is that one case, moved the same way in both attempts, so it is not noise: the
price sentence now gives about 8.1-8.2% a year at $22.70, and the committee reads it as a case
under conditions. Which change moved it (C2 or the price sentence) this run cannot tell.
Facts are not worse: fewer wrong numbers, the share of matched numbers and reproduced
calculations within one point, fewer unsourced prose numbers. The constant answer "weak case"
also scores error cost 0.80 on these attempts, so on this set the committee no longer beats it.
Recorded, nothing changed because of it; the Kraft Heinz label (weak primary, conditional
acceptable) stays as the author wrote it.

## 2026-10-22 — banks and other financial companies flagged by SIC code (E7; data pack change for them only)

The author's run on Goldman Sachs (SIC 6211) gave "insufficient data": revenue, total debt, EV and
the DCF were missing and a free cash flow yield of -15.8% meant nothing for a broker-dealer.
Goldman reports net revenues under RevenuesNetOfInterestExpense (58.283 billion for FY2025),
which the pack did not read. Now a company whose SIC code is in the SEC list's bank, credit,
broker-dealer and insurance ranges (6021-6099, 6111-6199, 6200-6282, 6311-6411; the SEC SIC
code list, checked 2026-10-22) gets: that concept as revenue after the general ones; a
`financial_company` block and a data quality note; enterprise value, EV multiples, P/FCF and the
FCF yield left out as "not meaningful for a bank or other financial company"; no DCF, with that
reason. A calm note on the lookup card and in the CLI says so before the run, which is not
blocked. For every other company nothing changes: the five golden packs are byte for byte the
same (tests/test_golden_packs.py). The analysts of a bank now see the flag and net revenues;
the effect needs a paid run on a bank (about 0.6 USD), not made.

## 2026-10-22 — translation: look-alike letters fixed by code, the retry names the word, one-sentence reason (E4, E5)

The author's Lithuanian copy of Costco kept "Forensic Accountant" in English: both answers wrote
"paketе", whose last letter is the Cyrillic "е" (U+0435); the check was right. Now, in a
Latin-script language, a Latin word with a few Cyrillic look-alikes (а е о р с х у к ...) gets
the Latin letters from code, with no retry; a word that is mostly Cyrillic or has a letter with
no Latin twin ("Vердикt") is still rejected, and the retry note names the word and each foreign
letter with its code point. Russian copies are not changed by code (the note names the word).
The reason for a section kept in English is one sentence, the same in the copy, on the page
and in the CLI: "Forensic Accountant stayed in English: twice the translation mixed Latin and
Cyrillic letters (paketе)." Copies with the old "Kept in English:" note are still read.
The translation prompt changes only on a retry, by the named words. Checked with the fake
client; one live Lithuanian translation of the Costco report follows (about 0.03 USD).

## 2026-10-22 — pre-release P3 lost to batch-call timeouts; the batch client now survives them (eval instrument)

The first `v4_release` run (5 cases x 2 reps, --batch) and a second run the author started both
ended with every attempt "only 0 of 4 perspectives succeeded": the client's calls to the
batches API timed out ("APITimeoutError", the SDK default of 10 minutes, retried twice), and
the eval gave up. On the server both step-A batches of 10 requests still ran (created 08:27
and 08:54 UTC, ended 10:40 and 10:25 UTC, about two hours in the queue) and were billed:
6,500 input, 157,582 cache-write, 66,434 cache-read and 120,292 output tokens, about
0.81 USD at batch prices, for no result.

What changed (`core/batch_client.py`, no request content changed): the create call has a
120-second timeout and no SDK retry; if it fails, the client looks for a batch with the same
number of requests made after it was sent and adopts it, so a lost answer never becomes a
second, paid copy. Status checks and the results download have a 60-second timeout, and a
failed one (timeout, dropped connection, 5xx, 429) is tried again at the next poll; the batch
is given up only after 30 failures in a row. Tests with a fake batches API cover the adopted
batch, failing status checks and a create that made no batch.

## 2026-10-22 — pre-release P5 fixes: lookup names the company, short banner; translation rejects mixed alphabets

Found on the real page (lookups 2026-10-22, about 0.0002 USD each):
- "paramount": the model offered PSKY (Paramount Skydance) and PARA, "former Paramount Global
  ticker"; the SEC list now gives PARA to Banzai International, Inc., and the page showed that
  company as a green exact match. The lookup schema now asks for each candidate's own
  company_name, and code drops a candidate whose SEC title does not name the same company
  (every word of the shorter name in the longer, so "Skydance Corp" fits "Paramount Skydance
  Corporation" and "General Mills" does not fit "General Motors"); the log says why.
- "chrysler": the model's reason ran to sixteen words ("is a subsidiary of Stellantis, which is
  listed in the US and not separately by Chrysler"); the prompt asks for at most ten words and
  code replaces a reason over twelve words with "is not listed in the US on its own".
Found in the real translations of the Microsoft report: words mixing two alphabets
("Vердикt", "Komitето", "krītа" in Lithuanian, "ИT", "капex" in Russian; older copies have
"заkладывает", "бottлеров", "típично"). Such a word now sends the section back once with the
stricter note. Checked with the fake client only; the lookup change needs one live lookup of
"paramount" and "chrysler" (under 0.001 USD) to confirm.

## 2026-10-22 — pre-release P1: the shared output schema is refused by the API (no change in behaviour)

The paid check of `SHARED_OUTPUT_SCHEMA=on` on NVDA (the same pack as the morning run,
340f5b779ac9) failed before any generation: every analyst call came back with HTTP 400
"The compiled grammar is too large, which would cause performance issues. Simplify your tool
schemas or reduce the number of strict tools." Nothing was billed (0 tokens, 0.00 USD). The
envelope has 5 union parameters and 0 optional ones, within the documented explicit limits
(16 and 24); the grammar of five full evaluator schemas exceeds an internal size limit that the
docs mention only as "Schema is too complex" / compiled grammar size. Not a transient error, so
no retry. Decision by the rule fixed before the run: the shared schema stays off; the eval of it
(P2) was not run, since every attempt would fail the same way. Each analyst keeps writing its own
cache entry (about 0.08 USD a run that a working shared prefix would save).

## 2026-10-22 — reports end with a collapsed glossary; the translator no longer sees it (D5)

What changed (no analyst, committee or translation prompt text changed): report.md ends with a
collapsed glossary of the terms it uses (translate/glossaries/english.md, the same 101 terms plus
"done / failed"). A translation takes that block off before sending sections to the model and
appends the target language's block (or keeps the English one with a one-line note when the
language has no glossary file). The cost table says "done" / "failed" instead of "success" /
"error"; the Russian and Lithuanian glossaries define these words, so the translator gets them
as terms for the cost section. The page shows the glossary and the cost table collapsed.

Expected effect: the copy's status column comes back translated (it stayed "success" in the
NVDA copy of 2026-10-22); the glossary is never paid for or altered by the model. Checked with
the fake client only.

## 2026-10-22 — translation: Lithuanian by default, its number formats, a draft Lithuanian glossary (D3)

What changed: Lithuanian is the default language on the page and in `python -m translate`; the
page remembers the last choice in the browser. The number check reads Lithuanian formatting
(decimal comma, spaces or no-break spaces between thousands, "5,3 %", tūkst./mln./mlrd./trln.,
"proc." as a percent, "procentinio punkto" as percentage points, "kartų", dates as
"2024 m. gegužės 30 d."); the Russian cases are unchanged. translate/glossaries/lithuanian.md
drafts the same 101 terms as the Russian glossary, every row marked "draft, review
pending"; with it the translator gets Lithuanian terms and analyst names for the first time. The
translation prompt is unchanged.

Expected effect: a Lithuanian copy uses one name per analyst and the glossary's terms; numbers
written the Lithuanian way are not rejected. Risk: the glossary is a machine draft; a person
fluent in Lithuanian must review it. Checked with the fake client only; no Lithuanian translation
has been paid for yet (about 0.03 USD for one report).

## 2026-10-22 — company lookup: exact match or related company (D2; lookup prompt and schema, not an analyst)

What changed: the lookup call (Haiku 5.5, web/resolve.py; it never touches the data pack or the
analysts) now answers per candidate match_type ("exact" or "related"), relation (a few words,
e.g. "major investor in OpenAI") and share_class, and for the query query_name,
is_private_or_not_listed and a reason. Its prompt says what each type means and asks for no
candidates rather than a guess. Code keeps checking every ticker against the SEC list and the
filing history, orders exact, related, then companies that cannot be analyzed, and writes the
banner ("OpenAI is a private company and files no reports with the SEC. Related public
companies:"). A run started from a related card says so in the report title and on the page
("Microsoft Corp (found as a company related to OpenAI)"); the relation never enters the pack.
Every lookup is logged at INFO (query, the model's candidates, kept or dropped and why).

Expected effect: "openai" shows Microsoft and Nvidia as related companies under the banner
instead of as unexplained suggestions. Risk: the model may call a brand owner "related" or a
partner "exact"; the label then misleads, but the SEC checks still stop anything that cannot be
analyzed. Checked with the fake client only (tests/test_resolve.py); no paid call. One lookup
costs about 0.0002 USD, so the author's manual checks of "openai", "chrysler" and "anthropic" on
the real page cost under 0.001 USD.

## 2026-10-22 — prompt cache: one output schema for all analysts, behind SHARED_OUTPUT_SCHEMA (D1; request change, off by default, NOT measured)

Finding, from the author's NVDA run of 2026-10-22 (its run log) and the 2026-10-21
Coca-Cola run: every analyst wrote 10,030-10,677 tokens to the cache and read 0. The cached text
was byte-identical (19,847 characters, same pack hash), the model, tools (none), thinking and
effort settings were the same, and the four parallel analysts started a few milliseconds after
the Valuation Analyst's assumptions step had returned, so neither the layout, the timing nor the
TTL (5 minutes, the whole fan-out took 67 s) is the cause. The writes differ per analyst by the size of its output
schema (a fit over the five calls: about 8,600 tokens + 0.57 tokens per character of schema JSON).
The structured outputs docs (checked 2026-10-22): "Claude automatically receives an additional
system prompt explaining the expected output format ... Changing the output_config.format parameter
will invalidate any prompt cache". That prompt sits ahead of our breakpoint, so five schemas are
five prefixes. The minimum cacheable length (512 tokens for Sonnet 5.5, prompt caching docs,
checked 2026-10-22) is far below the prefix. The committee sends no cached prefix: it is one call
with nothing to share. The fake client used by the tests keyed its simulated cache on the system
text only, which is why the test "step A warms the cache" passed; it now keys on everything
rendered up to the breakpoint (model, tools, thinking, effort, output schema, text) and reproduces
the five writes.

What changed (code only; no analyst or committee prompt text changed): `SHARED_OUTPUT_SCHEMA=on`
sends one envelope schema, `AnalystOutput`, to all five analyst calls (fields business_model,
forensic, valuation_assumptions, valuation, pre_mortem, each the analyst's own schema or null;
5 union parameters, 0 optional, within the documented limits of 16 and 24). The user message,
after the breakpoint, ends with one generated line: "Put your answer in the output field <field>
and set every other field to null." Code rejects an answer in another field or a null own field
(one retry, as for any validation problem) and unwraps the field, so results, reports and the eval
see the same dicts as before. Default off.

Expected effect (estimate from config.py prices, Sonnet 5.5: input 2 USD/MTok, cache write 1.25x,
cache read 0.05x): the NVDA run cost 0.577 USD, of which cache writes 51,529 tokens = 0.129 USD.
With the shared schema the prefix grows to about 16,400 tokens (8,600 + 0.57 x 13,836 characters of
the envelope schema): one write 0.041 USD + four reads 0.007 USD = 0.048 USD. Saving about
0.08 USD a run (about 14%): about 0.50 USD instead of 0.58 USD for the same NVDA pack. Output tokens
(most of the cost) are unchanged.

Risk to watch: the model now sees all five schemas in the format prompt. It could fill the wrong
field (code catches it and retries, each retry costs a call) or let another analyst's field
descriptions colour its answer. This is why it is off until measured.

How to check: one paid run, same NVDA pack (the daily cache holds it on the same day; otherwise any
ticker): `$env:SHARED_OUTPUT_SCHEMA="on"; venv\Scripts\python.exe main.py NVDA`, about 0.50 USD.
Expect in the cost table: the assumptions step writes about 16k tokens, the other four read about
16k and write 0, and no "invalid result" retry in the log. If that holds, one eval pass
(`$env:SHARED_OUTPUT_SCHEMA="on"; venv\Scripts\python.exe -m eval.run_eval --reps 1 --batch
--variant shared_schema`, about 1.4 USD) before making it the default.

## 2026-10-21 — live page run on Coca-Cola after C1-C8, and the fixes it led to

The author's OK for a paid run (0.667 USD) and its Russian translation (0.022 USD), through the page in
headless Chrome, code 474b12d. Result: weak case, medium confidence (acceptable by the label);
28 of 34 quoted numbers match, 1 wrong; 20 of 25 calculations reproduced; 3 of 310 prose numbers
without a source; cache reads 0 (each analyst has its own schema).

Seen on the page: "1 filing event"; "At today's price of $93.49 ... about 4.9% a year"; "Revenue
growth for five years needed to earn 7.5% a year: 21.5%"; the 10-Q filed 2026-07-29 "still missing
from SEC company facts 84 days later"; "Save report (.md)"; "Report in Russian"; the metadata table
header "Параметр | Значение"; no section kept in English.

C4 measured once: the copy uses one Russian name per analyst in the text, but the translator
headed the forensic section "Криминалистический аналитик" instead of the glossary's
"Аналитик-криминалист". Fixed in code: the heading of an analyst's own section is now set from the
glossary after the translation ("### Аналитик-криминалист (Forensic Accountant)"; square brackets
when the English name has brackets of its own). Also found: report.md wrote the pack path
derived.valuation.pe as "calculated › Valuation Analyst › P/E", and the copy carried the analyst's
name into the basis; inside a path an analyst key is now a plain word (6718c25).

The 5 calculations not reproduced in that run, read one by one: 4 quote a number their basis does
not cite (a 32-34% range, the 3.1% yield, about 2% growth, a 15.8% ratio of two cited
differences), which the check is right to flag. One was the check's fault: the basis
"derived.valuation.pe x 0.5 = 29.36 x 0.5" used the letter x for multiplication, so the stated
50% (0.5) went unexplained. "x" and "×" now multiply. Mutation test unchanged (correct 318/318,
wrong factors caught 1256/1272 = 98.7%, flipped growth 132/133); v3_release regrade unchanged
(198 of 211).

The report's title "Stock Autopsy: <company>" is also put back by code after the translation
(the copy had "Разбор акций").

## 2026-10-21 — translation: a section kept in English says why (C7)

Investigation (free, from the logs of 2026-10-17): in the Tesla copy the section "Business Model
Analyst" was rejected twice as "left in English"; the DEBUG lines show the model returned the
English section unchanged both times. Not a number-check rejection, a timeout or a parse failure.
The likely cause is the old prompt rule "keep the analyst names in English" on a section that
starts with an analyst's name; C4 removed that rule (unmeasured).

What changed: the fallback was marked but gave no reason ("This section could not be translated").
The mark now says "Kept in English: the translator returned the English text, twice. The English
original follows." (or the numbers that changed, the structure that changed, the wrong language).
The page reads the marks back from the copy and names each section with its reason, also for a
translation made earlier; the CLI prints them. No change to what the translator is asked.

## 2026-10-21 — translation: one translated name per analyst (C4)

What changed: the translation prompt (our translation code, not an analyst prompt) said "Keep the
analyst names in English"; it now asks for the names the term list gives, the same name every
time, with the English name in brackets only in the heading of the analyst's own section. The
Russian glossary has a last section with ten names (the eight analysts of the source of truth, the
valuation assumptions step, the committee), marked as drafts for review. The
heading check no longer lets an analyst's heading come back in English.

Why: the 2026-10-17 Russian copy of the Coca-Cola report mixed "Аналитик оценки" with "Business
Model Analyst (аналитик бизнес-модели)".

Risk to watch: a heading kept in English is now rejected, asked again and, if it fails twice, the
section stays in English and is marked. Not measured: no paid call in this session; one Russian
translation of a saved report (about 0.03 USD) shows it.

## 2026-10-21 — "what the price assumes" writes the price with its currency (C3)

What changed: the Python sentence `valuation_math.price_assumes` said "At today's price of 93.90";
it now says "At today's price of $93.90" (the pack's price currency; another currency is written
after the number, an unknown one leaves the bare number). `valuation_math.inputs` gains `currency`.

Effect on the model: the committee and valuation step B read this sentence and the inputs as data;
the change is formatting only, no number changes, no prompt changes. No paid eval was run.

## 2026-10-21 — reverse DCF names the return its growth is needed for (C2)

What changed: `valuation_math.reverse_dcf` gains `discount_rate` (the base-case rate the model
chose) and `years` (5). report.md says "to earn the base-case discount rate of 8.0% a year,
revenue would have to grow about 23.6% a year for five years"; the page row reads "Revenue growth
for five years needed to earn 8.0% a year" instead of "Revenue growth the price implies".

Why: the Coca-Cola result (2026-10-17) put "the price only makes sense if revenue grew about 23.6%
a year" next to "about 5% a year if things go as expected"; the reader could not see that the
23.6% is the growth needed to earn the model's 8% discount rate, not to break even.

Effect on the model: valuation step B and the committee read `valuation_math` as data; they now
see two more numbers. No prompt changed. The committee sentence itself is model text and is not
touched. No paid run.

## 2026-10-21 — data pack: the freshness note counts the days since the missing filing (C1)

What changed: the data quality note for a filed quarter that SEC company facts lack said "is not
yet in SEC company facts"; it now says "is in the SEC filing history but not in SEC company facts
78 days later". The page and report.md say the same in words. Only the golden Coca-Cola pack
changes (that one note); the other four golden packs are byte-identical after re-freezing.

Why: a fresh fetch on 2026-10-21 (no cache) showed the gap is not our filter. Coca-Cola's 10-Q for
the quarter ending 2026-07-03 (filed 2026-07-29, inline XBRL) is absent from company facts: none of
its facts carry that filing's accession number, and the latest period end of any us-gaap fact is
2026-04-03. Snowflake, Kraft Heinz, Comcast, Plug Power and Tesla have their latest 10-Q in
company facts within days. "Not yet" suggested a short lag; the day count says how old the gap is.

Effect on the model: the note is pack data the analysts read; wording only, no number changes.
No paid run. Regrade of v3_release before and after: identical (198 of 211 calculations
reproduced, 7 wrong numbers on exact paths in 379 data claims).

Left for the author: reading the missing quarter from the filing's own XBRL instance (as
`datalayer/extensions.py` already does for receivables) would close the gap; that is a data-layer
feature, not done.

## 2026-10-17 — live run through the page: Coca-Cola, then a Russian translation (reviewed 2026-10-21)

No behavior change; a check of the page after M1-M15 on code 922c655. Headless Chrome typed
"Coca-Cola", picked Coca Cola Co and translated the result on the page.

- Cost and time: run 0.656 USD, 173 s (cache reads 0, as expected while each analyst has its
  own schema); translation 0.021 USD, 39 s, no section kept in English, no number rejection.
- Result: weak case, medium confidence (acceptable by the label). 27 of 31 quoted numbers
  match, 1 not in the cited data; 24 of 27 calculations reproduced; 5 of 299 prose numbers
  without a source.
- Seen on screen: tagline (M1); lookup offered Coca Cola Co and Keurig Dr Pepper and flagged
  Coca-Cola Europacific Partners as a 20-F filer before any paid call (M7); "Analyzing Coca Cola
  Co" while running (M11); card states waits / working / done and capitalized verdict badges
  (M9, M10, M12); the price sentence "revenue growth slowing from 4% to 3% a year" (M14); data
  quality with the freshness gap first and restatements grouped (M2); live updates at 0:02,
  0:25, 1:00 and 1:59 and the result after 3 minutes (M4: no failure shown; the server log does
  not record reconnects, so a reconnect cannot be ruled out). "DCF not computed" did not occur
  (M8 untested live). The download name is covered by a test, not by the live run (M3).
- Fixed after the review (5037b0f): "1 filing events" on the data pack step; "Report in
  Русский" above the translation, now "Report in Russian".
- Left for the author: the price sentence says "At today's price of 93.90" without a currency
  while the rest of the page writes $93.90. The sentence reaches the committee, so changing it
  is a behavior change, not made while 67404ad is unmeasured.

## 2026-10-17 — calculation check: stated constants, parts of a formula, the sign of a difference (M15)

- **What (grading only, no model input changes):** in the check of calculated (DERIVED) claims,
  (1) a constant the basis formula uses as an operand ("0.5 * pe") counts as explained when the
  statement states it ("a 50% fall"); a value the model quotes in brackets ("pe (29.49)") and the
  shape constants 0, 1 and 100 do not count; (2) every part of a basis formula (a numerator, a
  denominator, a bracket) counts as reproduced; (3) a difference of two data terms counts with
  both signs, because its sign is the writer's convention ("costs fell by $3.0 billion" written
  as old - new), while a change such as a / b - 1 keeps its sign.
- **Why:** three correct Coca-Cola statements of the 2026-10-17 web run were "not reproduced".
- **Mutation test of calculated claims (new, tests/derived_mutations.py, 5 golden packs, 318
  claims):** correct claims reproduced 280/318 before, 318/318 after (the "spread" kind, the KO
  case, 3/29 -> 29/29; net debt over income with a three-term numerator 5/14 -> 14/14). Errors
  caught, before = after: x1.1 313/318, x0.75 313/318, x2 317/318, x10 313/318 (98.7% overall);
  a flipped direction on a growth rate 132/133. A flipped direction on a difference ("rose by"
  for a fall) is not caught, before (both orders of a pair were already accepted, and the KO
  "spread" accepted only the flipped one) or after.
- **DATA claims mutation test:** that code did not change; 208 golden values, correct 100%
  matched, errors caught x1.1 93.8%, x0.75 96.2%, x2 100%, x10 100%, flipped sign 100%.
- **Regrade of `v3_release` (free):** calculations reproduced 195/211 -> 198/211 (SNOW rep1 +2,
  KHC rep0 +1); no grade, verdict or wrong-number count changed.

## 2026-10-17 — "what the price assumes" sentence: no "4% to 4%" ranges (M14)

- **What:** the Python sentence on what the price assumes, which valuation step B and the
  committee also read, now says "revenue growth of 4% a year" when the first and last year are
  equal (it said "4% to 4%"), and "slowing from 5% to 3% a year" / "rising from ... to ..." when
  they differ; the same for the operating margin ("rising" / "falling"). Numbers unchanged.
- **Expected effect:** none on verdicts; clearer text for the reader. Not evaluated.

## 2026-10-17 — data pack: split-history note reworded, reverse splits, missing share counts

- **What:** three data-layer changes from review 2. (1) Reverse splits beyond 1-for-10
  (1/12 ... 1/100) are now splits; before, their share counts stayed 12-100 times too high.
  (2) A missing cover-page share count takes the same fallback as a stale one (the latest
  diluted weighted-average count); Meta and Alphabet now get a market value. (3) The note for
  a split-history entry that is not a split now reads "not treated as a stock split: a
  corporate-action price adjustment (for example a spin-off or a special or stock dividend)"
  instead of naming a spin-off only.
- **Golden packs:** only Comcast's changes, in that one note line (hash `fe84c1acd56c` ->
  `17ea6b1887e1`); the regrade finds the old pack in git history. KO, SNOW, KHC and PLUG are
  unchanged. Expected effect on answers: none measurable; not evaluated.

## 2026-10-17 — report translation (M13, variant A): measured on three saved reports

- **Measurement (author's OK, Haiku 5.5, real Russian glossary of 96 terms):** final runs with
  all checks of the day (number check with labels, durations and dates in words; structure
  check):

  | Report | Cost | Time | Sections | Kept in English | Number rejections | Retries |
  |---|---|---|---|---|---|---|
  | Coca-Cola (KO, 2026-10-17) | 0.031 USD | 63 s | 19 | 0 | 0 | 4 (3 left in English, 1 structure) |
  | Tesla (TSLA, 2026-10-17) | 0.025 USD | 43 s | 19 | 1 (Business Model, English twice) | 0 | 3 |
  | Comcast (CMCSA, 2026-10-16) | 0.023 USD | 41 s | 19 | 0 | 0 | 1 (left in English) |

- **What the first runs found (and fixed the same day):** the first Coca-Cola run kept 5 of 19
  sections in English after 10 number rejections, all false (Q4, "10-year", "5-year", a date
  written the Russian way) -> labels, durations and dates are now compared as words and dates.
  The next Coca-Cola and Tesla runs passed the number check with two defects it cannot see: the
  translator's own comments with a repeated heading, and a stub table with "..." before the real
  one -> a section must keep its count of headings, table rows and list items.
- **Remaining:** Haiku at low effort sometimes answers an analyst's section in English (6
  answers in the final three runs); the retry fixes most. The product name in the title was
  translated once ("Стоп-анализ акций"). The author reads one translation and reviews the
  glossary.
- **Cost of the whole measurement:** 0.155 USD (six report translations, two of them before
  the fixes).

## 2026-10-17 — report translation (M13, variant A): code before the measurement

- **What:** `translate/` translates a finished report.md section by section with Haiku 5.5
  (low effort, a medium-effort retry), on the page or by `python -m translate`. New against
  Startup Autopsy's translator: a number check per section (same value and scale, retry once,
  then the section stays in English) and a glossary per language. It does not change any
  analysis answer: it runs after the report is written and never touches report.md.
- **Checked so far (free):** unit tests with a fake client and a test glossary; the number
  parser on all seven saved reports (about 7,000 numbers): no section rejected when compared
  with itself or with a mechanical Russian rewrite of its numbers.
- **To measure (author's OK needed, about 0.1 USD):** translate the saved KO, TSLA and CMCSA
  reports into Russian with the real glossary; record cost, time, sections kept in English and
  number-check rejections here; the author reads one. The real Russian glossary
  (`translate/glossaries/russian.md`) is drafted first and reviewed by the author.

## 2026-10-16 — release eval `v3_release`: 5 golden cases x 2 reps after the data fix and the label revision

- **Setup:** HEAD `b9b0282` (P2 bundle, corrected Comcast pack, revised labels), Sonnet 5.5 at
  the default effort, `--batch`, judge Haiku 5.5 by majority of three. Estimate 3.0 USD (cap
  4); **cost 2.67 USD** (869k input tokens, 28% read from cache; 387k output), 36 minutes.
- **Verdicts:** primary hit 7/10, acceptable 9/10, error cost 0.40. A constant "weak case" on
  the same attempts gets primary 4/10, acceptable 6/10, error cost 0.80: for the first time
  the committee verdict beats the constant answer.

| Case | rep0 | rep1 | Forensic | Implied annual return |
|---|---|---|---|---|
| KO | weak | weak | adequate, adequate | 5.0%, 4.9% |
| SNOW | weak | weak | adequate, adequate | 3.8%, 3.4% |
| KHC | weak | weak | weak, weak (not red-flagged) | 7.9%, 7.6% |
| CMCSA | conditional | conditional | adequate, adequate | 12.2%, 13.8% |
| PLUG | weak (wrong) | red-flagged | RED_FLAG sev 5, WEAK sev 4 | not computed (debt unknown) |

- **Plug Power is unstable at the committee, not only at Forensic:** rep0 got a severity-5
  red flag from Forensic and still said "weak case" (and missed the dilution must_find);
  rep1 got WEAK from Forensic and said red-flagged. Across all runs since P2: red-flagged in
  2 of 4 attempts.
- **Judge:** must_find 9/10 (PLUG rep0, dilution), must_not clean 9/10 (SNOW rep0 again: "the
  company reported no debt" in the early years, which the pack has as not reported; the
  absent-as-zero linter flagged the same attempt).
- **Grounding (after the parser fix below):** 7 wrong numbers on exact paths in 379 data
  claims; 195 of 211 calculated claims reproduced; 51 of 2,696 prose numbers without a
  source; 4 unknowns read as zero.
- **Comparison:** v2_before 4/5 primary, 5/5 acceptable, error cost 0.20; v2_after 2/5, 4/5,
  1.00 (one rep each, the old Comcast pack). Both v2 runs read Comcast at a P/E of 8.3 and an
  implied return of about 12%; with the corrected pack the price is lower relative to the
  cash flows and the implied return 12-14% a year, verdict unchanged. In both v2 runs the
  Valuation analyst noticed the 2009 share count against Yahoo's 3.55 billion and said so; the
  system did not act on it then.
- **Checks fixed on this run (no API cost, all variants regraded):** a dash between two
  numbers ("58.1%-62.1%") is a range, not a minus sign; "a 2-point step" is two percentage
  points. A regrade now checks each attempt against the pack it saw (the committed pack whose
  hash matches the trace), not against a pack rebuilt after a data fix.

## 2026-10-16 — labels: Comcast and Plug Power revised after two reviews (eval instrument, no system change)

- **Comcast:** primary conditional case, nothing acceptable (strong case dropped: with flat
  revenue and about 84 billion of debt the risks do not support interest on their own);
  rationale numbers from the corrected pack (P/E about 6.7, FCF yield about 27%).
- **Plug Power:** still red-flagged only, strict on purpose. Rationale and must_find now rest on
  liquidity and dilution (cash about 0.16 billion against an operating cash outflow of about
  0.48 billion over twelve months, operating loss larger than revenue since FY2023, about
  fourfold share count since FY2020); the 2021 non-reliance notice, late filings and the 2022
  auditor change stay as history. The old rationale's "operating loss larger than revenue
  every year since 2021" was wrong (not in FY2021 or FY2022).
- **EDGAR check of the four amended annual reports in the pack window (2026-10-16, SEC
  only):** 2017-05-01, 2023-05-01 and 2025-04-30 only add the Part III information
  (executive pay and governance, certifications; no new numbers): not red flags. 2022-03-14
  amends the FY2020 annual report (MD&A for the 2019-2020 quarters; the material weakness
  extended to 2018 and 2019): part of the 2021 history. New must_not: treating the Part III
  amendments as accounting red flags.
- **Label status for both:** drafted by Claude Code from the pack under the author's
  delegation; reviewed in two independent reviews; not blind-labelled by the author.

## 2026-10-16 — data pack: spin-off adjustments are not splits, stale cover-page share counts are not used (data change; Comcast's pack corrected)

- **Found by:** the independent review of the pre-publication audit. Comcast's pack used a
  cover-page share count dated 2009-12-31 (company facts hold no total since Comcast reports
  the count per share class) and applied Yahoo's 2026-01-05 entry of ratio 1.067 (the price
  adjustment for the Versant spin-off) as a stock split. Market cap came out 92.7 billion
  against Yahoo's 76.9; every share count filed before 2026-01-05 was 6.7% too high, which
  also produced two fake share-count restatements (FY2023, FY2024). The conflict with Yahoo
  was recorded but resolved for the 16-year-old EDGAR value. The grounding checks could not
  see it: the model quoted the pack faithfully; the pack was wrong.
- **Changed (code, no prompt):** a split-history ratio strictly between 0.8 and 1.25, or one
  that is not a simple fraction p/q with q at most 10, is not a split: share counts are not
  adjusted for it, and `period_notes` names it. A cover-page share count dated more than 400
  days before as_of is not used: the latest diluted weighted-average share count from the
  filings (latest period end, shortest period) stands in, with a note. `compare_sources`
  uses the fresher source when the EDGAR value is stale and the two differ by more than 5%,
  and records why. Golden-pack invariants: market cap within 5% of the frozen price
  snapshot, share count dated within 400 days, no adjustment applied as a split, no
  share-count restatement equal to a split ratio.
- **Comcast's pack, rebuilt from the same frozen raw files:** shares 4.403 B (2009) ->
  3.570 B (Q2 2026 diluted average); market cap 92.7 -> 75.1 billion (Yahoo 76.9); P/E
  8.28 -> 6.71; P/FCF 4.53 -> 3.68; FCF yield 22.1% -> 27.2%; EV/EBIT 9.24 -> 8.28;
  EV/EBITDA 4.97 -> 4.45; EV/revenue 1.36 -> 1.21; diluted shares FY2016-FY2022 6.7% lower
  (FY2022 4.43 B, as filed); the two fake restatements and the shares conflict are gone.
  KO, SNOW, KHC and PLUG come out byte-identical.
- **Effect on earlier measurements:** both P2 variants saw the old Comcast pack, so their
  comparison is like for like, but their Comcast numbers (implied return about 12.2% a year)
  are not. The implied return is computed at run time and will rise; pending the next eval
  run.

## 2026-10-15 — P2: what the price assumes + plain-language committee fields (prompt, schema and valuation math change; NOT measured yet)

- **Changed (one bundle, to save budget):** the reverse DCF also solves the implied annual
  return (`valuation_math.implied_return`) and Python writes `valuation_math.price_assumes`;
  the Valuation focus judges what the price assumes, not the DCF-vs-price gap at one chosen
  rate; the committee principles say the same; committee schema gains `headline`,
  `reasons_for`, `reasons_against` (D6/H1; evaluator cards use `key_finding`, H2).
- **Measurement plan:** `v2_before` = HEAD before this change (67404ad prompts), 5 golden
  cases x 1 rep, --batch, started 2026-10-15 late evening (~1.4 USD); then `v2_after` with
  this bundle, same setup (~1.4 USD). Compare verdicts on CMCSA (weak case is wrong) and PLUG
  (red-flagged only), and grounding on all.
- **Expected:** fewer "weak case" verdicts where the price assumes little (CMCSA); KO and SNOW
  unchanged or conditional; no change to grounding.
- **`v2_before` result (old code, which includes 67404ad; 1.47 USD, 32 minutes):** primary hit
  4/5, acceptable 5/5, error cost 0.20; CMCSA conditional case (right), PLUG red-flagged with
  Forensic RED_FLAG at severity 5 (right), KO weak (acceptable, not primary), SNOW and KHC weak.
  So the old prompts already separate the new cases; P2 has to keep that and is judged on KO.
  must_find 5/5, no must_not 5/5. Grounding (after the date fix below): 4 wrong numbers in 170
  data claims, 1 found nowhere, 120 of 130 calculated claims reproduced, 2 unknowns read as zero
  ("no dividend" on PLUG and SNOW). Against M5 for 67404ad: far more DERIVED claims (130 in 5
  attempts against 89 in 6) and no rise in wrong numbers: the plain-words / DERIVED change did
  what it was meant to.
- **`v2_after` result (this bundle; 1.49 USD):** primary hit 2/5, acceptable 4/5, error cost
  1.00 (before 0.20). CMCSA conditional (right; implied return 12.2% a year), KO weak
  (acceptable; the price implies about 5.1% a year if the base case comes true), SNOW weak,
  KHC conditional (acceptable), **PLUG weak instead of red-flagged**. The PLUG change comes from
  the Forensic Accountant, whose prompt did not change: WEAK with a severity-4 flag here
  against RED_FLAG at severity 5 before, and the committee followed it. Grounding: 3 wrong
  numbers in 167 data claims, 110 of 123 calculations reproduced, prose without a source 8 of
  1,280 (25 before), 4 unknowns read as zero (SNOW "no dividend" x3, CMCSA once).
- **Reading:** the headline scores fell (primary 4/5 -> 2/5, acceptable 5/5 -> 4/5, error cost
  0.20 -> 1.00): Kraft Heinz moved from weak to conditional (acceptable) and Plug Power from
  red-flagged to weak (wrong, traced to the Forensic analyst, whose prompt did not change). One
  rep per case cannot separate the bundle from noise. The valuation framing behaves as
  intended where it can be seen (a 5% implied return on Coca-Cola reads as expensive).
  **Correction (2026-10-16):** both variants used a Comcast pack with a wrong share count
  (see the data pack entry above), so the comparison is like for like but the Comcast figures
  (implied return about 12.2% a year) are not right; Comcast's numbers are pending the next run.
- **Decision (2026-10-16, delegated):** keep the bundle (the web page needs the plain-language
  fields). Open: Forensic's red-flag call on PLUG is unstable (RED_FLAG 1 of 2 attempts); two
  more PLUG attempts (~0.6 USD) would show how often, before any Forensic prompt change.
- **Grading fix found on this run:** "June 30, 2026", "30 June 2026" and "SIC 3620" were read as
  quantities (6 of PLUG's 7 "wrong numbers"); now skipped. Regraded baseline and effort_medium
  are unchanged apart from prose counts.

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
- **Decision (2026-10-15, delegated by the author):** keep the default effort; medium is not the default.

## 2026-10-15 — eval instrument: judge by majority of 3, substance-only must_find (no system change)

- **Changed:** the judge answers three times and each statement is decided by majority
  (`JUDGE_VOTES`); the SNOW must_find "losses in every year" now reads "loss-making on a GAAP
  basis" (author-approved), as the author first asked.
- **Why:** one judge answer flipped borderline statements between passes on identical text
  (must_find 6/6 -> 4/6; a must_not on SNOW rep1 judged present from "debt of 2.28B appeared
  after FY2024", which does not claim zero debt before; checked by hand).
- **Baseline regraded:** must_find 6/6, must_not clean 6/6; votes unanimous except one
  1/3 must_not on KO rep1 (outvoted). Judge cost about 0.003 USD per attempt.

## 2026-10-15 — M5 baseline: golden tickers, 2 reps each (no prompt, schema or model change)

- **Setup:** Sonnet 5.5, default effort, `--batch`; variant `baseline` in
  `.claude/hillclimb/stock/` (git-ignored). Labels in `eval/cases.json` (author-approved;
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
  the substance is there, the label is over-specific (the author asked for "losses").
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
