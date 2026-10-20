# Benchmarks

Accuracy, speed and size of doorplate, measured 2026-10-19. The scripts are in
`benchmarks/` (`benchmarks/README.md`) so every number can be rerun. usaddress
(the Python CRF library, 0.5.16) is one reference point, not the frame: it is
the tool people know, and the two libraries do different jobs (usaddress labels
tokens; doorplate also standardizes, builds a key and a slug, and reports
diagnostics).

This library formats and parses; it does not validate deliverability. None of
the figures below say an address exists or can receive mail.

This page holds the results. Which benchmark is which (the suite, the geocode benchmark, the speed and size
scripts, the checks on private data) and how to run each: the table in the project README
([Benchmarks](../README.md#benchmarks)) and [`benchmarks/README.md`](../benchmarks/README.md).

The benchmark suite that ships in the repository (`benchmarks/suite/v1/`, the specification in
`docs/benchmark-suite.md`, issue #75) leads this page. It is 19,586 labeled addresses that neither
library's rules, model or tests were made from, run under a fixed 4-CPU, 8 GB profile, and it holds both
libraries' blind spots on purpose. The other sets below are older and each favors one side for a reason
given with it.

**Machine:** Intel Core i9-9900K (14 threads), 49 GB RAM, Linux 6.18 on WSL2. The suite's runner pins 4 CPUs and
8 GB (its reference profile), and the Python speed runs below (`speed_python.py`, `bench_batch.py`) were pinned to
the same 4 CPUs with `taskset -c 0-3` and `RAYON_NUM_THREADS=4`; the Rust (criterion) and size runs were not
pinned and use all 14 threads where they use threads at all.
Rust 1.91, Python 3.13 (speed and size runs in a virtual environment),
doorplate 0.3.0 (measured on `main` from 9f09030 on, while the library's version string still said 0.2.0) and usaddress 0.5.16, built with `--release`.

## In short

| | doorplate | usaddress |
|---|---|---|
| Benchmark suite, `natural` stratum (16,001), whole address (coarse) | 98.3% | 96.1% |
| Benchmark suite, whole suite (19,586), whole address (coarse) | 92.2% | 85.5% |
| Geocode benchmark, dev split, whole address (coarse) | 94.4% | 88.1% |
| usaddress's own test files, whole address (coarse) | 99.2% | 100.0% |
| Addresses per second, one thread, benchmark suite inputs (`parse_tokens` / `usaddress.parse`) | 33,862 | 9,142 |
| Addresses per second, `parse_many` on 4 threads, suite inputs (usaddress has no batch call) | 127,001 | 9,142 |
| One address in Rust (median of the corpus shapes, criterion, unpinned) | 7 to 18 µs | |
| Installed size (wheel / package and dependencies) | 1.8 MB (4.3 MB unpacked) | 4.8 MB |
| Import time | 1 ms | 10 ms |

## The benchmark suite

`benchmarks/suite/v1/` holds 19,586 labeled addresses and `python benchmarks/suite.py all` scores doorplate
and usaddress on them (the runner, how to run it and the resource profile: `benchmarks/README.md`).
It was built once, audited, and is frozen: `v1` is never edited, and label errors found later go into `v2`
with both versions' scores kept here. Rows are anonymized National Address Database points (the real street,
city, state and ZIP; invented house and unit numbers), Census TIGER street names for the six states NAD
lacks, templates for PO boxes, routes, military and general delivery, and 1,000 hand-labeled shapes. The
gold labels come from the field each token was written from, never from either parser. Run on 4 CPUs and
8 GB (Linux, the Intel i9-9900K of the machine above, pinned by the runner), doorplate 0.3.0 (the version string
said 0.2.0 when it was run), usaddress 0.5.16.

**Whole address right, coarse** (street parts folded into `StreetName`; intervals are 95% Wilson):

| | Records | doorplate | usaddress |
|---|---|---|---|
| `natural` stratum, shared labels | 15,472 | 98.6% (98.4 to 98.8) | 96.4% (96.1 to 96.7) |
| `natural` stratum, all records | 16,001 | 98.3% (98.1 to 98.5) | 96.1% (95.8 to 96.4) |
| Whole suite, shared labels | 18,401 | 94.7% (94.4 to 95.1) | 87.9% (87.4 to 88.4) |
| Whole suite, all records | 19,586 | 92.2% (91.8 to 92.6) | 85.5% (85.0 to 86.0) |
| `hard` stratum | 2,585 | 54.3% (52.4 to 56.2) | 18.3% (16.9 to 19.8) |
| `hand` stratum | 1,000 | 92.3% (90.5 to 93.8) | 89.1% (87.0 to 90.9) |

- **Which row to read.** `natural` is a random draw of NAD rows by state population, written in the styles
  below; it is the estimate for ordinary input. `hard` holds, for each blind-spot class of either library, the
  records that fall in it (classes above 1 in 10,000 records in a local inventory), so it is low for both by
  design and is not a score to quote alone. The whole-suite rows blend the two at the fixed mix of 80% `natural`,
  15% `hard` and 5% `hand`.
- **Shared labels** leave out the 1,185 records whose gold labels include one doorplate does not model on purpose
  (a number prefix, a street premodifier, a recipient line, landmarks and corners, a country). **All records**
  count such a label as wrong for doorplate, so its blind spots stay in the figure. A trailing `USA` is not
  counted against doorplate: it drops the word and says so with `country_ignored`.
- **Paired, all records:** both right on 16,075, only doorplate on 1,981, only usaddress on 671, neither on 859.
- Tokens right (coarse): doorplate 98.6%, usaddress 96.8%.

By how the record is written (all strata, whole address right):

| | Records | doorplate | usaddress |
|---|---|---|---|
| Mixed case, commas | 3,561 | 94.7% | 89.4% |
| Uppercase, commas | 5,333 | 93.9% | 89.1% |
| Spelled out (`Avenue`, `Northwest`, `Apartment`) | 2,677 | 94.1% | 86.8% |
| Uppercase, no commas (the geocode style) | 5,042 | 88.6% | 80.1% |
| Mixed case, no commas | 1,973 | 89.6% | 78.7% |
| No state | 460 | 82.2% | 69.1% |
| No ZIP | 659 | 90.1% | 75.9% |
| A recipient line or a trailing `USA` | 612 | 91.7% | 78.1% |

By address type: street 92.0% against 85.9%; PO box 99.6% against 99.6%; rural route 100% against 91.0%;
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
| A fraction or suffix after the number read as street | 233 | 1.7% | 66.1% |
| A unit identifier read as street | 333 | 57.1% | 5.4% |
| A unit identifier read as city | 209 | 37.8% | 48.8% |
| A city read as street | 164 | 57.9% | 29.3% |
| A street premodifier (`Old`) read as street | 60 | 0.0% | 3.3% |

doorplate's largest gaps are the labels it does not model (number prefix, premodifier) and a fractional or
lettered house-number suffix. usaddress's are the unit-identifier and trailing-direction boundaries, military
and general delivery, and the strong drop with no commas.

**The private twin.** The same recipe with a seed that is not published builds a second suite in `local-data/`.
Scored the same way: `natural` 98.1% against 95.7%, `hard` 53.9% against 18.3%, `hand` 92.3% against 89.1%, all
within the public figures' intervals or 0.4 points of them, so nothing here has been tuned to the public set.
Compare the two at each release.

**doorplate only** (no usaddress counterpart; these figures never appear in a table above):

| Measure | Result |
|---|---|
| Fields input (`parse_fields`), whole record right | 98.9% of 17,693 records (`natural` 99.5%, `hard` 94.3%) |
| House number, street, direction, suffix, ZIP | 99.6% to 100% each |
| Unit number | 96.8% |
| Standardized output (`to_usps`), both lines right | 99.6% of 16,052 records |
| Key stability: one `k2` key across two to four styles of the same record | 91.6% of 18,586 records |
| Two different records with the same key | 4 of 18,585 |
| Of the records parsed wrong, share that raised a warning | 43.9% (187 records) |
| Of the records parsed right, share that raised a warning | 0.2% |

Key stability is below 100% for a reason: a spelled-out unit or direction and an abbreviation are the same
record to a person, and a rule that merges them is a rule of the key format (`docs/key-format.md`).

**Speed and memory** (the 19,586 inputs, best of 3, on the profile; read the ratios, the absolute figures
belong to one machine):

| | Strings per second | Relative to usaddress `parse` |
|---|---|---|
| usaddress `parse` (1 thread, no batch call) | 9,142 | 1.0x |
| doorplate `parse_tokens` (1 thread) | 33,862 | 3.7x |
| doorplate `parse_many` (1 thread) | 36,364 | 4.0x |
| doorplate `parse_many` (4 threads) | 127,001 | 13.9x |

Peak resident memory is 152 to 154 MB in the speed runs, including the inputs.

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
| **dev** | 60,522 | **94.4%** | 88.1% |
| train | 148,173 | 94.3% | 88.1% |
| of which the 20% held out, never read | 29,635 | 94.1% | 88.4% |
| test | 30,622 | 96.7% | 88.2% |

| dev split | doorplate | usaddress |
|---|---|---|
| Tokens (coarse) | 98.8% | 97.6% |
| Whole address (coarse) | 94.4% | 88.1% |
| Tokens (fine) | 96.2% | 95.4% |
| Whole address (fine) | 84.4% | 80.2% |

Neither library was trained on any split. **Read the dev figure (94.4%) as the
estimate, not the test figure (96.7%).** doorplate's rules and place list were first written
after reading the *test* split's error classes, so test is optimistic. Since then the rules
were fixed against 80% of train, with the other 20% held out and never read (94.1%) and dev
kept as a check; train, the held-out part and dev agree to 0.3 points. The remaining gap to
test is place names: city tokens are 97.4% right on test and 94.9% on dev (usaddress 95.7%),
because neighborhoods and unincorporated communities (`GLEN IRIS`) that no list holds are
read as part of the street (3,944 of the dev tokens predicted as street are place names),
and a few county-road forms (`LEE ROAD 123`, `CTY ROAD 321`, 343 tokens) are missed. Area
words, city names that start with a suffix word and spelled-out compass words were added
from this (issue #29); a gazetteer (GNIS) and the National Address Database were measured
and cover about a tenth and 1% of what is missing, so nothing from them ships. Once the dev
split's most common error classes had been listed, and again while rules were checked
for #29, it was no longer fully blind: fixes were made against train and checked on dev.

The benchmark writes street postdirectionals abbreviated (`N`), so a rule tuned on it alone
can overfit; a spelled-out `NORTH` after a suffix is always part of the city there, and that
was wrong on real addresses. A second check renders 300,000 random Florida records (public
record, kept private, true city known) as one line with no commas
(`tools/compare/oneline_fl.py`): the city is right for 94.7% of them, 77.6% of the
5,716 whose line 1 ends in a spelled-out compass word (`5TH AVE NORTH`) and 48.0% of
the 8,746 whose true city starts with one (`NORTH MIAMI`).

### usaddress's own test files

Addresses that are not in usaddress's training files (2,248 of 9,088).

| | Addresses | Tokens | doorplate: tokens | usaddress: tokens | doorplate: whole | usaddress: whole |
|---|---|---|---|---|---|---|
| all | 2,248 | 12,629 | 99.6% | 100.0% | 99.2% | 100.0% |

These are usaddress's own regression tests, so its near-100% is expected. Read
the gap as where the two libraries choose differently (hard cases in
`labeled.xml`, 89.8% for doorplate, and labels doorplate does not model), not as
an accuracy contest.

### Golden corpus

529 of 529 (100%). The corpus is written alongside the parser and every bug
fix adds a case, so it is a regression check and says nothing about accuracy on
new data.

## Speed

### Rust (criterion, `crates/doorplate/benches/parse.rs`)

Median of a measurement run, one thread unless noted.

| Benchmark | Time |
|---|---|
| `parse`, street only (`1305 SUNWOOD DR`) | 7.0 µs |
| `parse`, PO box | 8.0 µs |
| `parse`, military | 7.8 µs |
| `parse`, highway | 12.5 µs |
| `parse_fields` (street, city, state, ZIP) | 13.6 µs |
| `parse`, unit and ZIP+4 | 15.4 µs |
| `parse`, full one line | 17.9 µs |
| The 529 corpus inputs, one by one | 10.1 ms (19 µs each) |
| The same, `parse_many` (rayon, 14 threads) | 2.5 ms (4.7 µs each) |
| `to_usps` | 0.78 µs |
| `to_reso` | 1.45 µs |
| `key` | 0.37 µs |
| `slug` | 0.98 µs |

Parsing is by far the biggest cost; the emitters are about a tenth of a parse
or less, and a `ParsedAddress` builds them only when asked.

The command-line tool: `doorplate parse-file` over 440,288 distinct Florida
addresses (line 1, line 2, city, state and ZIP columns; this run a random sample of the
Florida DBPR files, 2026) took 14.5 s,
30,400 rows per second on one thread, including reading the CSV and writing
about 30 columns per row.

### Python

`benchmarks/speed_python.py`, 100,000 addresses (the inputs repeated), best of
five runs, pinned to 4 CPUs like the suite (`taskset -c 0-3 env RAYON_NUM_THREADS=4 python benchmarks/speed_python.py`).
The suite's own `speed` command (`python benchmarks/suite.py speed`) is the one to quote; this table shows the
shape of the cost on other inputs.

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` | 17.7 µs | 29.1 µs |
| doorplate `parse`, then `key()` and `to_usps()` | 20.9 µs | 33.0 µs |
| doorplate `tag` | 20.1 µs | 31.8 µs |
| doorplate `parse_tokens` | 19.8 µs | 31.5 µs |
| doorplate `parse_many` (4 threads) | 6.0 µs | 9.6 µs |
| usaddress `parse` | 85.3 µs | 95.8 µs |
| usaddress `tag` | 93.1 µs | 100.1 µs |

Call by call on one thread, `parse_tokens` is 4.3x `usaddress.parse` on the
corpus inputs and 3.0x on the geocode addresses. `parse_many` parses on all
the cores it is given (4 here) with the GIL released: 14x and 10x `usaddress.parse`, which is
single-threaded (usaddress could be run in several processes; that is a
different comparison). A Python call costs about what the Rust parse does
(18 µs against 19 µs on the corpus); the boundary is not the bottleneck.

Building DataFrames (`crates/doorplate-py/benchmarks/bench_batch.py`, 100,000
corpus addresses, 4 CPUs): a loop of `parse` 1.79 s, `parse_many` 0.62 s (2.9x),
`parse_many` into a pandas frame of seven columns 0.77 s (2.3x), into a Polars
frame 0.69 s (2.6x). Reading attributes from 100,000 Python objects is now
most of the time; `to_dict()` on every row costs about as much as parsing again.
The DuckDB functions (`doorplate.duckdb`) parse a 100,000-row table in 0.64 s with seven
struct fields (2.8x a loop of `parse`) and 0.91 s with all fifteen (2.0x): the cost of
building the Arrow struct grows with the columns, so ask for only those you need. A
1,000,000-row table with four fields ran at about 213,000 rows/s, against about 280,000/s
for `parse_many` on the same strings (a separate run on 2026-10-17 on all 14 threads, not repeated).

## Size and memory

`benchmarks/size_memory.py`.

| | Size |
|---|---|
| `doorplate` CLI binary (release, as built) | 5.0 MB (4.4 MB stripped) |
| `doorplate` wheel (abi3, one wheel per platform) | 1.8 MB |
| The extension module inside it | 4.1 MB |
| `usaddress` and its dependencies, installed | 4.8 MB (the model is 134 KB; the rest is python-crfsuite) |

The lexicon tables, the national place list and the Florida pack are compiled
in, so there is no model or data file to download or load. The tables are
inside the crate, so the crate package (53 files, 3.6 MiB unpacked,
0.8 MB compressed) and the Python source distribution (0.8 MB) carry them and
build from a clean directory.

Peak resident memory of a fresh Python process parsing 100,000 addresses
(corpus inputs repeated):

| | Import | After import | After the batch |
|---|---|---|---|
| Python alone | | 16 MB | |
| doorplate, loop of `parse`, each result dropped | 1 ms | 16 MB | 18 MB |
| usaddress, loop of `parse`, each result dropped | 10 ms | 18 MB | 20 MB |
| doorplate, loop of `parse`, 100,000 results kept | 1 ms | 16 MB | 151 MB |
| usaddress, loop of `parse`, 100,000 results kept | 10 ms | 18 MB | 128 MB |
| doorplate, `parse_many`, 100,000 results kept | 1 ms | 16 MB | 241 MB |

The parser itself adds about 2 MB to a process either way. A `ParsedAddress`
holds every component and its source spans (about 1.4 KB each against about
1.1 KB for usaddress's token list). `parse_many` builds all its results at once
on several threads, so its peak is higher than a loop's. usaddress loads its
model on its first call, so its memory after import understates it.

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
- There is no confidence score to measure: `confidence` is always `None`, and a score is not
  planned (see the roadmap).

## Rerunning

Every figure on this page can be rerun: `benchmarks/README.md` has one table of what to run for each question,
the setup, and what each script needs. In short: `python benchmarks/suite.py all` for the suite, then
`accuracy.py`, `speed_python.py`, `speed_rust.py` and `size_memory.py` for the older sets. The geocode
benchmark is not redistributable, so it is not in the repository: download it into `local-data/geocode-benchmark/`
(`benchmarks/README.md` says how); a script skips a source that is not there.
