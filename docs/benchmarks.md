# Benchmarks: accuracy

Accuracy of doorplate, with its 0.3.1-to-0.4.0 comparison and the caveats; speed, size and memory are on [their own page](speed-and-size.md). Measured 2026-10-19 on 0.3.0 and rerun on 0.4.0 (2026-10-25). The scripts are in
`benchmarks/` (`docs/running-benchmarks.md`) so every number can be rerun. usaddress
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
`docs/benchmark-suite.md`, issue #75) leads this page. It is 19,586 labeled addresses that neither
library's rules, model or tests were made from, run under a fixed 4-CPU, 8 GB profile, and it holds both
libraries' blind spots on purpose. The other sets below are older and each favors one side for a reason
given with it.

**Machine:** Intel Core i9-9900K (14 threads), 49 GB RAM, Linux 6.18 on WSL2. The suite's runner pins 4 CPUs and
8 GB (its reference profile), and the Python speed runs below (`speed_python.py`, `bench_batch.py`) were pinned to
the same 4 CPUs with `taskset -c 0-3` and `RAYON_NUM_THREADS=4`; the Rust (criterion) and size runs were not
pinned and use all 14 threads where they use threads at all.
Rust 1.91, Python 3.13 (speed and size runs in a virtual environment),
doorplate 0.4.0 (measured on `main` at 9f6a4a7, 2026-10-25, while the version string said `0.4.0-dev`; the 0.3.0 figures were measured from 9f09030, while it said 0.2.0) and usaddress 0.5.16, built with `--release`.

