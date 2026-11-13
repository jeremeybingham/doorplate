# Speed, size and memory

Figures: 0.6.1 (`c0976c7`), measured 2026-11-13, unless a table names another build (the criterion, command-line,
DataFrame, DuckDB and fastaddress figures were not re-run for the release); one machine (Intel Core i9-9900K, Linux on WSL2), so read
the ratios. Accuracy is on [Benchmarks: accuracy](benchmarks.md); how to rerun these scripts and profile the engine is in
[Running the benchmarks](running-benchmarks.md).

## Speed

### Rust (criterion, `crates/doorplate/benches/parse.rs`)

0.5.1 (`c68760e`), not re-run for 0.6.0. Median of a measurement run, one thread unless noted, unpinned (it varies by several percent from run to run).

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

`benchmarks/speed_python.py`, 100,000 addresses (the inputs repeated), run unpinned on all 14 threads, so `parse_many` has 14.
The suite's own `speed` command (`python benchmarks/suite.py speed`, [below](#speed-by-version)) is the one to quote
(it pins 4 CPUs); this table shows the shape of the cost on other inputs.

| | Corpus inputs | Geocode addresses |
|---|---|---|
| doorplate `parse` | 8.1 µs | 9.5 µs |
| doorplate `parse`, then `key()` and `to_usps()` | 11.2 µs | 13.0 µs |
| doorplate `tag` | 10.8 µs | 12.6 µs |
| doorplate `parse_tokens` | 10.9 µs | 12.5 µs |
| doorplate `parse_many` (14 threads) | 1.6 µs | 1.9 µs |
| usaddress `parse` | 91.9 µs | 99.9 µs |
| usaddress `tag` | 99.5 µs | 104.2 µs |

Call by call on one thread, `parse_tokens` is 8.5x `usaddress.parse` on the
corpus inputs and 8.0x on the geocode addresses. `parse_many` parses on all
the cores it is given (14 here) with the GIL released: 57x and 52x `usaddress.parse`, which is
single-threaded (usaddress could be run in several processes; that is a
different comparison). A Python call costs about what the Rust parse does;
the boundary is not the bottleneck. usaddress 0.5.16 was run live.

#### Against fastaddress

[`fastaddress`](https://github.com/vinvomero/fastaddress) (MIT, 0.1.0) runs usaddress's trained model in Rust with the
same Python API, so it is the fairer speed baseline. One run on a 0.6.0 pre-release build (`48206ef`, not re-run for the release), pinned to 4 CPUs, 100,000
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
corpus addresses, 4 CPUs, 0.4.0, not re-run): a loop of `parse` 1.58 s, `parse_many` 0.54 s (2.9x),
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
| `usaddress` and its dependencies, installed | 4.8 MB (the model is 0.1 MB; the rest is python-crfsuite) |

The lexicon tables, the national place list and the Florida state data are compiled
in, so there is no model or data file to download or load. The tables are
inside the crate, so the crate package (0.8 MB compressed) and the Python source
distribution (0.9 MB) carry them and build from a clean directory.

Peak resident memory of a fresh Python process parsing 100,000 addresses
(corpus inputs repeated):

| | Import | After import | After the batch |
|---|---|---|---|
| Python alone | | 16 MB | |
| doorplate, loop of `parse`, each result dropped | 1 ms | 17 MB | 20 MB |
| usaddress, loop of `parse`, each result dropped | 12 ms | 18 MB | 20 MB |
| doorplate, loop of `parse`, 100,000 results kept | 1 ms | 17 MB | 159 MB |
| usaddress, loop of `parse`, 100,000 results kept | 10 ms | 18 MB | 131 MB |
| doorplate, `parse_many`, 100,000 results kept | 1 ms | 16 MB | 253 MB |

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

