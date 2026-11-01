# Speed, size and memory

Speed, installed size, memory and where the time goes, measured on 0.5.1 (`c68760e`, taken as `0.5.1-dev`; the engine changes since 0.5.0
are speed only, and keys, warnings and unit fields are equal to 0.5.0's). The accuracy figures, the benchmark suite and the
caveats that apply to every number are on [Accuracy](benchmarks.md); how to rerun these scripts is in
[Running the benchmarks](running-benchmarks.md). Speed figures belong to one machine (Intel Core i9-9900K, Linux on WSL2): read the ratios.

## Speed

### Rust (criterion, `crates/doorplate/benches/parse.rs`)

Median of a measurement run, one thread unless noted, unpinned (it varies by several percent from run to run).

| Benchmark | Time |
|---|---|
| `parse`, street only (`1305 SUNWOOD DR`) | 4.1 µs |
| `parse`, PO box | 7.5 µs |
| `parse`, military | 6.0 µs |
| `parse`, highway | 7.7 µs |
| `parse_fields` (street, city, state, ZIP) | 10.7 µs |
| `parse`, unit and ZIP+4 | 10.6 µs |
| `parse`, full one line | 10.8 µs |
| The corpus inputs, one by one | 12.4 ms |
| The same, `parse_many` (rayon, 14 threads) | 2.7 ms |
| `to_usps` | 0.60 µs |
| `to_reso` | 1.13 µs |
| `key` | 0.44 µs |
| `slug` | 1.21 µs |

Parsing is by far the biggest cost; the emitters are about a tenth of a parse
or less, and a `ParsedAddress` builds them only when asked.

The command-line tool: `doorplate parse-file` over 440,288 distinct Florida
addresses (line 1, line 2, city, state and ZIP columns, a random sample of the
Florida DBPR files) took 14.5 s, 30,400 rows per second on one thread, including
reading the CSV and writing about 30 columns per row. That run is on private files
and on an older build; read it as an order of magnitude.

### Python

`benchmarks/speed_python.py`, 100,000 addresses (the inputs repeated), best of
five runs, pinned to 4 CPUs like the suite (`taskset -c 0-3 env RAYON_NUM_THREADS=4 python benchmarks/speed_python.py`).
The suite's own `speed` command (`python benchmarks/suite.py speed`) is the one to quote; this table shows the
shape of the cost on other inputs.

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` | 13.7 µs | 16.8 µs |
| doorplate `parse`, then `key()` and `to_usps()` | 18.3 µs | 20.8 µs |
| doorplate `tag` | 16.8 µs | 20.4 µs |
| doorplate `parse_tokens` | 17.6 µs | 21.1 µs |
| doorplate `parse_many` (4 threads) | 5.0 µs | 5.8 µs |
| usaddress `parse` | 87.0 µs | 93.4 µs |
| usaddress `tag` | 95.5 µs | 97.8 µs |

Call by call on one thread, `parse_tokens` is 4.9x `usaddress.parse` on the
corpus inputs and 4.4x on the geocode addresses. `parse_many` parses on all
the cores it is given (4 here) with the GIL released: 17x and 16x `usaddress.parse`, which is
single-threaded (usaddress could be run in several processes; that is a
different comparison). A Python call costs about what the Rust parse does;
the boundary is not the bottleneck. The usaddress rows come from a cache of
one run on this machine (same usaddress version and inputs).

Building DataFrames (`crates/doorplate-py/benchmarks/bench_batch.py`, 100,000
corpus addresses, 4 CPUs, 0.4.0): a loop of `parse` 1.58 s, `parse_many` 0.54 s (2.9x),
`parse_many` into a pandas frame of seven columns 0.71 s (2.2x), into a Polars
frame 0.64 s (2.5x). Reading attributes from 100,000 Python objects is
most of the time; `to_dict()` on every row costs about as much as parsing again.
`parse_column` asks Rust for the columns (one list of strings per column, built on a thread per column
with the GIL released) instead of reading them off the Python objects: for the 15 default columns of
100,000 corpus addresses that is 1.1x to 1.25x faster on 4 CPUs and 1.3x to 1.5x on 14, and the gain
grows with the number of columns. No Arrow dependency was added and no public Arrow result is built: the
remaining cost is Python strings. The pre-split path (`parse_fields_many`) still goes through Python objects.

The DuckDB functions (`doorplate.duckdb`) parse a 100,000-row table in 0.59 s with seven
struct fields (2.7x a loop of `parse`) and 0.86 s with all fifteen (1.8x): the cost of
building the Arrow struct grows with the columns, so ask for only those you need. A
1,000,000-row table with four fields ran at about 213,000 rows/s, against about 280,000/s
for `parse_many` on the same strings (an older run on all 14 threads, not repeated).

## Size and memory

`benchmarks/size_memory.py`.

| | Size |
|---|---|
| `doorplate` CLI binary (release, as built) | 5.2 MB (5.0 MB stripped) |
| `doorplate` wheel (abi3, one wheel per platform) | 2.1 MB (5.0 MB unpacked) |
| The extension module inside it | 4.8 MB |
| `usaddress` and its dependencies, installed | 4.8 MB (the model is 134 KB; the rest is python-crfsuite) |

The lexicon tables, the national place list and the Florida state data are compiled
in, so there is no model or data file to download or load. The tables are
inside the crate, so the crate package (0.8 MB compressed) and the Python source
distribution (0.9 MB) carry them and build from a clean directory.

Peak resident memory of a fresh Python process parsing 100,000 addresses
(corpus inputs repeated):

| | Import | After import | After the batch |
|---|---|---|---|
| Python alone | | 16 MB | |
| doorplate, loop of `parse`, each result dropped | 1 ms | 16 MB | 19 MB |
| usaddress, loop of `parse`, each result dropped | 14 ms | 18 MB | 20 MB |
| doorplate, loop of `parse`, 100,000 results kept | 1 ms | 16 MB | 158 MB |
| usaddress, loop of `parse`, 100,000 results kept | 16 ms | 18 MB | 130 MB |
| doorplate, `parse_many`, 100,000 results kept | 2 ms | 16 MB | 253 MB |

The parser itself adds about 2 MB to a process either way. A `ParsedAddress`
holds every component and its source spans (about 1.4 KB each against about
1.1 KB for usaddress's token list). `parse_many` builds all its results at once
on several threads, so its peak is higher than a loop's. usaddress loads its
model on its first call, so its memory after import understates it.

## Speed by version

Engine speed is instructions per parse (callgrind repeats exactly) and wall time on one pinned CPU, on the suite's `natural` mix,
measured on 0.5.1 (`c68760e`):

| | 0.4.1 | 0.5.0 | 0.5.1 |
|---|---|---|---|
| Instructions per parse | about 157,500 | about 171,600 | about 85,900 |
| Wall time per parse, one pinned CPU | 31.1 µs | 33.3 µs | 15.6 µs |

0.5.0 was 7% to 9% slower than 0.4.1 (its added rules do more lookups on the same tokens); that was accepted for the
`k4` rules. 0.5.1 is half the time of 0.4.1 and 2.1x the parses per second. The Python and criterion figures above move less
than the engine does, because the Python object work around a parse is not part of the parser. Wall time on this machine varies
10% to 60% between days, so these ratios come from alternating builds in one session, best of five.

## Profile: where the time goes

### The first profile (0.4.0)

The first profile, measured on `main` at the start of 0.4.0 (an old build, kept for the method and the shape of the cost), one machine (Intel i9-9900K, 8 cores, WSL2).
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
| 0 | `longest_at` and `longest_ending` join the tokens once and slice (each shorter run is a prefix, or a suffix, of the longest) | **-30% allocations (197 to 138 per parse, 4.35 to 3.92 KB) and +6.0% throughput measured** (38,800 to 41,200 per second, best of five, three runs each, against `main`) | low: **zero key and warning differences** against 0.3.1 over 37.0M rows | done |
| 1 | Make the table lookups themselves cheaper. A parse makes 135 table lookups, only 56 of them distinct (59% repeats), and 83% are misses; the binary searches called `memcmp` for every step, so the first byte is now compared inline (**+10% measured**, with no change to a call site). With candidate 3 below, **+17% in all** (43,000 to 50,300 per second, best of five, three runs each) | measured | low: a test compares the comparison with `str::cmp` | done. A per-token cache of the results would remove the repeats (up to 59% of the lookups) but needs `Token` and the call sites to change; not worth its code until the lookups are the top cost again |
| 2 | `place_key` without a `String` per candidate: the key is written into one buffer, kept per thread for `place` and `is_place` (29 allocations per parse before, the largest site after 0) | **-25% allocations (138 to 103 per parse, after 0) and +4.0% throughput measured** (41,380 to 43,030 per second, best of five, three runs each) | low: a test compares it with the old implementation on every place name and 30,000 generated strings | done |
| 3 | One pass in `normalize_key_cow` (no substring search for two spaces, one scan of the bytes instead of four) | **+3.5% measured** (38,500 to 39,800 per second); no allocation change | low: zero key and warning differences over 37.0M rows | done with #1: +7% of the 17% (50,300 against 47,300 per second) |
| 4 | `Vec::with_capacity` in `tokenize` and `assemble` | 3 fewer allocations of 197, no speed change | none | measured, **not worth doing** |
| 5 | Token text borrowed from the cleaned input instead of a `String` per token | the token-creating sites (`Piece::sub`, `tokenize`, `Piece::emit`) make about 28 of the 197 (14%), though not all of those are token `String`s; smaller than 0 and 2 | medium: `Token.text` is read in many places | attributed; do after 0 and 2 |
| 6 | A columnar result for pandas and Polars, since `to_dict()` costs 16 µs a row | large for that path, none for the parser | API | done in 0.4.x (see Python above) |

Not done, and why: the chunk size of `parse_many` and a different allocator were not measured (a new dependency is
ruled out anyway). The held-results memory in Python (2.46 KB each, against 928 bytes inline) is mostly the owned
`String` and `Vec` fields of a result; a smaller result type is an API change.

### The 0.5.1 round

The engine was profiled with `valgrind --tool=callgrind`, which gives instruction counts per function that repeat exactly from run to run
(wall time on this machine varies by 10% to 60%). Build `profile_loop` with `RUSTFLAGS="-C force-frame-pointers=yes" CARGO_PROFILE_RELEASE_STRIP=false`,
run `valgrind --tool=callgrind --callgrind-out-file=OUT target/release/examples/profile_loop FILE 1` on a few thousand inputs of
`benchmarks/profile_inputs.py`'s `mix.txt`, and read `callgrind_annotate --inclusive=yes OUT`. Compare two builds function by function; a function
that inlines differently in the two builds shows as new or gone, so check the callers before believing a difference. Each change below kept every key,
warning and unit field equal to the `k4` keys (zero differences over seven sources, 36.9M rows), and was kept only when it gained about 2% or was
exact and cheap; the instruction figures are per parse on the `natural` mix unless a percentage is given.

The 0.5.0 slowdown (9% in instructions, 157,500 to 171,600) was 57% tokenizer and 41% tagger: most of the tokenizer part was
`drop_unit_separators` looking up the previous and next word of every token before testing whether the token was a `-` or `/`, and the rest is the tagger's
added rules making more lookups on the same tokens.

| Change | Effect |
|---|---|
| A bit filter per keyed table: a lookup that cannot match is answered without the binary search (two bits per key from one hash; about 1.4% of misses still search; a custom layer adds to the table, never removes from it) | 21.8 to 18.4 µs per parse; 165,200 to 143,600 instructions. 83% of all lookups miss, and a binary search mispredicts its branches, so wall time fell more than instructions |
| First-word test for `special` (a run of more than one token is joined only when some multi-word key starts with its first token; with a layer every run is tried) | 18.5 to 17.4 µs; 143,600 to 138,200 instructions |
| Release profile: `lto = "fat"`, `codegen-units = 1` (table below) | -3.1% instructions |
| First two bytes of a spelling tested against the filter before it is normalized (`state`, `unit`, `special`, `highway`, military) | -5.3% |
| A bit filter for the place tables | -2.5% (less than the profile suggested: most `place_key` work is the per-word expansion, not the final search) |
| `glue_place`: look for the cut before running the vetoes (a test keeps the old order as a reference and compares both on 60,000 generated words and contexts) | -11.6% |
| `highway_in` normalizes once and fills one pre-sized `String` | -2.0% |
| Anchors (a later state or ZIP) computed once per piece; removes a loop that grew with the square of the piece count | -1.5% |
| `zip_agrees` in `last_line_in` evaluated lazily (only a state that is also a street suffix reads it) | -5.6% |
| `join` reserves its length first; first-word tests for `highway_at`, the directionals and states | -4.4% together |
| Plain tokens (ASCII letters and digits) skip the six punctuation readings in `Piece::sub` | -6.3% |
| A level-phrase guard in `units`; filters hold the start of the run of keys for each first byte | -1.6% together |
| The first-word filters reject a token by its first two bytes before normalizing | -2.0% |

Result, the `natural` mix: about 157,500 (0.4.1), 171,600 (0.5.0), 138,200 (before the round), about 85,900 instructions per parse now.

Tried and not kept: a per-token cache of lookup results (it removed none of the lookups and changed nothing in time: the tagger asks about each
token about once; the repeats are different runs); fusing normalizing and hashing in one pass (+1.1%: most tokens are already keys, so the borrowed path was cheap);
a branch-free `normalize_key_cow` (+2.1%: most tokens that are not keys leave the early-exit loop at the first byte); a per-table cap on the length of a
joined run (about 45 call sites for about 1%); `panic = "abort"` (0.05% of instructions, 2% of the stripped CLI, and the Python extension cannot use it);
an explicit `opt-level = 3` (the release default). For WebAssembly, `opt-level = "s"` is 1.8% smaller (3.74 MB) but 25% slower (about 57 against 45 µs
per address through `parse_batch` in Node), and fat LTO changes its speed less than the noise, so the module keeps the default level; `wasm-opt` was not tried.

The release profile, measured by callgrind on the first 4,000 inputs of the `natural` mix:

| Variant | Instructions per parse |
|---|---|
| Cargo defaults (16 codegen units, no LTO) | 136,700 |
| `codegen-units = 1` only | 137,000 (+0.2%) |
| thin LTO | 134,300 (-1.7%) |
| fat LTO, `codegen-units = 1` (kept) | 132,500 (-3.1%) |
| the same plus `panic = "abort"` (CLI only) | 132,400 (-3.2%) |

| Size and build time | Defaults | Kept |
|---|---|---|
| CLI binary, unstripped / stripped | 6.49 / 5.46 MB | 5.41 / 5.22 MB |
| Wheel (maturin, stripped) | 2.194 MB | 2.151 MB |
| WebAssembly, raw / gzip | 3.81 / 1.51 MB | 3.82 / 1.52 MB |
| Cold build: CLI / wheel / wasm | 12 / 17 / 12 s | 37 / 39 / 21 s |

Leads for a later round: re-take wall time, re-profile, then `malloc`/`free` (about 17% of instructions), `Parser::parse` self cost and further cuts in the number of calls
(cut call counts before rewriting a hot function).
