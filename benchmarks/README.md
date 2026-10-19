# Benchmarks

Scripts behind `docs/benchmarks.md`. They measure accuracy, speed and size so
the numbers can be rerun. Each script prints Markdown to stdout (the machine,
the versions and the input are in the output) and changes nothing in the
repository. The geocode benchmark is not redistributable, so it is not in the
repository (see below); a script skips a source that is not there.

This library formats and parses; it does not validate deliverability, and none
of these numbers say an address exists.

## Setup

```sh
cargo build --release -p doorplate-cli          # target/release/doorplate
python -m venv .venv && . .venv/bin/activate
pip install maturin usaddress pandas polars
(cd crates/doorplate-py && maturin develop --release)
```

A debug build is much slower: always use `--release`.

### The geocode benchmark

The
[geocoding address-parsing benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark)
(one-line US street addresses, IOB-labeled) has three splits: `test` (30,622),
`dev` (60,522) and `train` (148,173). It states no license, so it is not in
this repository. To use it, download `test.txt`, `dev.txt` and `train.txt` from
its `benchmark_dataset/` folder into `local-data/geocode-benchmark/`
(git-ignored), then convert them to usaddress's XML format, which
`tools/compare/compare_usaddress.py` reads:

```sh
python benchmarks/convert_geocode_benchmark.py test dev train
```

The rules and the place data were written while reading the `test` split's errors,
so `test` over-states accuracy. `dev` and `train` were not read for that, which
makes them the better estimate (but see `docs/benchmarks.md`: `dev`'s most common
error classes have since been looked at, so fix against `train` and check on `dev`.)

### Fixing against `train` without overfitting

Hold 20% of `train` out, unread: `python benchmarks/split_geocode_train.py` writes
`train80_usaddress.xml` (to fix against) and `train20_heldout_usaddress.xml` (every fifth address;
score it only to check that a fix generalizes) beside the other splits. Then `dev` and `test` are
regression checks. Two helpers (counts only, never an address):

```sh
python tools/compare/city_diff.py BASE_CLI NEW_CLI [train80|train20_heldout|dev|test]   # cities gained and lost
python tools/compare/oneline_fl.py [--binary target/release/doorplate]                  # Florida records as one line
```

The benchmark writes street postdirectionals abbreviated (`N`), so a compass word after a suffix is
always part of the city there; `oneline_fl.py` renders real Florida records (private, from the DBPR
files in `docs/data-policy.md`) as one line with no commas, where spelled-out postdirectionals occur.
A rule that helps one and hurts the other is a rule to look at again (#29).

## Scripts

| Script | Measures | Needs |
|---|---|---|
| `accuracy.py` | Whole-address and token accuracy: the golden corpus, usaddress's test files, the geocode benchmark (blind) | the CLI; `usaddress`; the geocode benchmark for the last |
| `speed_python.py` | Addresses per second from Python: `parse`, `parse_many`, `parse_fields`, against `usaddress.parse` and `usaddress.tag` on the same inputs | the extension; `usaddress` |
| `speed_rust.py` | Rust speed: runs `cargo bench` (criterion) and a CLI file run, prints the medians | Rust; optional CSV |
| `suite.py` | The benchmark suite (`benchmarks/suite/`): labeled addresses scored for doorplate and usaddress under a 4-CPU, 8 GB profile, the doorplate-only track, and speed (`benchmarks/suite/README.md`) | the extension; `usaddress` |
| `size_memory.py` | Binary, wheel and installed size; import time; resident memory after import and after a batch; usaddress for comparison | the CLI; the extension; `usaddress`; `maturin` |

```sh
python benchmarks/suite.py all
python benchmarks/accuracy.py
python benchmarks/speed_python.py [N]
python benchmarks/speed_rust.py [--csv FILE --column NAME]
python benchmarks/size_memory.py
```

Run on a quiet machine, with the power plan fixed. The speed scripts report the
best of several runs, which is the least noisy measure of a CPU-bound loop.
The existing `crates/doorplate-py/benchmarks/bench_batch.py` times pandas and
Polars frame building as well.
