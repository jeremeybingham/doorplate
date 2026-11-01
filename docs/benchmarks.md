# Benchmarks: accuracy

Accuracy of doorplate on the benchmark suite and the older sets, with the caveats; speed, size and memory are on [their own page](speed-and-size.md).
The scripts are in `benchmarks/` (`docs/running-benchmarks.md`) so every number can be rerun. usaddress
(the Python CRF library, 0.5.16) is one reference point, not the frame: it is
the tool people know, and the two libraries do different jobs (usaddress labels
tokens; doorplate also standardizes, builds a key and a slug, and reports
diagnostics).

This library formats and parses; it does not validate deliverability. None of
the figures below say an address exists or can receive mail.

This page holds the results. Which benchmark is which (the suite, the [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark), the speed and size
scripts, the checks on private data) and how to run each: the table in the project README
([Benchmarks](../README.md#benchmarks)) and [`docs/running-benchmarks.md`](running-benchmarks.md).

The benchmark suite that ships in the repository (`benchmarks/suite/v1/`, the specification in
`docs/benchmark-suite.md`) leads this page. It is 19,586 labeled addresses that neither
library's rules, model or tests were made from, run under a fixed 4-CPU, 8 GB profile, and it holds both
libraries' blind spots on purpose. The other sets below are older and each favors one side for a reason
given with it.

**Which build.** The suite and speed figures are from `main` at `c68760e` (0.5.1-dev, 2026-11-01); since 0.5.0 `main` has had speed changes only, and the suite's
accuracy sections are identical to the 0.5.0 run. The geocode, usaddress-test-file and Florida figures are from the 0.5.0 build.
**Machine:** Intel Core i9-9900K (14 threads), 49 GB RAM, Linux 6.18 on WSL2. The suite's runner pins 4 CPUs and
8 GB (its reference profile), and the Python speed runs were pinned to the same 4 CPUs with `taskset -c 0-3` and
`RAYON_NUM_THREADS=4`; the Rust (criterion) and size runs were not pinned and use all 14 threads where they use threads at all.
Rust 1.91, Python 3.13 (speed and size runs in a virtual environment), usaddress 0.5.16, built with `--release`.

## In short

| | doorplate | usaddress |
|---|---|---|
| Benchmark suite, `natural` stratum (16,001), whole address (coarse) | 98.5% | 96.1% |
| Benchmark suite, whole suite (19,586), whole address (coarse) | 93.4% | 85.5% |
| [Geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark), dev split, whole address (coarse) | 94.3% | 88.1% |
| usaddress's own test files, whole address (coarse) | 99.1% | 100.0% |
| Addresses per second, one thread, benchmark suite inputs (`parse_tokens` / `usaddress.parse`) | 43,411 | 9,297 |
| Addresses per second, `parse_many` on 4 threads, suite inputs (usaddress has no batch call) | 137,985 | 9,297 |
| One address in Rust (median of the corpus shapes, criterion, unpinned) | 4 to 11 µs | |
| Installed size (wheel / package and dependencies) | 2.1 MB (5.0 MB unpacked) | 4.8 MB |
| Import time | 1 ms | 14 ms |

## 0.4.1 to 0.5.0

The same benchmarks on the 0.4.1 build (the tag `v0.4.1`, in its own worktree) and on 0.5.0 (the `k4` cut), on one machine, both measured the same way in
the same session: the suite and the private twin with each build's Python package, the geocode splits and
the Florida check with a command-line binary built from each tree, speed on a quiet machine (the suite's 4-CPU profile; the Python script unpinned).
0.5.0 reads many more shapes (the closed rule list of the `k4`); the key changes are in the changelog and in
[`key-format.md`](key-format.md).

| | 0.4.1 | 0.5.0 | Change |
|---|---|---|---|
| Suite, `natural` stratum (16,001), whole address (coarse) | 98.3% | 98.5% | +0.2 |
| Suite, whole (19,586) | 92.3% | 93.4% | +1.1 |
| Suite, `hard` stratum (2,585) | 54.6% | 61.8% | +7.2 |
| Suite, `hand` stratum (1,000) | 94.3% | 94.3% | same |
| Suite, the private twin: `natural` / whole | 98.2% / 92.1% | 98.4% / 93.2% | +0.2 / +1.1 |
| Fields input (`parse_fields`), whole record right | 99.1% | 99.1% | same |
| Unit number right (fields input) | 97.8% | 98.0% | +0.2 |
| Key stability, one key across two to four styles | 91.7% | 91.7% | same |
| Geocode benchmark, dev (60,522) | 94.5% | 94.3% | -0.2 |
| Geocode benchmark, train (148,173) | 94.4% | 94.2% | -0.2 |
| Geocode benchmark, test (30,622; optimistic) | 96.8% | 96.7% | -0.1 |
| usaddress's own test files, whole address | 99.2% | 99.1% | -0.1 |
| One-line Florida check (300,000 records, city right) | 94.7% | 94.7% | 0 gained, 0 lost |
| Geocode `city_diff` (train80, held-out train, dev, test) | | | 0 gained, 0 lost on every split |

The gain is in the rare shapes: the `hard` stratum (a name or recipient text around the address, boxes, a unit written oddly) moves 7.2 points and
the `natural` stratum 0.2. The geocode benchmark loses 0.2 on dev: 113 of its 60,522 strings read their street parts differently, and at least 92
of them are one rule (a letter A to D after the house number joins the number, `123 A ELM ST` is `123A`, as the reviewed sources write it;
the benchmark's labels keep the letter in the street name). No city changed. The suite does not attribute a gain to a rule, and "improves the suite
score" is not a reason for one (see below).

**Speed.** 0.5.0 is lower than 0.4.1 (Python `parse` on the golden-corpus inputs -12%, on the geocode addresses -10%; the suite's `parse_tokens` on one thread -8%,
`parse_many` on 4 threads -11%): its rules add tokenizer and tagger passes. That was accepted for the `k4`, and the engine has since been made faster than 0.4.1
(see [speed by version](speed-and-size.md#speed-by-version)); the speed figures on this page are from `main`.

**Size.** The 0.5.0 wheel is 2.1 MB (5.1 MB unpacked) against 2.0 MB for 0.4.1; the CLI binary is 6.2 MB (5.2 MB stripped); import time is 1 ms.

The suite and its tables below are the latest run; the changelog has the rules behind them.

## 0.3.1 to 0.4.0

The release that went after the rare shapes. Ordinary input did not move: the suite's `natural` stratum stayed at 98.3%, the whole suite went from 92.2% to 92.3%,
the `hand` stratum from 92.3% to 94.3% (the tokenization change: `parse_tokens` cuts like `usaddress.tokenize`, so the character-span scoring stops losing tokens to a
different cut), and fields input from 98.9% to 99.1% (unit number right 96.8% to 97.8%). The geocode splits moved by +0.1. Speed rose: Python `parse` +9% to +13%,
`parse_many` on 4 threads +14% to +21%, Rust single-address parses -8% to -30% (the work on the lookups and allocations described on the speed page). The binary grew by about half a megabyte
(the state data was folded into the core); the wheel did not move.

## MessyStreets: web addresses (held out)

[MessyStreets](https://github.com/EdGaere/MessyStreets) (Gaere and von Wangenheim, ACM SIGSPATIAL '26, DOI 10.1145/3841645.3843362) is a
benchmark for geocoders: 3 tiers of 10,000 verbatim addresses from websites' schema.org markup (the December 2024 Web Data Commons extract),
multinational. We use the US-like rows only (an explicit US country, or no country and a state and ZIP; `tools/ingest/specs/messy-streets.toml`),
locally and as aggregates (`docs/data-policy.md`; the data is not in the repository). **Gold** (existence checked against OpenStreetMap or
OpenAddresses, components judged by an LLM) and **silver** (existence only) are held-out checks: their rows are never read or queued for review.
**Raw** (a random sample, neither check) is the work list for rules.

`tools/harness/messy_score.py` parses the one `input` string a geocoder would get and compares ZIP5, state, city and street name with the
page's own markup fields (street name: with the street of the existence record; gold and silver only). Rows with an empty or `nan` label for a
field are left out of that field's count (the count is in parentheses).

| The dataset's `input` (0.5.0-dev, `7bc011f`) | Rows | ZIP5 | State | City | Street name |
|---|---|---|---|---|---|
| Gold (held out) | 4,270 | 99.9% (4,218) | 98.3% (4,128) | 91.7% (4,254) | 88.3% (4,270) |
| Silver (held out) | 2,509 | 99.8% (2,205) | 97.9% (2,416) | 88.8% (2,493) | 87.8% (2,509) |
| Raw (work list) | 2,316 | 99.8% (2,041) | 97.8% (2,246) | 88.6% (2,298) | not available |

The dataset's `input` string carries the markup's literal missing-value strings (`NaN`, `undefined`, `null`): the ingest keeps them out of the
records, and `--joined` parses the cleaned fields joined with commas, the way the review queue does (no country
word). Measured on `main` (0.5.1-dev, `2e5441e`), the same rows:

| Cleaned fields, joined (`--joined`) | Rows | ZIP5 | State | City | Street name |
|---|---|---|---|---|---|
| Gold (held out) | 4,270 | 99.9% (4,218) | 98.8% (4,128) | 97.7% (4,254) | 89.6% (4,270) |
| Silver (held out) | 2,509 | 99.8% (2,205) | 98.4% (2,416) | 97.7% (2,493) | 90.2% (2,509) |
| Raw (work list) | 2,316 | 99.9% (2,041) | 98.4% (2,246) | 97.8% (2,298) | not available |

The city figure moves most (88.6% to 97.8% on raw): 303 of the 2,315 raw rows carry a missing-value string in the city, state or ZIP, and
70% of them leave text unparsed with it and none without. This is not a gain in the parser: the two tables parse different strings. Use the
first for comparison with other geocoders on the dataset's own input, the second for the work list.

Read with care: the labels are the web page's own markup, not hand-checked, so a miss is a question and not a bug count; a page's locality can be a
neighbourhood or a county; the street-name match is lenient (every word of our street name is a word of the verified street). These are not
accuracy figures for doorplate and are not comparable with other parsers' scores on other labels. They are recorded per release to see whether a
rule change moved them; the gold and silver rows are not tuned to. Retake with `python tools/harness/messy_score.py --confirm`.

## The benchmark suite

`benchmarks/suite/v1/` holds 19,586 labeled addresses and `python benchmarks/suite.py all` scores doorplate
and usaddress on them (the runner, how to run it and the resource profile: `docs/running-benchmarks.md`).
It was built once, audited, and is frozen: `v1` is never edited, and label errors found later go into `v2`
with both versions' scores kept here. Rows are anonymized National Address Database points (the real street,
city, state and ZIP; invented house and unit numbers), Census TIGER street names for the six states NAD
lacks, templates for PO boxes, routes, military and general delivery, and 1,000 hand-labeled shapes. The
gold labels come from the field each token was written from, never from either parser. Run on 4 CPUs and
8 GB (Linux, the Intel i9-9900K of the machine above, pinned by the runner), doorplate `main` (0.5.1-dev, `c68760e`), usaddress 0.5.16.

**Whole address right, coarse** (street parts folded into `StreetName`; intervals are 95% Wilson):

| | Records | doorplate | usaddress |
|---|---|---|---|
| `natural` stratum, shared labels | 15,472 | 98.8% (98.6 to 98.9) | 96.4% (96.1 to 96.7) |
| `natural` stratum, all records | 16,001 | 98.5% (98.3 to 98.7) | 96.1% (95.8 to 96.4) |
| Whole suite, shared labels | 18,401 | 96.0% (95.7 to 96.3) | 87.9% (87.4 to 88.4) |
| Whole suite, all records | 19,586 | 93.4% (93.1 to 93.8) | 85.5% (85.0 to 86.0) |
| `hard` stratum | 2,585 | 61.8% (59.9 to 63.6) | 18.3% (16.9 to 19.8) |
| `hand` stratum | 1,000 | 94.3% (92.7 to 95.6) | 89.1% (87.0 to 90.9) |

- **Which row to read.** `natural` is a random draw of NAD rows by state population, written in the styles
  below; it is the estimate for ordinary input. `hard` holds, for each blind-spot class of either library, the
  records that fall in it (classes above 1 in 10,000 records in a local inventory), so it is low for both by
  design and is not a score to quote alone. The whole-suite rows blend the two at the fixed mix of 80% `natural`,
  15% `hard` and 5% `hand`.
- **Shared labels** leave out the 1,185 records whose gold labels include one doorplate does not model on purpose
  (a number prefix, a street premodifier, a recipient line, landmarks and corners, a country). **All records**
  count such a label as wrong for doorplate, so its blind spots stay in the figure. A trailing `USA` is not
  counted against doorplate: it drops the word and says so with `country_ignored`.
- **Paired, all records:** both right on 16,264, only doorplate on 2,035, only usaddress on 482, neither on 805.
- Tokens right (coarse): doorplate 98.8%, usaddress 96.8%.

By how the record is written (all strata, whole address right):

| | Records | doorplate | usaddress |
|---|---|---|---|
| Mixed case, commas | 3,561 | 95.8% | 89.4% |
| Uppercase, commas | 5,333 | 95.1% | 89.1% |
| Spelled out (`Avenue`, `Northwest`, `Apartment`) | 2,677 | 95.0% | 86.8% |
| Uppercase, no commas (the geocode style) | 5,042 | 89.9% | 80.1% |
| Mixed case, no commas | 1,973 | 91.0% | 78.7% |
| No state | 460 | 83.5% | 69.1% |
| No ZIP | 659 | 91.4% | 75.9% |
| A recipient line or a trailing `USA` | 612 | 92.8% | 78.1% |

By address type: street 93.3% against 85.9%; PO box 99.6% against 99.6%; rural route 100% against 91.0%;
highway contract 100% against 100%; general delivery 100% against 0.0%; military 72.3% against 0.8%
(usaddress labels `PSC` as a subaddress and `UNIT` as a unit, and general delivery as a landmark). Of the 100
military records of the `natural` stratum, the 30 `CMR` boxes (an older type that the current Pub 28 does not
list, so doorplate leaves it out on purpose, `special.toml`) are not read as military; that is why its military
fields-input figure below is 70%. The suite's share of `CMR` is a choice of the templates (a quarter of the
generated military records), not a measured rate, so read that figure as a statement about `CMR` only.

Where each goes wrong (`hard` stratum, whole address right; the class is `gold -> predicted` for the first
token that differs, and the full list with every class is in the run's report):

| Blind spot | Records | doorplate | usaddress |
|---|---|---|---|
| A trailing direction read as part of the city | 395 | 79.2% | 16.5% |
| A number prefix (`W 615`) read as the number or as street | 767 | 0.0% | 1.7% |
| A fraction or suffix after the number read as street | 233 | 79.4% | 66.1% |
| A unit identifier read as street | 333 | 60.4% | 5.4% |
| A unit identifier read as city | 209 | 38.8% | 48.8% |
| A city read as street | 164 | 58.5% | 29.3% |
| A street premodifier (`Old`) read as street | 60 | 0.0% | 3.3% |

doorplate's largest gaps are the labels it does not model (number prefix, premodifier) and, less so, a fractional or
lettered house-number suffix. usaddress's are the unit-identifier and trailing-direction boundaries, military
and general delivery, and the strong drop with no commas.

**The private twin.** The same recipe with a seed that is not published builds a second suite in `local-data/`.
Scored the same way (0.5.0): `natural` 98.4% and the whole suite 93.2% for doorplate, within the public figures' intervals or 0.4 points of them, so nothing here has been tuned to the public set.
Compare the two at each release.

**doorplate only** (no usaddress counterpart; these figures never appear in a table above):

| Measure | Result |
|---|---|
| Fields input (`parse_fields`), whole record right | 99.1% of 17,693 records (`natural` 99.5%, `hard` 95.4%) |
| House number, street, direction, suffix, ZIP | 99.6% to 100% each |
| Unit number | 98.0% |
| Standardized output (`to_usps`), both lines right | 99.5% of 16,052 records |
| Key stability: one `k4` key across two to four styles of the same record | 91.7% of 18,586 records |
| Two different records with the same key | 4 of 18,584 |
| Of the records parsed wrong, share that raised a warning | 59.7% (159 records) |
| Of the records parsed right, share that raised a warning | 0.2% |

Key stability is below 100% for a reason: a spelled-out unit or direction and an abbreviation are the same
record to a person, and a rule that merges them is a rule of the key format (`docs/key-format.md`).

**Speed and memory** (the 19,586 inputs, best of 3, on the profile; read the ratios, the absolute figures
belong to one machine):

| | Strings per second | Relative to usaddress `parse` |
|---|---|---|
| usaddress `parse` (1 thread, no batch call) | 9,297 | 1.0x |
| doorplate `parse_tokens` (1 thread) | 43,411 | 4.7x |
| doorplate `parse_many` (1 thread) | 57,484 | 6.2x |
| doorplate `parse_many` (4 threads) | 137,985 | 14.8x |

The usaddress row is from a cache of one run on this machine; the doorplate rows were measured in the run. Peak resident memory is 154 to 157 MB in the speed runs, including the inputs.

**What the suite does not do.** It is not a regression test (the golden corpus is) and it is not a work list:
a rule change needs its own reason from another source, and "improves the suite score" is never one. It holds
street, PO box, route, military and general-delivery shapes in English, anonymized from NAD and TIGER, in the
styles and at the case mix the specification chose (the local data is 99% uppercase, so the share of mixed case
is chosen, not measured). Building names are not in `v1`.

## Accuracy

Scores use usaddress's labels, folded into the coarse set unless marked fine
(`docs/usaddress-compat.md`, "Scoring rules"). A whole address counts as
right only when every token is. `benchmarks/accuracy.py` prints these tables.

### Geocode benchmark (one line, no commas)

The [geocoding address-parsing benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark)
has three splits of street addresses with input errors and variants mined from a
production geocoder's logs, written uppercase as `4394 MAIN ST PORT HENRY NY 12974`.
The splits share no street. The benchmark states no license, so it stays in the
gitignored `local-data/` and only aggregate numbers are published.

| Whole address (coarse) | Addresses | doorplate | usaddress |
|---|---|---|---|
| **dev** | 60,522 | **94.3%** | 88.1% |
| train | 148,173 | 94.2% | 88.1% |
| test | 30,622 | 96.7% | 88.2% |

On the dev split, in the last full run (0.4.0), tokens were right for 98.8% (coarse) and 96.2% (fine) against usaddress's 97.6% and 95.4%, and the whole address in the fine
label set for 84.4% against 80.2%.

Neither library was trained on any split. **Read the dev figure (94.3%) as the
estimate, not the test figure (96.7%).** doorplate's rules and place list were first written
after reading the *test* split's error classes, so test is optimistic. Since then the rules
were fixed against 80% of train, with the other 20% held out and never read and dev
kept as a check; train and dev agree to 0.1 points. The remaining gap to
test is place names (these city-token counts are from an older analysis, not retaken): city tokens are 97.4% right on test and 94.9% on dev (usaddress 95.7%),
because neighborhoods and unincorporated communities (`GLEN IRIS`) that no list holds are
read as part of the street (3,944 of the dev tokens predicted as street are place names),
and a few county-road forms (`LEE ROAD 123`, `CTY ROAD 321`, 343 tokens) are missed. Area
words, city names that start with a suffix word and spelled-out compass words were added
from this; a gazetteer (GNIS) and the National Address Database were measured
and cover about a tenth and 1% of what is missing, so nothing from them ships. Once the dev
split's most common error classes had been listed, it was no longer fully blind: fixes were
made against train and checked on dev.

The benchmark writes street postdirectionals abbreviated (`N`), so a rule tuned on it alone
can overfit; a spelled-out `NORTH` after a suffix is always part of the city there, and that
was wrong on real addresses. A second check renders 300,000 random Florida records (public
record, kept private, true city known) as one line with no commas
(`tools/compare/oneline_fl.py`): the city is right for 94.7% of them, 76.6% of the
5,735 whose line 1 ends in a spelled-out compass word (`5TH AVE NORTH`) and 47.2% of
the 8,702 whose true city starts with one (`NORTH MIAMI`). The sample is fixed, so runs are comparable: 0.4.1 and 0.5.0 give the same city for every one of the 300,000 records.

### usaddress's own test files

Addresses that are not in usaddress's training files (2,248 of 9,088): doorplate gets the whole address right on 99.1% and usaddress on 100.0%.
These are usaddress's own regression tests, so its near-100% is expected. Read
the gap as where the two libraries choose differently (hard cases in
`labeled.xml`, 89.8% for doorplate, and labels doorplate does not model), not as
an accuracy contest.

### Golden corpus

1,032 of the golden corpus's 1,035 whole addresses are right (99.7%; `doorplate corpus test`). The three that are not are known cases whose expected result is
undecided (`rg-171`, for one, an old negative case that was changed on purpose: a bare `1 1234567` on line 2 is now one unit) and are left out of `tests/corpus/passing.txt`. The corpus is written alongside
the parser and every bug fix adds a case, so it is a regression check and says nothing about accuracy on new data.

## What these numbers do not say

- They do not say an address is real or deliverable.
- Accuracy is for US addresses written in English, and mostly one line. The
  geocode benchmark has street addresses only (no units, PO boxes or routes);
  rural routes, military and general delivery are covered by the corpus, not by
  a measured rate.
- Both libraries' scores depend on the label set. usaddress labels more things
  (recipient names, landmarks, corners) that doorplate leaves unparsed on
  purpose, and those tokens are out of scope in the scoring.
- The speed figures are for one machine with the GIL released where noted.
  Relative numbers hold up better than absolute ones.

## Rerunning

Every figure on this page can be rerun: `docs/running-benchmarks.md` has one table of what to run for each question,
the setup, and what each script needs. In short: `python benchmarks/suite.py all` for the suite, then
`accuracy.py`, `speed_python.py`, `speed_rust.py` and `size_memory.py` for the older sets. The geocode
benchmark is not redistributable, so it is not in the repository: download it into `local-data/geocode-benchmark/`
(`docs/running-benchmarks.md` says how); a script skips a source that is not there.
