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
