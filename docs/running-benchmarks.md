# Benchmarks: how to run them

Results: [`benchmarks.md`](benchmarks.md). The suite's specification and fairness rules:
[`benchmark-suite.md`](benchmark-suite.md).

## Which one do I run?

| I want to know | Run | Needs |
|---|---|---|
| How accurate doorplate is next to usaddress, on addresses neither was made from | `python benchmarks/suite.py compare` | the extension; `usaddress` |
| What only doorplate does: fields input, Pub 28 output, key stability, warnings | `python benchmarks/suite.py doorplate` | the extension |
| Speed and memory under a fixed profile (4 CPUs, 8 GB) | `python benchmarks/suite.py speed` | the extension; `usaddress` |
| All three of the above (about 20 seconds) | `python benchmarks/suite.py all` | the extension; `usaddress` |
| Accuracy on one-line street addresses from an outside data set | `python benchmarks/accuracy.py` | the CLI; `usaddress`; the geocode benchmark (not in the repository) |
| The geocode benchmark scored as its paper does (F1 per label, Parsing Score), next to the paper's models | `python benchmarks/geocode_paper_compare.py [test] [dev] [train]` | the extension; `usaddress`; the geocode benchmark |
| Whether a parse-rule fix generalizes instead of overfitting | `split_geocode_train.py`, then `tools/compare/city_diff.py` | the geocode benchmark |
| Python speed of `parse`, `parse_many`, `parse_fields` against usaddress (and `fastaddress` when it is installed) | `python benchmarks/speed_python.py [N]` | the extension; `usaddress`; optionally `fastaddress` |
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

`suite.py` scores doorplate and usaddress on the 19,586 records in `benchmarks/suite/v1/`. What it holds and why
it is fair: [`benchmark-suite.md`](benchmark-suite.md).

```sh
python benchmarks/suite.py all --out suite-report.md       # every track and speed
python benchmarks/suite.py compare                          # the comparison with usaddress
python benchmarks/suite.py doorplate                        # the doorplate-only track
python benchmarks/suite.py speed                            # speed and peak memory
```

`--cache-usaddress` reuses the usaddress results stored by an earlier run instead of running usaddress again (the comparison
track's predictions and the speed track's `parse` timing; `speed_python.py` takes the same flag for its usaddress rows). A stored result is
used only when the usaddress version and the inputs are the same, and, for a timing, the machine and CPU count; otherwise usaddress is run and
its result stored. The file is `local-data/benchmarks/usaddress-cache.json` (delete it to start again), and the report says which rows came
from the cache and when they were made. Quote a cached figure as cached: usaddress's time was measured on that earlier day.

