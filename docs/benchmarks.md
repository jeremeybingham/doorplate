# Benchmarks

Accuracy, speed and size of doorplate, measured 2026-10-19. The scripts are in
`benchmarks/` (`benchmarks/README.md`) so every number can be rerun. usaddress
(the Python CRF library, 0.5.16) is one reference point, not the frame: it is
the tool people know, and the two libraries do different jobs (usaddress labels
tokens; doorplate also standardizes, builds a key and a slug, and reports
diagnostics).

This library formats and parses; it does not validate deliverability. None of
the figures below say an address exists or can receive mail.

A standard benchmark suite that ships in the repository is being built
(`docs/benchmark-suite.md`, issue #75). When it is done, its figures will lead this page. It
is a fair comparison with usaddress, run under a 4-CPU, 8 GB profile, and it holds both
libraries' blind spots.

**Machine:** Intel Core i9-9900K (14 threads), 49 GB RAM, Linux 6.18 on WSL2,
Rust 1.91, Python 3.13 (speed and size runs in a virtual environment),
doorplate `main` at 9f09030 (the unreleased 0.3.0 work; the version string is still 0.2.0) and usaddress 0.5.16, built with `--release`.

## In short

| | doorplate | usaddress |
|---|---|---|
| Geocode benchmark, dev split, whole address (coarse) | 94.4% | 88.1% |
| usaddress's own test files, whole address (coarse) | 99.2% | 100.0% |
| One address from Python, `parse` / `usaddress.parse` | 18 µs | 85 µs |
| 100,000 addresses, `parse_many` / a loop of `usaddress.parse` | 0.27 s | 8.5 s |
| One address in Rust (median of the corpus shapes) | 7 to 18 µs | |
| Installed size (wheel / package and dependencies) | 1.8 MB (4.3 MB unpacked) | 4.8 MB |
| Import time | 1 ms | 10 ms |

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
five runs.

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` | 18 µs | 30 µs |
| doorplate `parse`, then `key()` and `to_usps()` | 21 µs | 34 µs |
| doorplate `tag` | 20 µs | 33 µs |
| doorplate `parse_tokens` | 20 µs | 33 µs |
| doorplate `parse_many` (14 threads) | 2.7 µs | 4.0 µs |
| usaddress `parse` | 85 µs | 98 µs |
| usaddress `tag` | 94 µs | 102 µs |

Call by call on one thread, `parse_tokens` is 4.1x `usaddress.parse` on the
corpus inputs and 3.0x on the geocode addresses. `parse_many` parses on all
cores with the GIL released: 31x and 24x `usaddress.parse`, which is
single-threaded (usaddress could be run in several processes; that is a
different comparison). A Python call costs about what the Rust parse does
(18 µs against 19 µs on the corpus); the boundary is not the bottleneck.

Building DataFrames (`crates/doorplate-py/benchmarks/bench_batch.py`, 100,000
corpus addresses): a loop of `parse` 1.89 s, `parse_many` 0.27 s (7.0x),
`parse_many` into a pandas frame of seven columns 0.46 s (4.2x), into a Polars
frame 0.36 s (5.2x). Reading attributes from 100,000 Python objects is now
most of the time; `to_dict()` on every row costs about as much as parsing again.
The DuckDB functions (`doorplate.duckdb`) parse a 100,000-row table in 0.46 s with seven
struct fields (4.2x a loop of `parse`) and 0.69 s with all fifteen (2.7x): the cost of
building the Arrow struct grows with the columns, so ask for only those you need. A
1,000,000-row table with four fields ran at about 213,000 rows/s, against about 280,000/s
for `parse_many` on the same strings (a separate run on 2026-10-17, not repeated).

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
- Confidence scores are not measured: `confidence` is always `None`.

## Rerunning

```sh
cargo build --release -p doorplate-cli
(cd crates/doorplate-py && maturin develop --release)
python benchmarks/accuracy.py
python benchmarks/speed_python.py
python benchmarks/speed_rust.py [--csv FILE --column NAME ...]
python benchmarks/size_memory.py
```

`benchmarks/README.md` has the setup and what each script needs. The geocode
benchmark is not redistributable, so it is not in the repository: download it
and put it in `local-data/geocode-benchmark/` (`benchmarks/README.md`); a script
skips a source that is not there.
