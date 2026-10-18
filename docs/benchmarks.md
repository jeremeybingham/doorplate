# Benchmarks

Accuracy, speed and size of doorplate, measured 2026-10-17. The scripts are in
`benchmarks/` (`benchmarks/README.md`) so every number can be rerun. usaddress
(the Python CRF library, 0.5.16) is one reference point, not the frame: it is
the tool people know, and the two libraries do different jobs (usaddress labels
tokens; doorplate also standardizes, builds a key and a slug, and reports
diagnostics).

This library formats and parses; it does not validate deliverability. None of
the figures below say an address exists or can receive mail.

**Machine:** Intel Core i9-9900K (14 threads), 49 GB RAM, Linux 6.18 on WSL2,
Rust 1.91, Python 3.13 (speed and size runs in a virtual environment),
doorplate 0.2.0 and usaddress 0.5.16, built with `--release`.

## In short

| | doorplate | usaddress |
|---|---|---|
| Geocode benchmark, dev split, whole address (coarse) | 92.6% | 88.1% |
| usaddress's own test files, whole address (coarse) | 99.2% | 100.0% |
| One address from Python, `parse` / `usaddress.parse` | 17 µs | 83 µs |
| 100,000 addresses, `parse_many` / a loop of `usaddress.parse` | 0.26 s | 8.3 s |
| One address in Rust (median of the corpus shapes) | 7 to 17 µs | |
| Installed size (wheel / package and dependencies) | 1.7 MB (4.1 MB unpacked) | 4.8 MB |
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
| **dev** | 60,522 | **92.6%** | 88.1% |
| train | 148,173 | 92.5% | 88.1% |
| test | 30,622 | 96.4% | 88.2% |

| dev split | doorplate | usaddress |
|---|---|---|
| Tokens (coarse) | 98.4% | 97.6% |
| Whole address (coarse) | 92.6% | 88.1% |
| Tokens (fine) | 95.7% | 95.4% |
| Whole address (fine) | 82.7% | 80.2% |

Neither library was trained on any split. **Read the dev figure (92.6%) as the
estimate, not the test figure (96.4%).** doorplate's rules and place list were written
after reading the *test* split's error classes, so test is optimistic; dev and train were
not read for that and agree with each other to 0.1 point. The 4-point gap is mostly place
names: city tokens are 97.1% right on test and 93.2% on dev (usaddress 95.7%), because
neighborhoods and unincorporated communities (`GLEN IRIS`, `DOWNTOWN MONTGOMERY`) that
the place list lacks are read as part of the street, and a few county-road forms (`LEE ROAD 123`,
`CTY ROAD 321`) are missed. The fix plan is issue #29.
Once the dev split's most common error classes had been listed (to write this up), it was
no longer fully blind: fixes should be made against train and checked on dev.

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

437 of 437 (100%). The corpus is written alongside the parser and every bug
fix adds a case, so it is a regression check and says nothing about accuracy on
new data.

## Speed

### Rust (criterion, `crates/doorplate/benches/parse.rs`)

Median of a measurement run, one thread unless noted.

| Benchmark | Time |
|---|---|
| `parse`, street only (`1305 SUNWOOD DR`) | 6.6 µs |
| `parse`, PO box | 7.6 µs |
| `parse`, military | 7.6 µs |
| `parse`, highway | 11.7 µs |
| `parse_fields` (street, city, state, ZIP) | 12.3 µs |
| `parse`, unit and ZIP+4 | 14.4 µs |
| `parse`, full one line | 16.5 µs |
| The 437 corpus inputs, one by one | 7.8 ms (18 µs each) |
| The same, `parse_many` (rayon, 14 threads) | 2.1 ms (4.8 µs each) |
| `to_usps` | 0.75 µs |
| `to_reso` | 1.47 µs |
| `key` | 0.37 µs |
| `slug` | 1.01 µs |

Parsing is by far the biggest cost; the emitters are about a tenth of a parse
or less, and a `ParsedAddress` builds them only when asked.

The command-line tool: `doorplate parse-file` over 440,288 distinct Florida
public-record addresses (line 1, line 2, city, state and ZIP columns) took 15.4 s,
28,600 rows per second on one thread, including reading the CSV and writing
about 30 columns per row.

### Python

`benchmarks/speed_python.py`, 100,000 addresses (the inputs repeated), best of
five runs.

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` | 17 µs | 29 µs |
| doorplate `parse`, then `key()` and `to_usps()` | 20 µs | 33 µs |
| doorplate `tag` | 19 µs | 32 µs |
| doorplate `parse_tokens` | 19 µs | 31 µs |
| doorplate `parse_many` (14 threads) | 2.6 µs | 3.9 µs |
| usaddress `parse` | 83 µs | 94 µs |
| usaddress `tag` | 90 µs | 98 µs |

Call by call on one thread, `parse_tokens` is 4.3x `usaddress.parse` on the
corpus inputs and 3.0x on the geocode addresses. `parse_many` parses on all
cores with the GIL released: 32x and 24x `usaddress.parse`, which is
single-threaded (usaddress could be run in several processes; that is a
different comparison). A Python call costs about what the Rust parse does
(17 µs against 18 µs on the corpus); the boundary is not the bottleneck.

Building DataFrames (`crates/doorplate-py/benchmarks/bench_batch.py`, 100,000
corpus addresses): a loop of `parse` 1.71 s, `parse_many` 0.26 s (6.5x),
`parse_many` into a pandas frame of seven columns 0.43 s (4.0x), into a Polars
frame 0.35 s (4.9x). Reading attributes from 100,000 Python objects is now
most of the time; `to_dict()` on every row costs about as much as parsing again.

## Size and memory

`benchmarks/size_memory.py`.

| | Size |
|---|---|
| `doorplate` CLI binary (release, as built) | 5.0 MB (4.4 MB stripped) |
| `doorplate` wheel (abi3, one wheel per platform) | 1.7 MB |
| The extension module inside it | 4.1 MB |
| `usaddress` and its dependencies, installed | 4.8 MB (the model is 134 KB; the rest is python-crfsuite) |

The lexicon tables, the national place list and the Florida pack are compiled
in, so there is no model or data file to download or load. The tables are
inside the crate, so the crate package (52 files, 3.6 MiB unpacked,
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
| usaddress, loop of `parse`, 100,000 results kept | 10 ms | 18 MB | 126 MB |
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