Wall-time retake, 2026-11-12 (#672): `main` at `159b3dc` (after sections B and C) against the release tags, one session, one pinned CPU
(`taskset -c 2`), the first 4,000 inputs of the `natural` mix (`profile_loop`, 20 repetitions, best of five), three alternating rounds that
agreed within about 1%. This input file is not the one behind the 0.5.1 column above, so the two tables do not compare:

| | 0.4.1 | 0.5.0 | 0.6.0 | `main` (`159b3dc`) |
|---|---|---|---|---|
| Wall time per parse (µs, rounds 1 to 3) | 20.91, 21.09, 21.18 | 22.78, 22.81, 22.69 | 10.91, 11.00, 10.89 | 7.96, 7.95, 7.84 |
| Parses per second (median round) | about 47,400 | about 43,900 | about 91,600 | about 125,700 |

`main` takes 27% less time than 0.6.0 (1.37x the parses per second), which matches the callgrind figure (−27.6%). 0.5.1 was not built for this run.

Every release tag in one session, 2026-11-13, at the release (`v0.6.1`, `5a72a70`): the same recipe as the retake (`profile_loop` from
`v0.6.1` built into each tag with frame pointers, `taskset -c 2`, the first 4,000 `natural` inputs, 20 repetitions, best of five, three
alternating rounds that agreed within about 2%), and callgrind on the same binaries (one pass of five loops over the 4,000 inputs,
divided by 20,000 parses). These are the figures in the [0.6.1 blog post](https://jeremeybingham.github.io/doorplate/2026/11/13/doorplate-0-6-1.html):

| | 0.3.1 | 0.4.0 | 0.4.1 | 0.5.0 | 0.5.1 | 0.6.0 | 0.6.1 |
|---|---|---|---|---|---|---|---|
| Wall time per parse (µs, median round) | 25.75 | 21.08 | 21.01 | 23.16 | 10.56 | 11.18 | 8.10 |
| Parses per second (median round) | 38,831 | 47,428 | 47,604 | 43,179 | 94,661 | 89,436 | 123,453 |
| Instructions per parse (callgrind) | about 187,200 | about 156,500 | about 157,500 | about 171,600 | about 86,200 | about 89,700 | about 62,700 |

0.6.1 takes 27% less time than 0.6.0 (1.38x the parses per second) and 30% fewer instructions; the changelog's −27.6% is the sum of
the #672 steps on their own bases. The rule releases cost time: 0.5.0 took 10% longer than 0.4.1, 0.6.0 6% longer than 0.5.1 (4% more
instructions).

Every build in one session (the release tags, and a 0.6.0 pre-release build at `4b07638`; Python unpinned on a quiet machine):

| | 0.3.1 | 0.4.0 | 0.4.1 | 0.5.0 | 0.5.1 | 0.6.0 pre-release |
|---|---|---|---|---|---|---|
| Python `parse`, golden-corpus inputs, per second | 54,788 | 66,611 | 65,311 | 57,489 | 104,870 | 103,030 |
| Instructions for 4,000 inputs (callgrind, millions) | | 3,094 | 3,117 | 3,395 | 1,706 | 1,728 |
| CLI binary, release as built / stripped (MB) | 5.0 / 4.4 | 5.5 / 4.6 | 6.1 / 5.1 | 6.2 / 5.2 | 5.2 / 5.0 | 5.2 / 5.0 |
| Wheel (MB) | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 |

The 0.6.0 release run (`a6a7df4`; a different session, so not comparable with the table above) gave 97,769 per second for
Python `parse` on the same inputs; the 0.6.1 run (`c0976c7`, the Python table above) gives 123,826 per second, unpinned. The 0.6.1 build has a 5.2 / 5.0 MB CLI binary and a 2.1 MB wheel.

The benchmark suite's own `speed` command on 0.6.1 (`c0976c7`, 2026-11-13; the 19,586 inputs, the 4-CPU profile, best of 3; peak memory 158 MB
with usaddress loaded, 155 MB for doorplate alone; usaddress run live, so its rate differs from the 9,297 of the 0.6.0 run, cached from 2026-10-31):

| | Addresses per second | Against usaddress `parse` |
|---|---|---|
| usaddress `parse` (1 thread, no batch call) | 8,880 | 1.0x |
| doorplate `parse_tokens` (1 thread) | 82,331 | 9.3x |
| doorplate `parse_many` (1 thread) | 110,178 | 12.4x |
| doorplate `parse_many` (4 threads) | 324,740 | 36.6x |
