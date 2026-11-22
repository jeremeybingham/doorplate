# Speed, size and memory

The headline is the [parser showdown](#against-usaddress-and-libpostal)'s cost table: doorplate, usaddress and libpostal
timed on the same strings in one session. The sections after it are doorplate's own measurements, in more detail and by
build: Rust, Python, DataFrames, size and memory, and speed by version.

**Builds.** 0.6.2 (`041c38d`, the parser code of the release), measured 2026-11-14, unless a table names another build
(the command-line, DataFrame and DuckDB figures were not re-run for the release). One machine (Intel Core i9-9900K, Linux
on WSL2), so read the ratios. Accuracy is on [Benchmarks: accuracy](benchmarks.md); how to rerun these scripts and
profile the engine is in [Running the benchmarks](running-benchmarks.md).

## Against usaddress and libpostal

From the [showdown report](https://github.com/jeremeybingham/address-parser-showdown/blob/main/report/REPORT.md), section 8:
the pinned run of 2026-11-16 (doorplate 0.6.0, usaddress 0.5.16, libpostal with the Senzing 1.2.0 model). 100,000
strings (the golden set's 2,439 repeated), median of 5 passes, 4 CPUs; each parser's own Python call is timed, without
the adapter.

| | doorplate | usaddress | libpostal |
|---|---|---|---|
| Strings per second, one process | **72,028** | 8,952 | 14,577 |
| Strings per second, 4 processes | **223,510** | 28,054 | 43,951 |
| Load time (import and first parse) | 0.003 s | 0.012 s | 3.480 s |
| Memory after loading, one process | 27 MB | 27 MB | 2,958 MB |
| Memory, 4 processes together | 37 MB | 42 MB | 11,771 MB |
| Install size | 4.9 MB | 4.8 MB | 2,993 MB |

- **doorplate is about 8 times as fast as usaddress and 5 times as fast as libpostal** in one process. libpostal needs
  about 3 GB of memory and disk per process, where the other two need under 30 MB.
- **Speed varies 5 to 14% between runs** on this machine (the showdown's run of 2026-11-15 measured 64,876, 8,395 and
  12,818 strings per second), so read the ratios.
- **0.6.2 is faster.** The showdown's [releases appendix](https://github.com/jeremeybingham/address-parser-showdown/blob/main/report/RELEASES.md)
  timed 0.6.2 at 113,315 strings per second in one process and 317,934 in four, in a session of its own (usaddress and
  libpostal were not re-timed there). doorplate's own figures for 0.6.2 follow.
- These figures time one string per call. doorplate's batch call, `parse_many`, runs on several threads in one process
  with the GIL released ([Python](#python) below); neither of the others has one.

## Speed

### Rust (criterion, `crates/doorplate/benches/parse.rs`)

0.6.2 (`041c38d`), 2026-11-14. Median of a measurement run, one thread unless noted, unpinned (it varies by several percent from run to run).

| Benchmark | Time |
|---|---|
| `parse`, street only (`1305 SUNWOOD DR`) | 1.9 µs |
| `parse`, PO box | 3.4 µs |
| `parse`, military | 2.7 µs |
| `parse`, highway | 3.3 µs |
| `parse_fields` (street, city, state, ZIP) | 5.0 µs |
| `parse`, unit and ZIP+4 | 4.3 µs |
| `parse`, full one line | 4.5 µs |
| The corpus inputs, one by one | 9.6 ms |
| The same, `parse_many` (rayon, 14 threads) | 2.1 ms |
| `to_usps` | 0.59 µs |
| `to_reso` | 1.16 µs |
| `key` | 0.30 µs |
| `slug` | 0.78 µs |

Parsing is the biggest cost; each emitter takes 0.3 to 1.2 µs against 2 to 5 µs
for a parse, and a `ParsedAddress` builds them only when asked.

The command-line tool: `doorplate parse-file` over 440,288 distinct Florida
addresses (line 1, line 2, city, state and ZIP columns, a random sample of the
Florida DBPR files) took 14.5 s, 30,400 rows per second on one thread, including
reading the CSV and writing about 30 columns per row. That run is on private files
and on an older build; read it as an order of magnitude.

### Python

`benchmarks/speed_python.py`, 100,000 addresses (the inputs repeated), run unpinned on all 14 threads, so `parse_many` has 14.
The suite's own `speed` command (`python benchmarks/suite.py speed`, [below](#speed-by-version)) is the one to quote
(it pins 4 CPUs); this table shows the shape of the cost on other inputs.

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` | 6.6 µs | 7.5 µs |
| doorplate `parse`, then `key()` and `to_usps()` | 9.3 µs | 10.8 µs |
| doorplate `tag` | 9.3 µs | 10.5 µs |
| doorplate `parse_tokens` | 9.2 µs | 10.5 µs |
| doorplate `parse_many` (14 threads) | 1.5 µs | 1.7 µs |
| usaddress `parse` | 90.6 µs | 97.0 µs |
| usaddress `tag` | 98.4 µs | 101.2 µs |

Call by call on one thread, `parse_tokens` is 9.9x `usaddress.parse` on the
corpus inputs and 9.3x on the geocode addresses. `parse_many` parses on all
the cores it is given (14 here) with the GIL released: 59x and 57x `usaddress.parse`, which is
single-threaded (usaddress could be run in several processes; that is a
different comparison). A Python call costs about what the Rust parse does;
the boundary is not the bottleneck. usaddress 0.5.16 was run live.

#### Against fastaddress

[`fastaddress`](https://github.com/vinvomero/fastaddress) (MIT, 0.1.0) runs usaddress's trained model in Rust with the
same Python API, so it is the fairer speed baseline. One run on 0.6.2 (`041c38d`), 2026-11-14,
pinned to 4 CPUs, 100,000 addresses, best of five; usaddress run live:

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` (a `ParsedAddress`) | 6.6 µs | 7.5 µs |
| doorplate `parse_tokens` (labels, the shape of `usaddress.parse`) | 9.2 µs | 10.4 µs |
| doorplate `parse_many` (4 threads) | 2.5 µs | 2.7 µs |
| fastaddress `parse` (labels) | 9.5 µs | 11.4 µs |
| fastaddress `tag` (a dict) | 9.8 µs | 11.4 µs |
| usaddress `parse` | 89.6 µs | 96.6 µs |
| usaddress `tag` | 97.0 µs | 101.2 µs |

Like for like (labels), fastaddress takes 1.04x the time of `parse_tokens` on the corpus inputs and 1.09x on the geocode
addresses (0.86x and 0.96x on 0.6.1, 0.75x on a 0.6.0 pre-release build): `parse_tokens` has passed it. doorplate `parse` returns the whole `ParsedAddress` in less time than
fastaddress takes for the labels, and `parse_many` is the only batch call of the three.
fastaddress gave exactly usaddress's output on every input tried, so its accuracy is usaddress's.

Building DataFrames (`crates/doorplate-py/benchmarks/bench_batch.py`, 100,000
corpus addresses, 4 CPUs, 0.6.2 on 2026-11-14): a loop of `parse` 0.66 s, `parse_many` 0.26 s (2.6x),
`parse_many` into a pandas frame of seven columns 0.43 s (1.5x), into a Polars
frame 0.34 s (1.9x). The speed-ups are smaller than in 0.4.0 (2.9x, 2.2x, 2.5x) because the loop they are measured against got 2.4x faster. Reading attributes from 100,000 Python objects is
most of the time; `to_dict()` on every row costs about as much as parsing again.
`parse_column` asks Rust for the columns (one list of strings per column, built on a thread per column
with the GIL released) instead of reading them off the Python objects: for the 15 default columns of
100,000 corpus addresses it takes 0.55 s into pandas and 0.40 s into Polars on 4 CPUs (the earlier gain over reading the objects, 1.1x to 1.25x on 4 CPUs and 1.3x to 1.5x on 14, was measured on 0.4.x and not repeated), and the gain
grows with the number of columns. No Arrow dependency was added and no public Arrow result is built: the
remaining cost is Python strings. The pre-split path (`parse_fields_many`) still goes through Python objects.

The DuckDB functions (`doorplate.duckdb`) parse a 100,000-row table in 0.29 s with seven
struct fields (2.3x a loop of `parse`) and 0.44 s with all fifteen (1.5x), on 4 CPUs in 0.6.2: the cost of
building the Arrow struct grows with the columns, so ask for only those you need. A
1,000,000-row table with four fields ran at about 213,000 rows/s, against about 280,000/s
for `parse_many` on the same strings (an older run on all 14 threads, not repeated).

## Size and memory

`benchmarks/size_memory.py`.

| | Size |
|---|---|
| `doorplate` CLI binary (release, as built) | 6.7 MB (6.5 MB stripped) |
| `doorplate` wheel (abi3, one wheel per platform) | 2.5 MB (6.5 MB unpacked) |
| The extension module inside it | 6.3 MB |
| `usaddress` and its dependencies, installed | 4.8 MB (the model is 0.1 MB; the rest is python-crfsuite) |

The binary and the extension are 1.5 MB larger than in 0.6.1 (5.2 to 6.7 MB, 4.8 to 6.3 MB): from 0.6.2 `build.rs` writes the place and
ZIP tables as static data (#703 G6) instead of building them on the first parse (the likely cause; the growth was not bisected). The wheel went from
2.1 to 2.5 MB. The lexicon tables, the national place list and the Florida curated rows are compiled
in, so there is no model or data file to download or load. The tables are
inside the crate, so the crate package (0.8 MB compressed) and the Python source
distribution (0.9 MB) carry them and build from a clean directory.

Peak resident memory of a fresh Python process parsing 100,000 addresses
(corpus inputs repeated):

| | Import | After import | After the batch |
|---|---|---|---|
| Python alone | | 16 MB | |
| doorplate, loop of `parse`, each result dropped | 1 ms | 17 MB | 21 MB |
| usaddress, loop of `parse`, each result dropped | 10 ms | 18 MB | 20 MB |
| doorplate, loop of `parse`, 100,000 results kept | 1 ms | 17 MB | 160 MB |
| usaddress, loop of `parse`, 100,000 results kept | 10 ms | 18 MB | 131 MB |
| doorplate, `parse_many`, 100,000 results kept | 1 ms | 17 MB | 254 MB |

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

Every release tag in one session, 2026-11-13, at the release (`v0.6.1`, `5a72a70`; the 0.6.2 column is a later session, 2026-11-14, described below): one pinned CPU (`profile_loop` from
`v0.6.1` built into each tag with frame pointers, `taskset -c 2`, the first 4,000 `natural` inputs, 20 repetitions, best of five, three
alternating rounds that agreed within about 2%), and callgrind on the same binaries (one pass of five loops over the 4,000 inputs,
divided by 20,000 parses). These are the figures in the [0.6.1 blog post](https://jeremeybingham.github.io/doorplate/2026/11/13/doorplate-0-6-1.html):

| | 0.3.1 | 0.4.0 | 0.4.1 | 0.5.0 | 0.5.1 | 0.6.0 | 0.6.1 | 0.6.2 |
|---|---|---|---|---|---|---|---|---|
| Wall time per parse (µs, median round) | 25.75 | 21.08 | 21.01 | 23.16 | 10.56 | 11.18 | 8.10 | 5.98 |
| Parses per second (median round) | 38,831 | 47,428 | 47,604 | 43,179 | 94,661 | 89,436 | 123,453 | 167,154 |
| Instructions per parse (callgrind) | about 187,200 | about 156,500 | about 157,500 | about 171,600 | about 86,200 | about 89,700 | about 62,700 | about 47,000 |

The 0.6.2 column was measured on 2026-11-14 at `041c38d` with the same method, in a session of its own with `v0.6.1` rebuilt beside it, three alternating rounds (0.6.2: 5.98, 5.97 and 6.00 µs; 0.6.1: 7.91, 7.93 and 8.00 µs; instructions 46,986 and 62,696 per parse). The older columns are the 2026-11-13 session, whose 0.6.1 figure (8.10 µs) is 2% above this session's, so compare 0.6.2 with the 0.6.1 of its own session: 0.6.2 takes 24.6% less time than 0.6.1 (1.32x the parses per second) and 25.1% fewer instructions. Between 0.6.0 and 0.6.2 that is 1.87x the parses per second on the 2026-11-13 figures.

0.6.1 takes 27% less time than 0.6.0 (1.38x the parses per second) and 30% fewer instructions; the changelog's −27.6% is the sum of
the #672 steps on their own bases. The rule releases cost time: 0.5.0 took 10% longer than 0.4.1, 0.6.0 6% longer than 0.5.1 (4% more
instructions).

Python `parse` for every release tag in one session, 2026-11-13 (each tag built with `maturin develop --release`; the
golden-corpus inputs of `main` repeated to 100,000, best of five, the median of three alternating rounds that agreed within
about 2%; unpinned on a quiet machine), with each release's size (from earlier runs, not re-measured in this session):

| | 0.3.1 | 0.4.0 | 0.4.1 | 0.5.0 | 0.5.1 | 0.6.0 | 0.6.1 | 0.6.2 |
|---|---|---|---|---|---|---|---|---|
| Python `parse`, golden-corpus inputs, per second | 53,710 | 66,037 | 64,734 | 57,333 | 107,380 | 101,919 | 134,761 | 150,949 (one run) |
| CLI binary, release as built / stripped (MB) | 5.0 / 4.4 | 5.5 / 4.6 | 6.1 / 5.1 | 6.2 / 5.2 | 5.2 / 5.0 | 5.2 / 5.0 | 5.2 / 5.0 | 6.7 / 6.5 |
| Wheel (MB) | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.1 | 2.1 | 2.5 |

From Python, 0.6.1 makes 1.32x the parses per second of 0.6.0 (24% less time per call), less than the engine's 27% because
the Python object work around a parse did not change. The [Python table](#python) above (a different run, 123,826 per
second for the same row on 0.6.1) is the one with the other calls. The 0.6.2 figure is a single run on 2026-11-14, not an alternating session: against the
123,826 of the same kind of run on 0.6.1 it is 1.22x (150,949 per second), and the 0.6.2 size figures are from the same day.

The benchmark suite's own `speed` command on 0.6.2 (`041c38d`, 2026-11-14; the 19,586 inputs, the 4-CPU profile, best of 3; peak memory 159 MB
with usaddress loaded, 157 MB for doorplate alone; usaddress run live, so its rate differs from the 9,297 of the 0.6.0 run, cached from 2026-10-31; on 0.6.1 the same command gave 82,331, 110,178 and 324,740):

| | Addresses per second | Against usaddress `parse` |
|---|---|---|
| usaddress `parse` (1 thread, no batch call) | 9,150 | 1.0x |
| doorplate `parse_tokens` (1 thread) | 98,830 | 10.8x |
| doorplate `parse_many` (1 thread) | 139,851 | 15.3x |
| doorplate `parse_many` (4 threads) | 426,574 | 46.6x |
