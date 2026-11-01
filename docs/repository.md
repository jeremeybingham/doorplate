# Repository layout and tests

Where things are in the repository and how they are tested. How the parser itself works is on [How doorplate works](how-it-works.md);
what to update with a change is in [When you change something](change-checklist.md).

## Repository layout

```
Cargo.toml                  workspace: doorplate, doorplate-cli, doorplate-py
crates/
  doorplate/                pure Rust, no Python dependency
    build.rs                compiles data/ into static tables
    data/                   suffixes, directionals, units, states, special (.toml);
                            places/ (national list) and states/fl/ (Florida)
    src/                    clean, tokenize, classify, tagger/, assemble, parser, input,
                            place, lexicon, country, intersection, types,
                            emit/{key,usps,reso,slug,display,usaddress}, anonymize, layer, corpus
    tests/                  corpus, property tests, usaddress score floor
    benches/                criterion benchmarks
  doorplate-cli/            the `doorplate` binary
  doorplate-py/             PyO3 bindings, the Python package, its tests
  doorplate-wasm/           the core compiled to WebAssembly for the demo page (not published; shares
                            the command-line tool's json.rs)
tests/corpus/               golden corpus (JSONL) and its baseline
tests/external/usaddress/   usaddress's labeled test files (MIT, vendored)
tools/                      corpus emitter expectations, usaddress comparison, place list, Pub 28 checks,
                            the harness (harness/), the ingest tool that turns any address source
                            into one record format (ingest/), the review page for hard rows (review/) and the benchmark suite generator (benchsuite/)
benchmarks/                 the benchmark suite (suite.py, suite/v1/) and the accuracy, speed and size scripts
site/                       the blog and the live demo (Jekyll), published to GitHub Pages by .github/workflows/pages.yml
examples/                   notebook, Polars, pandas and DuckDB pipelines, sample data
fuzz/                       cargo-fuzz targets (nightly)
docs/                       the documentation (the source of the site)
```

## Testing

- **Golden corpus** (`tests/corpus/*.jsonl`): expected components and warnings; most
  cases also carry the key, slug, USPS and RESO output, written from the specs by
  `tools/corpus/emit_expect.py` (an independent implementation of the rules, so a
  disagreement shows up as a failing case). The runner fails on malformed records
  and on regressions against `passing.txt`. The corpus is hand-labeled and the rules
  were tuned against it, so 100% on it is a regression check, not an accuracy
  measure.
- **USPS round trip**: parsing the USPS output of a parsed address gives the same key.
- **Property tests** (proptest): no panic, valid spans, every emitter, `parse_many`
  consistent with a loop.
- **usaddress score floor**: this parser on usaddress's labeled test files must not
  fall below a recorded score.
- **Fuzzing** (cargo-fuzz, nightly): `parse` (with a `default_state` hint) and
  `parse_fields`, each running every emitter on the result.
- **Python tests**: the wrapper, type stubs, `parse_many`, the dataframe and DuckDB
  helpers, the examples (including the notebook). **Wheels** are built and tested for
  Linux, macOS and Windows.
- **Benchmark suite** (`benchmarks/suite.py`): 19,586 labeled addresses that neither
  library was made from, scored for doorplate and usaddress under a fixed 4-CPU, 8 GB
  profile. It measures accuracy and holds both libraries' blind spots on purpose, so it
  is a benchmark and not a regression test, and a score on it is never a reason to change
  a rule on its own (`benchmark-suite.md`).
- **Checks on private data** (maintainers; only counts leave `local-data/`): a before and
  after comparison on a sample of the Netsyms address database for every parse-rule
  change, a full run over its 146.6 million US rows before a release (no panics, no failed
  rows, warning and mismatch counts compared with the previous run), the National Address
  Database scorecard, and a one-line Florida check (`docs/tools/harness.md`,
  `docs/running-benchmarks.md`, `data-policy.md`).
- **Pub 28 check**: `tools/pub28/verify.py` compares the tables with the live
  Publication 28 pages and runs every Appendix F example through the parser.
- **CI**: `cargo fmt --check`, `clippy -D warnings`, `cargo test --workspace
  --all-features`, the corpus report, the emitter-expectation check, a package
  build and a check of the license files, an sdist build in a clean environment, a short
  fuzz smoke run of each target, a line-coverage job (`cargo llvm-cov`, uploaded to Codecov; informational, `codecov.yml`), the Python suite, the ingest, harness and review tools' tests and the wheel build. The benchmark
  suite and the two release workflows run by hand or on a version tag; the Pages workflow
  runs when `site/` or the parser changes on `main`. CI also builds `doorplate-wasm` for
  `wasm32-unknown-unknown`, so a change to the core cannot break the demo.