`--suite DIR` scores another version (`benchmarks/suite/v2`, which scores the same records with a letter A to D after the house number
right as the number's suffix or as a unit; a rebuilt copy; or the private twin), `--limit N` runs the first N
records (a quick test), `--min-group N` changes the smallest group a breakdown prints, `--out FILE` also
writes the Markdown.

The runner prints the `natural` stratum first and the whole suite after it; read a stratum, not only the blend. It applies
the resource profile itself (4 logical CPUs, 8 GB, Linux; its header prints what it got), and `suite.py --no-profile`
runs unpinned for quick development checks (do not quote its speed). On macOS and Windows, run it in Docker with
`--cpus=4 --memory=8g`; the `workflow_dispatch` job `.github/workflows/suite.yml` runs it on a real runner.

Data and rebuilding: [`suite/README.md`](../benchmarks/suite/README.md). Versions: [`benchmark-suite.md`](benchmark-suite.md#versions).

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
against `train`, check on `dev`, and use `dev` as the estimate (94.4% on the 0.6.1 release build, see [`benchmarks.md`](benchmarks.md), for data of that shape:
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
one and hurts the other is a rule to look at again.

## Speed and size

| Script | Measures | Needs |
|---|---|---|
| `speed_python.py [N]` | Addresses per second from Python: `parse`, `parse_many`, `parse_fields`, against `usaddress.parse` and `usaddress.tag` on the same inputs (and `fastaddress.parse` and `.tag` when `fastaddress` can be imported) | the extension; `usaddress` |
| `crates/doorplate-py/benchmarks/bench_batch.py [N]` | `parse_many` against a loop of `parse`, and the cost of building pandas and Polars frames and of the DuckDB functions | the extension; pandas, Polars, DuckDB |
| `speed_rust.py [--csv FILE --column NAME]` | Rust speed: runs `cargo bench` (criterion, `crates/doorplate/benches/parse.rs`) and, with `--csv`, a CLI file run | Rust; optional CSV |
| `size_memory.py` | Binary, wheel and installed size; import time; resident memory after import and after a batch; usaddress for comparison | the CLI; the extension; `usaddress`; `maturin`; `uv` |

These time the corpus's single-line addresses (committed, invented) and, when `local-data/` has it, the
geocode benchmark's addresses (only timings are printed). The suite's `speed` command times its own inputs
under the fixed profile; use it when you want a figure someone else can reproduce, and these scripts when you
want the shape of the cost (single call, batch, frames).

### Profiling the engine

Judge engine speed by instruction counts, which repeat exactly; wall time on a shared machine varies by 10% to 60%.

1. Write plain input files from the suite: `python benchmarks/profile_inputs.py` (`mix.txt` is the `natural` mix).
2. Build the timing loop with frame pointers and symbols:
   `RUSTFLAGS="-C force-frame-pointers=yes" CARGO_PROFILE_RELEASE_STRIP=false cargo build --release -p doorplate --example profile_loop`.
3. Run it under callgrind on a few thousand inputs:
   `valgrind --tool=callgrind --callgrind-out-file=OUT target/release/examples/profile_loop FILE 1`, then read
   `callgrind_annotate --inclusive=yes OUT`.
4. To compare two builds, profile both on the same file and compare function by function. A function that inlines
   differently in the two builds shows as new or gone: check its callers before believing a difference. Cut the number
   of calls before rewriting a hot function.
5. Quote wall time only from alternating builds in one session on one pinned CPU, best of five.

**The CI guard (#672).** Every pull request runs `tools/perf/callgrind_guard.sh BASE_REF` (the `perf-guard` job in
`.github/workflows/ci.yml`): it builds `profile_loop` at the base and at the head, counts instructions under callgrind
on the first 4,000 inputs of the `natural` mix (5 passes, 20,000 parses) and fails when the head executes more than 1%
more. Both builds run in the same job, so a compiler update cannot trip it, and the counts repeat to within a few instructions. A rule that
costs more on purpose (the 0.6.0 rules added +1.3%) says why in the pull request and takes the label `perf-ok`, which
skips the job. Run it locally with the same command (needs `valgrind`; a few minutes).

Allocations per parse: `crates/doorplate/examples/profile_alloc.rs` (a counting allocator) and `benchmarks/profile_heap.py`
(groups a `heaptrack` run by the innermost `doorplate::` frame). `benchmarks/profile_fold.py` folds a `perf record -g`
profile into tables by function and by stage, where `perf` can resolve symbols.

What an output costs on top of `parse` (callgrind, one run per mode, then subtract the `parse` run): `crates/doorplate/examples/profile_emit.rs` (modes `parse`, `key`, `usps`, `reso`, `display`, `usaddress`).

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
| `profile_inputs.py`, `profile_fold.py`, `profile_heap.py`, `crates/doorplate/examples/profile_loop.rs`, `profile_alloc.rs` | The profiling kit: plain input files from the suite, a single-thread timing loop, allocations per parse, a table of where `perf` samples land (by function and by stage) and where `heaptrack` says the allocations are made | [Profiling the engine](#profiling-the-engine) |
| `tools/compare/checkpoint.py` | The foundation checkpoint (`docs/backlog.md`): the key comparison with the released build over all the large sources in one run, keeping the current keys as the baseline for the `k3`; prints a plan and needs `--confirm` | [`docs/backlog.md`](backlog.md) |
| `tools/compare/key_diff.py` | The row-by-row key comparison between two builds over the records files (`dump` in each environment, then `diff`; counts only; each dump records the version and the checkout's commit, and warns when the installed extension is older than the source; `dump --unit` also writes the unit-level key and the unit fields, which a rule that only moves a unit needs, since the property-level key has no unit) | [`docs/backlog.md`](backlog.md) |
| `tools/benchsuite/` | The suite's generator, label audit and inventories; rebuilds the suite from private data | [`docs/benchmark-suite.md`](benchmark-suite.md) |

For a parse-rule pull request: the tests, the sample comparison, and for a rule on one-line input
`city_diff.py` and `oneline_fl.py` (`CLAUDE.md` has the loop). Before a release: `suite.py all`, the speed and
size scripts, one full Netsyms run, and the figures updated in `docs/benchmarks.md` and the package READMEs.
