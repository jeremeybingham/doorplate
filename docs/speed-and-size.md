# Speed, size and memory

Speed, installed size, memory and where the time goes, measured on 0.3.0 and rerun on 0.4.0. The accuracy figures, the
benchmark suite and the caveats that apply to every number are on [Accuracy](benchmarks.md); how to rerun these
scripts is in [Running the benchmarks](running-benchmarks.md). Speed figures belong to one machine: read the ratios.

## Speed

### Rust (criterion, `crates/doorplate/benches/parse.rs`)

Median of a measurement run, one thread unless noted (0.4.0; [0.3.1 to 0.4.0](benchmarks.md#031-to-040) has the same table for
both builds). The corpus has grown from 529 to 762 inputs since the figures of 0.3.1, so the corpus rows do not compare.

| Benchmark | Time |
|---|---|
| `parse`, street only (`1305 SUNWOOD DR`) | 4.8 µs |
| `parse`, PO box | 6.8 µs |
| `parse`, military | 6.9 µs |
| `parse`, highway | 9.3 µs |
| `parse_fields` (street, city, state, ZIP) | 10.0 µs |
| `parse`, unit and ZIP+4 | 11.1 µs |
| `parse`, full one line | 12.4 µs |
| The 762 corpus inputs, one by one | 11.3 ms (15 µs each) |
| The same, `parse_many` (rayon, 14 threads) | 2.6 ms (3.4 µs each) |
| `to_usps` | 0.75 µs |
| `to_reso` | 1.44 µs |
| `key` | 0.36 µs |
| `slug` | 0.97 µs |

Parsing is by far the biggest cost; the emitters are about a tenth of a parse
or less, and a `ParsedAddress` builds them only when asked.

The command-line tool: `doorplate parse-file` over 440,288 distinct Florida
addresses (line 1, line 2, city, state and ZIP columns; this run a random sample of the
Florida DBPR files, 2026) took 14.5 s,
30,400 rows per second on one thread, including reading the CSV and writing
about 30 columns per row (a 0.3.0 figure on private files, not retaken for 0.4.0).

### Python

`benchmarks/speed_python.py`, 100,000 addresses (the inputs repeated), best of
five runs, pinned to 4 CPUs like the suite (`taskset -c 0-3 env RAYON_NUM_THREADS=4 python benchmarks/speed_python.py`).
The suite's own `speed` command (`python benchmarks/suite.py speed`) is the one to quote; this table shows the
shape of the cost on other inputs.

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` | 16.2 µs | 26.0 µs |
| doorplate `parse`, then `key()` and `to_usps()` | 20.5 µs | 30.6 µs |
| doorplate `tag` | 19.6 µs | 28.9 µs |
| doorplate `parse_tokens` | 19.5 µs | 27.3 µs |
| doorplate `parse_many` (4 threads) | 5.2 µs | 7.3 µs |
| usaddress `parse` | 93.3 µs | 96.5 µs |
| usaddress `tag` | 100.8 µs | 100.9 µs |

Call by call on one thread, `parse_tokens` is 4.8x `usaddress.parse` on the
corpus inputs and 3.5x on the geocode addresses. `parse_many` parses on all
the cores it is given (4 here) with the GIL released: 18x and 13x `usaddress.parse`, which is
single-threaded (usaddress could be run in several processes; that is a
different comparison). A Python call costs about what the Rust parse does
(16 µs against 15 µs on the corpus); the boundary is not the bottleneck.

Building DataFrames (`crates/doorplate-py/benchmarks/bench_batch.py`, 100,000
corpus addresses, 4 CPUs): a loop of `parse` 1.58 s, `parse_many` 0.54 s (2.9x),
`parse_many` into a pandas frame of seven columns 0.71 s (2.2x), into a Polars
frame 0.64 s (2.5x). Reading attributes from 100,000 Python objects is now
most of the time; `to_dict()` on every row costs about as much as parsing again.
**Columns built in Rust (#24, 2026-10-27, measured before and after on the same inputs).** `parse_column` used to read each column off the Python objects (serial, about as long as the parse itself); it now asks Rust for the columns (`_parse_columns`: one list of strings per column, built on a thread per column with the GIL released), with identical values (a test compares every column on the whole corpus). The 15 default columns of 100,000 corpus addresses: pandas 1.03 s to 0.83 s, Polars 0.86 s to 0.70 s, DuckDB 0.79 s to 0.70 s (4 CPUs, the profile above); on 14 CPUs, where the parse is cheap, pandas 0.76 s to 0.54 s, Polars 0.61 s to 0.42 s, DuckDB 0.65 s to 0.51 s. The gain is 1.1x to 1.25x on 4 CPUs and 1.3x to 1.5x on 14, and it grows with the number of columns. No Arrow dependency was added; a public Arrow result is not built (the issue's option 2) because the remaining cost is Python strings, and no user has asked for it. The pre-split path (`parse_fields_many`) still goes through Python objects.

The DuckDB functions (`doorplate.duckdb`) parse a 100,000-row table in 0.59 s with seven
struct fields (2.7x a loop of `parse`) and 0.86 s with all fifteen (1.8x): the cost of
building the Arrow struct grows with the columns, so ask for only those you need. A
1,000,000-row table with four fields ran at about 213,000 rows/s, against about 280,000/s
for `parse_many` on the same strings (a separate run on 2026-10-17 on all 14 threads, not repeated for 0.4.0).

## Size and memory

`benchmarks/size_memory.py`.

| | Size |
|---|---|
| `doorplate` CLI binary (release, as built) | 5.5 MB (4.6 MB stripped) |
| `doorplate` wheel (abi3, one wheel per platform) | 1.8 MB |
| The extension module inside it | 4.4 MB |
| `usaddress` and its dependencies, installed | 4.8 MB (the model is 134 KB; the rest is python-crfsuite) |

The lexicon tables, the national place list and the Florida state data are compiled
in, so there is no model or data file to download or load. The tables are
inside the crate, so the crate package (53 files, 3.6 MiB unpacked,
0.8 MB compressed; not remeasured for 0.4.0) and the Python source distribution (0.9 MB) carry them and
build from a clean directory.

Peak resident memory of a fresh Python process parsing 100,000 addresses
(corpus inputs repeated):

| | Import | After import | After the batch |
|---|---|---|---|
| Python alone | | 16 MB | |
| doorplate, loop of `parse`, each result dropped | 1 ms | 16 MB | 19 MB |
| usaddress, loop of `parse`, each result dropped | 10 ms | 18 MB | 20 MB |
| doorplate, loop of `parse`, 100,000 results kept | 1 ms | 16 MB | 152 MB |
| usaddress, loop of `parse`, 100,000 results kept | 10 ms | 18 MB | 128 MB |
| doorplate, `parse_many`, 100,000 results kept | 1 ms | 16 MB | 243 MB |

The parser itself adds about 2 MB to a process either way. A `ParsedAddress`
holds every component and its source spans (about 1.4 KB each against about
1.1 KB for usaddress's token list). `parse_many` builds all its results at once
on several threads, so its peak is higher than a loop's. usaddress loads its
model on its first call, so its memory after import understates it.

## Profile: where the time goes

Issue #90, measured on `main` at the start of 0.4.0 (2026-10-23), one machine (Intel i9-9900K, 8 cores, WSL2).
The input is the suite's `natural` mix (19,586 addresses, one text form each; `benchmarks/profile_inputs.py`),
parsed on one pinned CPU. Tools: `crates/doorplate/examples/profile_loop.rs` (timing),
`profile_alloc.rs` (a counting allocator), and `benchmarks/profile_fold.py` (folds a `perf record -e cpu-clock -g`
profile into tables; WSL2's perf cannot resolve symbols itself). Absolute numbers are this machine's.

| | Result |
|---|---|
| One address, the mix, one thread | **26.0 µs** (38,400 per second); streets 26.3 µs, PO boxes 12.6, highways 14.7, military 10.4 |
| Allocations per parse | **197** (4.35 KB requested); 102 for a PO box, 120 for a highway or military address |
| `size_of::<ParsedAddress>()` | 928 bytes inline; 2.46 KB per result held in Python (230 MB for 97,930 results) |
| `parse_many`, 1 / 2 / 4 / 8 / 14 threads | 37,400 / 69,100 / 132,000 / 224,000 / 283,000 per second (3.5x at 4, 7.6x at 14 on 8 cores): scaling is good, so allocator contention is not the problem |
| From Python, per row (1 thread) | reading 6 attributes 0.5 µs, `key()` 0.6, `to_usps()` 1.7, **`to_dict()` 16.4** (63% of a parse) |

Samples by pipeline stage (the stack, 10,788 samples; "inclusive" counts a stage anywhere in the stack):

| Stage | Exclusive | Inclusive |
|---|---|---|
| libc (`memcmp`, `malloc`, `memcpy`) | 39% | |
| `lexicon` (lookups, `normalize_key_cow`, `place_key`) | 31% | 43% |
| `std`/`alloc`/`core` (Vec growth, iterators) | 16% | |
| `tokenize` | 5% | 40% |
| `tagger` | 3% | 44% |
| `clean`, `classify`, `assemble`, `parser` | under 2% each | |

The cost is not in one stage but in lexicon lookups made from everywhere: the tokenizer (`Piece::sub`, 33% inclusive,
which tries route, unit and period readings on every piece) and the tagger (`delivery`, `last_line_in`, `street_from`)
each call `suffix`, `directional`, `unit`, `special`, `state`, `is_place` and `place` for the same tokens. Every call
normalizes its key (`normalize_key_cow`, 9.6% exclusive) and binary-searches a table (the `memcmp` in libc, whose
callers are mostly the lexicon and Vec growth). `place_key` is 14% inclusive and allocates a `String` per candidate.

Where the 197 allocations come from (`heaptrack` on 2,000 inputs, 10,000 parses; `benchmarks/profile_heap.py`,
which counts each allocation against the innermost `doorplate::` frame of its stack):

| Module | Share | Per parse | The big sites |
|---|---|---|---|
| `classify` | 48.5% | 95 | `longest_at` and `longest_ending` build a joined `String` for every candidate length (about 78 per parse), `join` 17 |
| `lexicon` | 23.7% | 47 | `place_key` 29 (a `String` per candidate), `highway_in` 8.6, `place` 6.0 |
| `tokenize` | 18.7% | 37 | `Piece::sub` 18.4, `glue_place` 8.7, `tokenize` 7.6 |
| `country`, `assemble`, `tagger`, `parser`, `clean` | 9% | 18 | `country::strip_trailing` 5.4, `assemble` 5.1 |

Candidates, ranked by the effect on batch throughput and memory (not by effort):

| # | Candidate | Effect | Risk | Status |
|---|---|---|---|---|
| 0 | `longest_at` and `longest_ending` join the tokens once and slice (each shorter run is a prefix, or a suffix, of the longest) | **-30% allocations (197 to 138 per parse, 4.35 to 3.92 KB) and +6.0% throughput measured** (38,800 to 41,200 per second, best of five, three runs each, against `main`) | low: **zero key and warning differences** against 0.3.1 over 37.0M rows | prototyped on branch `perf-join-once` (commit `f096e1f`) |
| 1 | Make the table lookups themselves cheaper. A parse makes 135 table lookups, only 56 of them distinct (59% repeats), and 83% are misses; the binary searches called `memcmp` for every step, so the first byte is now compared inline (**+10% measured**, with no change to a call site). With #3 below, **+17% in all** (43,000 to 50,300 per second, best of five, three runs each, against the branch of #148) | measured | low: a test compares the comparison with `str::cmp` | done (#147). A per-token cache of the results would remove the repeats (up to 59% of the lookups) but needs `Token` and the call sites to change; not worth its code until the lookups are the top cost again |
| 2 | `place_key` without a `String` per candidate: the key is written into one buffer, kept per thread for `place` and `is_place` (29 allocations per parse before, the largest site after #0) | **-25% allocations (138 to 103 per parse, after #0) and +4.0% throughput measured** (41,380 to 43,030 per second, best of five, three runs each) | low: a test compares it with the old implementation on every place name and 30,000 generated strings | done (#148) |
| 3 | One pass in `normalize_key_cow` (no substring search for two spaces, one scan of the bytes instead of four) | **+3.5% measured** (38,500 to 39,800 per second); no allocation change | low: zero key and warning differences over 37.0M rows | done with #1 (#147): +7% of the 17% (50,300 against 47,300 per second) |
| 4 | `Vec::with_capacity` in `tokenize` and `assemble` | 3 fewer allocations of 197, no speed change | none | measured, **not worth doing** |
| 5 | Token text borrowed from the cleaned input instead of a `String` per token | the token-creating sites (`Piece::sub`, `tokenize`, `Piece::emit`) make about 28 of the 197 (14%), though not all of those are token `String`s; smaller than #0 and #2 | medium: `Token.text` is read in many places | attributed; do after #0 and #2 |
| 6 | A columnar result for pandas and Polars (#24), since `to_dict()` costs 16 µs a row | large for that path, none for the parser | API (after 0.4.0) | an existing issue |

Not done, and why: the chunk size of `parse_many` and a different allocator were not measured (a new dependency is
ruled out anyway). The held-results memory in Python (2.46 KB each, against 928 bytes inline) is mostly the owned
`String` and `Vec` fields of a result; a smaller result type is an API change.