## Coverage: what the tests reach, and what is left alone

Coverage is a map of untested code, not a gate: the Codecov checks are informational (`codecov.yml`). It is measured with
`cargo llvm-cov --workspace --all-features` (the `custom-layer` and `corpus` features are on; `build.rs`, the benches, the
tests folders, `corpus.rs`, `doorplate-wasm`, `doorplate-py` and `fuzz/` are left out, see `codecov.yml`). Measured locally, before and after adding tests for what a user can reach:

| | Before | After |
|---|---|---|
| Workspace, regions | 96.5% | 98.1% |
| Workspace, lines | 96.8% | 98.6% |
| `doorplate-cli/src/main.rs` | 85.4% | 93.6% |
| `doorplate-cli/src/json.rs` | 87.5% | 97.5% |
| `doorplate/src/layer/load.rs` | 89.3% | 97.2% |
| `doorplate/src/types.rs` | 92.4% | 99.4% |
| `doorplate/src/clean.rs` | 93.3% | 96.6% |
| `doorplate/src/lexicon.rs` | 95.5% | 95.9% |

`main.rs` ends below the 95% the issue named for it, for the reason in the second item below: what remains is the error arm of `?` on a
failing system call.

What was added: one table-driven test of every kind of wrong layer entry (each message names the file, the entry and the
problem); the command line's usage and error branches (a missing value or column, `--usaddress` and `--tag` on a line and on
stdin, `parse-file` with split columns, an output file, a blank row and a ragged row, `anonymize` to a file, `corpus` with
`--verbose` and `--update-baseline`, a bad layer); and small tests for the character folding, the `Display` forms and a span of
`Fields` input. Every address in them is invented.

**What is left uncovered, and why** (the regions Codecov shows as missed; nothing here is a behavior a user can reach with valid input):

- **Guards on the generated tables** (`lexicon.rs`: `record()`, `checked_mul`, `usize::try_from(..).ok()?`, `.get(index)?` on the
  suffix, unit, state, highway and place tables, about 25 regions). `build.rs` writes those tables from the TOML data, so an index
  that is out of range cannot happen with a build that passed its own table checks; the guards exist so that a corrupt table returns
  `None` instead of panicking (the never-panic rule), and a test would have to corrupt a generated table.
- **`?` on an operating-system failure** (`main.rs`, about 30 regions): writing to a closed stdout or a full disk, a stdin line that
  is not UTF-8, a CSV read that fails halfway, the baseline file of `corpus test --update-baseline` that cannot be written. The
  conversion of an `io::Error` into exit code 2 is tested through the unwritable-output and missing-file cases; the remaining arms
  are the same conversion on other calls.
- **The failure message of an `assert!` inside a test** (`lexicon.rs`, `anonymize.rs`, about 20 regions): the formatting
  code of `assert!(.., "{s:?}")` runs only when the assert fails, so it is counted as missed while the tests pass.
- **Repeated "this entry has no required key" arms** (`layer/load.rs`, 13 `continue` regions): each section of `aliases.toml` and
  `overrides.toml` repeats the same `req_str` check; the check and its message are tested once, for the file where it is cheapest.
- **Layer loader branches that need a broken file system or a shipped override** (`layer/load.rs`: a file that exists but cannot be
  read, a poisoned lock, a layer entry that clashes with a state-specific override the shipped Florida data already has).
- **Thin wrappers over a word list** (`lexicon.rs`: the layer hooks for the non-recipient, numbered-street and city-head lists):
  the lookup is the same one the tested `country`, `place_prefix` and `area` lists use; a test needs an address whose reading hinges
  on an invented word of that one list.
- **Folding of rarely typed letters** (`clean.rs`: `Ł`, `Ř`, `Ź` and the like): each is one entry of the same table the tested letters use.

Not measured at all, by decision (#121): the Python package (pytest drives it, and the wrapper is thin), the `tools/` scripts and the
notebook. Uploading Python coverage as a separate Codecov flag would show the wrapper's real figure without moving the Rust one; it
was left out on purpose to avoid noise, and can be added if wanted.