**Rerun on 0.4.0 (2026-10-25).** Every figure on this page was retaken, except the few marked "not retaken" (the
city-token analysis of the geocode benchmark, the CLI file run, the crate package size, the 1,000,000-row DuckDB run,
and the profile section, which is dated). The parser, the key and the speed all changed in 0.4.0; [0.3.1 to
0.4.0](#031-to-040) has the two builds side by side.

Earlier, on 0.3.1 (2026-10-22), every figure matched, so none was retaken: accuracy was identical (the suite, its
private twin, the geocode splits, usaddress's test files and the golden corpus; the suite's data checksum is
unchanged), speed was within 2% of 0.3.0 in an alternating A/B of the two builds (the suite's speed track varies by
about 10% from run to run on its own), and package and import sizes were unchanged.

## In short

| | doorplate | usaddress |
|---|---|---|
| Benchmark suite, `natural` stratum (16,001), whole address (coarse) | 98.5% | 96.1% |
| Benchmark suite, whole suite (19,586), whole address (coarse) | 93.4% | 85.5% |
| [Geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark), dev split, whole address (coarse) | 94.3% | 88.1% |
| usaddress's own test files, whole address (coarse) | 99.1% | 100.0% |
| Addresses per second, one thread, benchmark suite inputs (`parse_tokens` / `usaddress.parse`) | 35,951 | 9,037 |
| Addresses per second, `parse_many` on 4 threads, suite inputs (usaddress has no batch call) | 133,873 | 9,037 |
| One address in Rust (median of the corpus shapes, criterion, unpinned) | 5 to 12 µs | |
| Installed size (wheel / package and dependencies) | 2.1 MB (5.1 MB unpacked) | 4.8 MB |
| Import time | 1 ms | 10 ms |

## 0.4.1 to 0.5.0

The same benchmarks on the 0.4.1 build (the tag `v0.4.1`, in its own worktree) and on `main` at 958bb72 (0.5.0-dev, the `k4` cut), on one machine on
2026-10-31, both measured the same way in the same session: the suite and the private twin with each build's Python package, the geocode splits and
the Florida check with a command-line binary built from each tree, speed on a quiet machine (the suite's 4-CPU profile; the Python script unpinned).
0.5.0 reads many more shapes (the closed rule list of the `k4`, tracker #201); the key changes are in the changelog and in
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
of them are one rule (#270: a letter A to D after the house number joins the number, `123 A ELM ST` is `123A`, as the reviewed sources write it;
the benchmark's labels keep the letter in the street name). No city changed. The suite does not attribute a gain to a rule, and "improves the suite
score" is not a reason for one (see below).

**Speed is lower.** Python, `benchmarks/speed_python.py` (100,000 addresses, best of several runs): `parse` on the golden-corpus inputs 63,901 to 56,114 per
second (-12%), on the geocode addresses 41,908 to 37,784 (-10%). The suite's own speed track (4 CPUs): `parse_tokens` on one thread 39,244 to 35,951
(-8%), `parse_many` on 4 threads 149,972 to 133,873 (-11%). Each figure is one session, and the suite's speed track varies by about 10% from run to run
on its own, but the four rows move the same way. The cause has not been looked for: the 0.5.0 rules add tokenizer and tagger passes. It is not a
regression test failure (nothing in `cargo test` measures speed); a profile is a follow-up.

**Size.** The wheel is 2.1 MB (5.1 MB unpacked) against 2.0 MB for 0.4.1; the CLI binary is 6.2 MB (5.2 MB stripped); import time is 1 ms; resident
memory after parsing 100,000 addresses is 158 MB (a loop of `parse`) to 253 MB (`parse_many`, all results kept).

The detailed tables below ("The benchmark suite", "Accuracy") are the 0.4.0 run; the figures above are the current ones, and the changelog has the
rules behind them.

## 0.3.1 to 0.4.0

The same benchmarks on the 0.3.1 build and on `main` at 9f6a4a7 (0.4.0-dev), on one machine on 2026-10-25. Both columns were measured
the same way, in the same session: the 0.3.1 suite, twin and speed tracks with the 0.3.1 Python package, the geocode splits with
a 0.3.1 command-line binary built from the tag. Speed is a back-to-back A/B: 0.3.1 was built from the `v0.3.1` tag in its own directory, and both builds ran the same
script on the same inputs, pinned to 4 CPUs (`taskset -c 0-3 env RAYON_NUM_THREADS=4`) on a quiet machine; the Rust
(criterion) runs were unpinned, one after the other.

**Accuracy.** Ordinary input did not move; the gains are in the rare shapes the closed rule list of 0.4.0 went after, in
fields input, in units and in warnings.

| | 0.3.1 | 0.4.0 | Change |
|---|---|---|---|
| Suite, `natural` stratum (16,001), whole address (coarse) | 98.3% | 98.3% | same |
| Suite, whole (19,586) | 92.2% | 92.3% | +0.1 |
| Suite, `hard` stratum (2,585) | 54.3% | 54.6% | +0.3 |
| Suite, `hand` stratum (1,000) | 92.3% | 94.3% | +2.0 |
| Suite, the private twin: `natural` / `hard` / `hand` | 98.1% / 53.9% / 92.3% | 98.2% / 54.2% / 94.3% | +0.1 / +0.3 / +2.0 |
| Geocode benchmark, dev (60,522) | 94.4% | 94.5% | +0.1 |
| Geocode benchmark, train (148,173) | 94.3% | 94.4% | +0.1 |
| Geocode benchmark, the 20% of train held out (29,635) | 94.1% | 94.2% | +0.1 |
| Geocode benchmark, test (30,622; optimistic) | 96.7% | 96.8% | +0.1 |
| usaddress's own test files, whole address | 99.2% | 99.2% | same |
| Fields input (`parse_fields`), whole record right | 98.9% | 99.1% | +0.2 |
| Unit number right (fields input) | 96.8% | 97.8% | +1.0 |
| Key stability, one key across two to four styles | 91.6% | 91.7% | +0.1 |
| Records parsed wrong (fields input) that raised a warning | 43.9% (187) | 54.7% (159) | +10.8; 28 fewer wrong |
| Records parsed right that raised a warning | 0.1% | 0.3% | +0.2 |
| One-line Florida check (300,000 records, city right) | the same city on every record | | 0 gained, 0 lost |

The `hand` gain is the tokenization change of #78 (`parse_tokens` cuts like `usaddress.tokenize`, so the suite's character-span
scoring stops losing tokens to a different cut); the other differences in these rows are inside the intervals. The one-line Florida row is a paired comparison of the two
binaries on one fixed sample (`tools/compare/oneline_fl.py` scores one build; the pairing is the check), and the
geocode `city_diff` between the two builds gains 3 cities and loses none on the held-out split, and gains 2 and loses
none on dev. `unit_number` and the warning figures are the likely home of the rules of 0.4.0 (a unit left in the street name,
#128; a department name, #166; a lone directional on line 2, #170; the warnings of #102): the suite does not
attribute a gain to a rule, and "improves the suite score" is not a reason for one (see below), so read these as
measured changes, not as the effect of any one rule. The full Netsyms run is on a different footing: its counts are in
the changelog and the release checklist, not here, because it has no labels.

**Speed, Python** (`benchmarks/speed_python.py`, 100,000 addresses, best of five, 4 CPUs; the geocode addresses are one
fixed set, so both builds parsed the same strings):

| Per second, geocode addresses | 0.3.1 | 0.4.0 | Change |
|---|---|---|---|
| doorplate `parse` | 34,149 | 38,463 | +13% |
| doorplate `parse`, then `key()` and `to_usps()` | 30,825 | 32,718 | +6% |
| doorplate `tag` | 31,408 | 34,575 | +10% |
| doorplate `parse_tokens` | 30,868 | 36,642 | +19% |
| doorplate `parse_many` (4 threads) | 113,873 | 137,876 | +21% |

| Per second, golden-corpus inputs | 0.3.1 | 0.4.0 | Change |
|---|---|---|---|
| doorplate `parse` | 56,443 | 61,698 | +9% |
| doorplate `parse_tokens` | 50,678 | 51,186 | +1% |
| doorplate `parse_many` (4 threads) | 169,532 | 193,058 | +14% |

(Both builds read the same committed corpus, which has grown since 0.3.1, so these rows compare the builds, not the
corpus with its older self.) The suite's own `speed` track, 4 CPUs, both builds measured in this session: `parse_tokens` on one thread 33,630 to 38,305 per
second (+14%; usaddress `parse` 9,015 and 8,937 in the two runs, so the run to run noise of that track is about 1%),
`parse_many` on one thread 37,357 to 43,657 (+17%), and `parse_many` on four threads 118,441 to 152,376 (+29%). Against
usaddress that is 3.7x to 4.3x on one thread and 13.1x to 17.1x on four.

**Speed, Rust** (criterion, median, unpinned, 0.3.1 built from the tag in its own target directory):

| Benchmark | 0.3.1 | 0.4.0 | Change |
|---|---|---|---|
| `parse`, street only | 6.80 µs | 4.78 µs | -30% |
| `parse`, PO box | 7.78 µs | 6.84 µs | -12% |
| `parse`, military | 7.45 µs | 6.88 µs | -8% |
| `parse`, highway | 12.06 µs | 9.25 µs | -23% |
| `parse_fields` (street, city, state, ZIP) | 13.54 µs | 10.03 µs | -26% |
| `parse`, unit and ZIP+4 | 15.24 µs | 11.06 µs | -27% |
| `parse`, full one line | 17.30 µs | 12.40 µs | -28% |
| `to_usps` | 0.80 µs | 0.75 µs | -6% |
| `to_reso` | 1.53 µs | 1.44 µs | -6% |
| `key` | 0.39 µs | 0.36 µs | -8% |
| `slug` | 1.02 µs | 0.97 µs | -5% |

(The corpus rows of the same benchmark, 10.58 ms and 11.28 ms one by one, are not comparable: each tree benchmarks its own
corpus, 529 inputs in 0.3.1 and 762 now.) The speed gains are the profile work of 0.4.0, [on the speed page](speed-and-size.md#profile-where-the-time-goes):
`longest_at` and `longest_ending` join the tokens once (fewer allocations), the table lookups compare the first byte inline,
`place_key` writes into one buffer, and `normalize_key_cow` scans once. The emitters changed little; the small gain
there is the same cheaper lookups.

**Size.**

| | 0.3.1 | 0.4.0 |
|---|---|---|
| `doorplate` CLI binary (release) | 5.0 MB (4.4 MB stripped) | 5.5 MB (4.6 MB stripped) |
| The extension module inside the wheel | 4.1 MB | 4.4 MB |
| `doorplate` wheel (abi3, one per platform) | 1.8 MB | 1.8 MB |
| The wheel unpacked | 4.3 MB | 4.5 MB |
| Python source distribution | 0.8 MB | 0.9 MB |
| Import time | 1 ms | 1 ms |
| Memory, a loop of `parse`, results dropped | 18 MB | 19 MB |

The binary grew by about half a megabyte: the state data is folded into the core and the lexicon tables carry the
rules' new spellings. The wheel is compressed, so it did not move.

## The benchmark suite

`benchmarks/suite/v1/` holds 19,586 labeled addresses and `python benchmarks/suite.py all` scores doorplate
and usaddress on them (the runner, how to run it and the resource profile: `docs/running-benchmarks.md`).
It was built once, audited, and is frozen: `v1` is never edited, and label errors found later go into `v2`
with both versions' scores kept here. Rows are anonymized National Address Database points (the real street,
city, state and ZIP; invented house and unit numbers), Census TIGER street names for the six states NAD
lacks, templates for PO boxes, routes, military and general delivery, and 1,000 hand-labeled shapes. The
gold labels come from the field each token was written from, never from either parser. Run on 4 CPUs and
8 GB (Linux, the Intel i9-9900K of the machine above, pinned by the runner), doorplate 0.4.0 (`0.4.0-dev` when it was run), usaddress 0.5.16.

**Whole address right, coarse** (street parts folded into `StreetName`; intervals are 95% Wilson):

| | Records | doorplate | usaddress |
|---|---|---|---|
| `natural` stratum, shared labels | 15,472 | 98.6% (98.4 to 98.8) | 96.4% (96.1 to 96.7) |
| `natural` stratum, all records | 16,001 | 98.3% (98.1 to 98.5) | 96.1% (95.8 to 96.4) |
| Whole suite, shared labels | 18,401 | 94.9% (94.6 to 95.2) | 87.9% (87.4 to 88.4) |
| Whole suite, all records | 19,586 | 92.3% (92.0 to 92.7) | 85.5% (85.0 to 86.0) |
| `hard` stratum | 2,585 | 54.6% (52.7 to 56.5) | 18.3% (16.9 to 19.8) |
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
- **Paired, all records:** both right on 16,099, only doorplate on 1,988, only usaddress on 647, neither on 852.
- Tokens right (coarse): doorplate 98.6%, usaddress 96.8%.

By how the record is written (all strata, whole address right):

| | Records | doorplate | usaddress |
|---|---|---|---|
| Mixed case, commas | 3,561 | 94.7% | 89.4% |
| Uppercase, commas | 5,333 | 94.0% | 89.1% |
| Spelled out (`Avenue`, `Northwest`, `Apartment`) | 2,677 | 94.2% | 86.8% |
| Uppercase, no commas (the geocode style) | 5,042 | 88.6% | 80.1% |
| Mixed case, no commas | 1,973 | 89.6% | 78.7% |
| No state | 460 | 82.2% | 69.1% |
| No ZIP | 659 | 90.3% | 75.9% |
| A recipient line or a trailing `USA` | 612 | 91.7% | 78.1% |

By address type: street 92.2% against 85.9%; PO box 99.6% against 99.6%; rural route 100% against 91.0%;
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
| A unit identifier read as street | 333 | 59.2% | 5.4% |
| A unit identifier read as city | 209 | 37.8% | 48.8% |
| A city read as street | 164 | 57.9% | 29.3% |
| A street premodifier (`Old`) read as street | 60 | 0.0% | 3.3% |

doorplate's largest gaps are the labels it does not model (number prefix, premodifier) and a fractional or
lettered house-number suffix. usaddress's are the unit-identifier and trailing-direction boundaries, military
and general delivery, and the strong drop with no commas.

**The private twin.** The same recipe with a seed that is not published builds a second suite in `local-data/`.
Scored the same way: `natural` 98.2% against 95.7%, `hard` 54.2% against 18.3%, `hand` 94.3% against 89.1%, all
within the public figures' intervals or 0.4 points of them, so nothing here has been tuned to the public set.
Compare the two at each release.

**doorplate only** (no usaddress counterpart; these figures never appear in a table above):

| Measure | Result |
|---|---|
| Fields input (`parse_fields`), whole record right | 99.1% of 17,693 records (`natural` 99.5%, `hard` 95.4%) |
| House number, street, direction, suffix, ZIP | 99.6% to 100% each |
| Unit number | 97.8% |
| Standardized output (`to_usps`), both lines right | 99.6% of 16,052 records |
| Key stability: one `k3` key across two to four styles of the same record | 91.7% of 18,586 records |
| Two different records with the same key | 4 of 18,584 |
| Of the records parsed wrong, share that raised a warning | 54.7% (159 records) |
| Of the records parsed right, share that raised a warning | 0.3% |

Key stability is below 100% for a reason: a spelled-out unit or direction and an abbreviation are the same
record to a person, and a rule that merges them is a rule of the key format (`docs/key-format.md`).

**Speed and memory** (the 19,586 inputs, best of 3, on the profile; read the ratios, the absolute figures
belong to one machine):

| | Strings per second | Relative to usaddress `parse` |
|---|---|---|
| usaddress `parse` (1 thread, no batch call) | 8,937 | 1.0x |
| doorplate `parse_tokens` (1 thread) | 38,305 | 4.3x |
| doorplate `parse_many` (1 thread) | 43,657 | 4.9x |
| doorplate `parse_many` (4 threads) | 152,376 | 17.1x |

Peak resident memory is 153 to 155 MB in the speed runs, including the inputs.

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
| **dev** | 60,522 | **94.5%** | 88.1% |
| train | 148,173 | 94.4% | 88.1% |
| of which the 20% held out, never read | 29,635 | 94.2% | 88.4% |
| test | 30,622 | 96.8% | 88.2% |

| dev split | doorplate | usaddress |
|---|---|---|
| Tokens (coarse) | 98.8% | 97.6% |
| Whole address (coarse) | 94.5% | 88.1% |
| Tokens (fine) | 96.2% | 95.4% |
| Whole address (fine) | 84.4% | 80.2% |

Neither library was trained on any split. **Read the dev figure (94.5%) as the
estimate, not the test figure (96.8%).** doorplate's rules and place list were first written
after reading the *test* split's error classes, so test is optimistic. Since then the rules
were fixed against 80% of train, with the other 20% held out and never read (94.2%) and dev
kept as a check; train, the held-out part and dev agree to 0.3 points. The remaining gap to
test is place names (these city-token counts are from the 0.3.0 analysis and were not retaken): city tokens are 97.4% right on test and 94.9% on dev (usaddress 95.7%),
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
(`tools/compare/oneline_fl.py`): the city is right for 94.7% of them, 76.6% of the
5,735 whose line 1 ends in a spelled-out compass word (`5TH AVE NORTH`) and 47.2% of
the 8,702 whose true city starts with one (`NORTH MIAMI`). The sample is fixed since 0.4.0 (the script sorted nothing
before it shuffled, so each run drew different records and the scores moved by 0.1 point); on this sample 0.3.1 and
0.4.0 give the same city for every one of the 300,000 records.

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

761 of 762 whole addresses right (99.9%). The one that is not is `rg-171`, an old negative case that #128 changed on purpose (a
bare `1 1234567` on line 2 is now one unit) and left out of `tests/corpus/passing.txt` (issue #196 decides what it should do). The corpus is written alongside
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
