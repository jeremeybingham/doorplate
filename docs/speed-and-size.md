# Speed, size and memory

Figures: 0.5.1 (`c68760e`) unless a table names another build; one machine (Intel Core i9-9900K, Linux on WSL2), so read
the ratios. Accuracy is on [Benchmarks: accuracy](benchmarks.md); how to rerun these scripts and profile the engine is in
[Running the benchmarks](running-benchmarks.md).

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
The suite's own `speed` command (`python benchmarks/suite.py speed`, [below](#speed-by-version)) is the one to quote; this
table shows the shape of the cost on other inputs.

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

#### Against fastaddress

[`fastaddress`](https://github.com/vinvomero/fastaddress) (MIT, 0.1.0) runs usaddress's trained model in Rust with the
same Python API, so it is the fairer speed baseline. One run, 0.6.0-dev (`48206ef`), pinned to 4 CPUs, 100,000
addresses, best of five; the usaddress rows from the cache:

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` (a `ParsedAddress`) | 9.9 µs | 11.9 µs |
| doorplate `parse_tokens` (labels, the shape of `usaddress.parse`) | 12.5 µs | 14.7 µs |
| doorplate `parse_many` (4 threads) | 3.5 µs | 4.0 µs |
| fastaddress `parse` (labels) | 9.3 µs | 11.0 µs |
| fastaddress `tag` (a dict) | 9.7 µs | 11.2 µs |
| usaddress `parse` | 88.0 µs | 93.4 µs |
| usaddress `tag` | 96.4 µs | 97.8 µs |

Like for like (labels), fastaddress takes 0.75x the time of `parse_tokens`; doorplate `parse` returns the whole
`ParsedAddress` in about the time fastaddress takes for the labels, and `parse_many` is the only batch call of the three.
fastaddress gave exactly usaddress's output on every input tried, so its accuracy is usaddress's.

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

Every build in one session (the release tags, and 0.6.0-dev at `4b07638`; Python unpinned on a quiet machine):

| | 0.3.1 | 0.4.0 | 0.4.1 | 0.5.0 | 0.5.1 | 0.6.0-dev |
|---|---|---|---|---|---|---|
| Python `parse`, golden-corpus inputs, per second | 54,788 | 66,611 | 65,311 | 57,489 | 104,870 | 103,030 |
| Instructions for 4,000 inputs (callgrind, millions) | | 3,094 | 3,117 | 3,395 | 1,706 | 1,728 |
| CLI binary, release as built / stripped (MB) | 5.0 / 4.4 | 5.5 / 4.6 | 6.1 / 5.1 | 6.2 / 5.2 | 5.2 / 5.0 | 5.2 / 5.0 |
| Wheel (MB) | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 |

The benchmark suite's own `speed` command (the 19,586 inputs, the 4-CPU profile, best of 3; peak memory 154 to 157 MB
with the inputs):

| | Addresses per second | Against usaddress `parse` |
|---|---|---|
| usaddress `parse` (1 thread, no batch call) | 9,297 | 1.0x |
| doorplate `parse_tokens` (1 thread) | 43,411 | 4.7x |
| doorplate `parse_many` (1 thread) | 57,484 | 6.2x |
| doorplate `parse_many` (4 threads) | 137,985 | 14.8x |
