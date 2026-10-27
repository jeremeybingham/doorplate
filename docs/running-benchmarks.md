# Benchmarks: how to run them

Every way this repository measures doorplate, in one place. The results are in
[`docs/benchmarks.md`](benchmarks.md); the specification of the standard suite and the rules that
keep it fair are in [`docs/benchmark-suite.md`](benchmark-suite.md). The overview with the headline
numbers is in the [project README](../README.md#benchmarks).

This library formats and parses; it does not validate deliverability, and none of these numbers say an
address exists.

## Which one do I run?

There are three kinds of measure here, and they answer different questions.

| I want to know | Run | Needs |
|---|---|---|
| How accurate doorplate is next to usaddress, on addresses neither was made from | `python benchmarks/suite.py compare` | the extension; `usaddress` |
| What only doorplate does: fields input, Pub 28 output, key stability, warnings | `python benchmarks/suite.py doorplate` | the extension |
| Speed and memory under a fixed profile (4 CPUs, 8 GB) | `python benchmarks/suite.py speed` | the extension; `usaddress` |
| All three of the above (about 20 seconds) | `python benchmarks/suite.py all` | the extension; `usaddress` |
| Accuracy on one-line street addresses from an outside data set | `python benchmarks/accuracy.py` | the CLI; `usaddress`; the geocode benchmark (not in the repository) |
| Whether a parse-rule fix generalizes instead of overfitting | `split_geocode_train.py`, then `tools/compare/city_diff.py` | the geocode benchmark |
| Python speed of `parse`, `parse_many`, `parse_fields` against usaddress | `python benchmarks/speed_python.py [N]` | the extension; `usaddress` |
| Speed of batches and of pandas, Polars and DuckDB frames | `python crates/doorplate-py/benchmarks/bench_batch.py [N]` | the extension; the frame libraries |
| Rust speed (criterion) and a CSV file run | `python benchmarks/speed_rust.py [--csv FILE --column NAME]` | Rust |
| Package size, import time, resident memory | `python benchmarks/size_memory.py` | the CLI; the extension; `maturin`; `uv` |
| Release and rule-PR checks on private data (Netsyms, NAD, Florida) | `tools/harness/`, `tools/compare/` | `local-data/` (maintainers only) |

Two things that look like benchmarks are not. The **golden corpus** (`tests/corpus/`, run by
`cargo test` or `doorplate corpus test`) is a regression set that doorplate passes by construction, so
its score says nothing about accuracy on new data. **usaddress's own test files**
(`tests/external/usaddress/`) are usaddress's regression tests, so it scores about 100% on them; they are a
compatibility check, not a contest. `accuracy.py` prints both beside the geocode benchmark so the three
are never mistaken for each other.

If you want one answer, run the suite. Read its fairness rules before using a result to decide what to
change: the suite is not a work list.

## Setup (once)

```sh
cargo build --release -p doorplate-cli          # target/release/doorplate, for accuracy.py and size_memory.py
python -m venv .venv && . .venv/bin/activate
pip install maturin usaddress pandas polars
(cd crates/doorplate-py && maturin develop --release)
```

A debug build is much slower: always use `--release`. The suite runner needs only the extension and
`usaddress`. Run the speed scripts on a quiet machine with the power plan fixed; they report the best of
several runs, the least noisy measure of a CPU-bound loop. Each script prints Markdown to stdout with the
machine, the versions and the input, and changes nothing in the repository.

## The benchmark suite

`benchmarks/suite/v1/` holds 19,586 labeled US addresses and `suite.py` scores doorplate and usaddress on
them. It is the standard benchmark: a fixed set that ships in the repository, with gold labels that come from
the source field of each token and not from either parser, a mix fixed before either parser ran on it, and
one resource profile. It holds both libraries' known blind spots on purpose, so neither is expected to reach
100%.

```sh
python benchmarks/suite.py all --out suite-report.md       # every track and speed
python benchmarks/suite.py compare                          # the comparison with usaddress
python benchmarks/suite.py doorplate                        # the doorplate-only track
python benchmarks/suite.py speed                            # speed and peak memory
```

`--suite DIR` scores another version (a rebuilt copy, or the private twin), `--limit N` runs the first N
records (a quick test), `--min-group N` changes the smallest group a breakdown prints, `--out FILE` also
writes the Markdown.

**Two tracks, never mixed.** The comparison track (`compare.jsonl.gz`) gives both libraries the same
strings and scores their token labels, in usaddress's label set, by character span. The doorplate-only track
(`doorplate.jsonl.gz`) measures what usaddress cannot do: `parse_fields` on pre-split fields against Pub 28
components, the `to_usps` lines, whether the same record in several styles gives one `k3` key, and whether
a wrong parse raises a warning. No figure from the second track appears in a doorplate-versus-usaddress
table.

**Four strata.** `natural` (16,001, a random draw by state population) is the estimate for ordinary input.
`hard` (2,585) holds, for each blind-spot class of either library, the records that fall in it, so it is low
for both by design. `hand` (1,000) is 90 hand-labeled shapes of messy real forms. The runner prints the
`natural` rows first and the whole-suite rows after them; read a stratum, not only the blend.

**The resource profile** is **4 logical CPUs and 8 GB of memory, on Linux**, which a GitHub-hosted
`ubuntu-latest` runner on a public repository and an ordinary laptop both match. The runner applies it itself
(CPU affinity, `RAYON_NUM_THREADS=4`, an 8 GB address-space limit) and its header prints what it got. Speed is
reported on 1 thread and on 4, never on all cores, and leads with ratios; accuracy does not depend on the
profile. On macOS and Windows, run it in Docker with `--cpus=4 --memory=8g`. The `workflow_dispatch` job
`.github/workflows/suite.yml` runs it on a real runner. The profile belongs to benchmark runs only: builds,
tests, the harness and the other tools use all the cores and memory of the machine, and `suite.py --no-profile`
runs the suite unpinned for quick development checks (do not quote its speed).

**What is in `v1/`, and rebuilding it:** [`suite/README.md`](../benchmarks/suite/README.md). `v1` is never edited after it
was published; label errors found later go into `v2`.

## The geocode benchmark and `accuracy.py`

The [geocoding address-parsing benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark)
is an outside data set of one-line US street addresses, IOB-labeled, uppercase and with no commas (no units,
PO boxes or routes). It has three splits: `test` (30,622), `dev` (60,522) and `train` (148,173). It states no
license, so it is not in this repository. To use it, download `test.txt`, `dev.txt` and `train.txt` from its
`benchmark_dataset/` folder into `local-data/geocode-benchmark/` (git-ignored), then convert them to
usaddress's XML format, which `tools/compare/compare_usaddress.py` reads:

```sh
python benchmarks/convert_geocode_benchmark.py test dev train
python benchmarks/accuracy.py
```

`accuracy.py` prints whole-address and token accuracy for the golden corpus, usaddress's test files and the
geocode benchmark (a part is skipped when its source is not there). Which split to believe: the rules and the
place data were first written while reading the `test` split's errors, so `test` over-states accuracy; `dev`
and `train` were not read for that, but `dev`'s most common error classes have since been looked at. So fix
against `train`, check on `dev`, and use `dev` as the estimate (94.5% at the last run, for data of that shape:
one line, US street addresses, a city and a state).

### Fixing against `train` without overfitting

Hold 20% of `train` out, unread: `python benchmarks/split_geocode_train.py` writes `train80_usaddress.xml` (to
fix against) and `train20_heldout_usaddress.xml` (every fifth address; score it only to check that a fix
generalizes) beside the other splits. Then `dev` and `test` are regression checks. Two helpers (counts only,
never an address):

```sh
python tools/compare/city_diff.py BASE_CLI NEW_CLI [train80|train20_heldout|dev|test]   # cities gained and lost
python tools/compare/oneline_fl.py [--binary target/release/doorplate]                  # Florida records as one line
```

The geocode benchmark writes street postdirectionals abbreviated (`N`), so a compass word after a suffix is
always part of the city there; `oneline_fl.py` renders real Florida records (private, from the DBPR files in
`docs/data-policy.md`) as one line with no commas, where spelled-out postdirectionals occur. A rule that helps
one and hurts the other is a rule to look at again (#29).

## Speed and size

| Script | Measures | Needs |
|---|---|---|
| `speed_python.py [N]` | Addresses per second from Python: `parse`, `parse_many`, `parse_fields`, against `usaddress.parse` and `usaddress.tag` on the same inputs | the extension; `usaddress` |
| `crates/doorplate-py/benchmarks/bench_batch.py [N]` | `parse_many` against a loop of `parse`, and the cost of building pandas and Polars frames and of the DuckDB functions | the extension; pandas, Polars, DuckDB |
| `speed_rust.py [--csv FILE --column NAME]` | Rust speed: runs `cargo bench` (criterion, `crates/doorplate/benches/parse.rs`) and, with `--csv`, a CLI file run | Rust; optional CSV |
| `size_memory.py` | Binary, wheel and installed size; import time; resident memory after import and after a batch; usaddress for comparison | the CLI; the extension; `usaddress`; `maturin`; `uv` |

These time the corpus's single-line addresses (committed, invented) and, when `local-data/` has it, the
geocode benchmark's addresses (only timings are printed). The suite's `speed` command times its own inputs
under the fixed profile; use it when you want a figure someone else can reproduce, and these scripts when you
want the shape of the cost (single call, batch, frames).

## Checks on private data (maintainers)

These need `local-data/` and the go-aheads in `CLAUDE.md`; only aggregate numbers leave it
(`docs/data-policy.md`). They check that a rule change helps on real data and does not regress, and they are
not published as accuracy.

| Tool | Does | Read |
|---|---|---|
| `tools/harness/` (`run.py`, `analyze.py`, `compare.py`) | Parses the US rows of the Netsyms database (a 12-second sample comparison per rule; a full run of about 20 minutes on the release commit) and compares two runs | [`docs/tools/harness.md`](tools/harness.md) |
| `tools/harness/nad_score.py` | Scores doorplate against the labeled columns of the National Address Database sample | `docs/tools/harness.md` |
| `tools/compare/compare_usaddress.py` | The token-by-token comparison with usaddress that `suite.py` and `accuracy.py` use; also runs on any labeled XML or CSV | its docstring |
| `tools/compare/oneline_fl.py`, `city_diff.py` | The one-line Florida check and the cities gained and lost (above) | above |
| `profile_inputs.py`, `profile_fold.py`, `profile_heap.py`, `crates/doorplate/examples/profile_loop.rs`, `profile_alloc.rs` | The profiling kit of #90: plain input files from the suite, a single-thread timing loop, allocations per parse, a table of where `perf` samples land (by function and by stage) and where `heaptrack` says the allocations are made | the "Profile" section of [`docs/benchmarks.md`](benchmarks.md) |
| `tools/compare/checkpoint.py` | The foundation checkpoint (`docs/backlog.md`): the key comparison with the released build over all the large sources in one run, keeping the current keys as the baseline for the `k3`; prints a plan and needs `--confirm` | [`docs/backlog.md`](backlog.md) |
| `tools/compare/key_diff.py` | The row-by-row key comparison between two builds over the records files (`dump` in each environment, then `diff`; counts only) | [`docs/backlog.md`](backlog.md) |
| `tools/benchsuite/` | The suite's generator, label audit and inventories; rebuilds the suite from private data | [`docs/benchmark-suite.md`](benchmark-suite.md) |

For a parse-rule pull request: the tests, the sample comparison, and for a rule on one-line input
`city_diff.py` and `oneline_fl.py` (`CLAUDE.md` has the loop). Before a release: `suite.py all`, the speed and
size scripts, one full Netsyms run, and the figures updated in `docs/benchmarks.md` and the package READMEs.
