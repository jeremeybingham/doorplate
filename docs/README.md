# Documentation index

Every piece of documentation in the repository, grouped by topic, and a table of what
to check when you change something. This library formats and parses; it does not
validate that an address exists or can receive mail, and no page here says otherwise.

New to the project? Read the [project README](../README.md), then
[How doorplate works](how-it-works.md).

## Using the library

| Page | What it covers |
|---|---|
| [`README.md`](../README.md) | What it is, quickstart, features, working with pandas, Polars, DuckDB and CSV files, the benchmarks at a glance |
| [`crates/doorplate-py/README.md`](../crates/doorplate-py/README.md) | The Python package (PyPI): install, the API, batches and DataFrames, coming from usaddress |
| [`crates/doorplate/README.md`](../crates/doorplate/README.md) | The Rust library (crates.io): install, API, features, batches |
| [`crates/doorplate-cli/README.md`](../crates/doorplate-cli/README.md) | The `doorplate` command: parsing a line, a file or a pipe |
| [`examples/README.md`](../examples/README.md) | Runnable examples: a notebook tour, pandas, Polars and DuckDB pipelines, sample data of several shapes |
| [`usaddress-compat.md`](usaddress-compat.md) | Coming from usaddress: the output in its shape, the label mapping, what differs, how the two are compared |

## How it works, and what it outputs

| Page | What it covers |
|---|---|
| [`how-it-works.md`](how-it-works.md) | The pipeline, the principles, the warnings, the lexicon layers, the tests |
| [`key-format.md`](key-format.md) | The match key (`k2`) and the slug: the contract, and when a key changes |
| [`reso-mapping.md`](reso-mapping.md) | The RESO Data Dictionary 2.0 field mapping |
| [`usps-pub28-notes.md`](usps-pub28-notes.md) | The USPS Publication 28 rules: the source of every table and parser rule, and what was left as it is on purpose |

## Data: places, state data and what data may be used

| Page | What it covers |
|---|---|
| [`places.md`](places.md) | The national place list: sources, licenses, how it is built and compiled in, coverage |
| [`states/README.md`](states/README.md) | State data: what a state's folder holds and how to add one |
| [`states/fl.md`](states/fl.md) | The Florida state data: places, spellings, ZIPs, evidence |
| [`data-policy.md`](data-policy.md) | What data the project uses, what may be committed, and what may be said about data that is not ours to publish |
| [`NOTICE`](../NOTICE), [`LICENSE-MIT`](../LICENSE-MIT), [`LICENSE-APACHE`](../LICENSE-APACHE) | Licenses and third-party credits (GeoNames, the National Address Database) |

## Accuracy, speed and the benchmark suite

| Page | What it covers |
|---|---|
| [`benchmarks.md`](benchmarks.md) | The results: the suite, the geocode benchmark, speed, size and memory |
| [`benchmarks/README.md`](../benchmarks/README.md) | How to run every benchmark, and which one answers which question |
| [`benchmark-suite.md`](benchmark-suite.md) | The benchmark suite's specification: what it holds, how it was built and audited, the rules that keep it fair |
| [`benchmarks/suite/README.md`](../benchmarks/suite/README.md), [`MANIFEST.md`](../benchmarks/suite/v1/MANIFEST.md) | The suite's data folder, and the composition and checksums of `v1` |
| [`tools/harness/README.md`](../tools/harness/README.md), [`SCHEMA.md`](../tools/harness/SCHEMA.md) | The harness (parse-rule comparisons, the pre-release full run on private data, runs on any ingested source, scoring against labeled parts, and the shapes worklist) and the columns of a run |
| [`tools/review/README.md`](../tools/review/README.md) | The review tool: a local page that shows the hard addresses of a harness run to a person, records the verdicts and corrections, and writes a shape-only export that may be shared |
| [`tools/ingest/README.md`](../tools/ingest/README.md) | The record format every address source is turned into, how to write a spec for a source, and `inventory.py`, the table of what is in `local-data/` (issue #93) |

## Test data

| Page | What it covers |
|---|---|
| [`tests/corpus/README.md`](../tests/corpus/README.md) | The golden corpus: the record format, how it is run, the baseline |
| [`tests/external/usaddress/README.md`](../tests/external/usaddress/README.md) | usaddress's labeled test files (vendored, MIT) and how they are used |

## Project, process and community

| Page | What it covers |
|---|---|
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Reporting a misparse, sharing messy data, building and testing, fixing a bug, data changes, the READMEs, releasing |
| [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md) | The tool-neutral guide for AI agents (also a map of the repository), and our own process for Claude Code |
| [`CHANGELOG.md`](../CHANGELOG.md) | What changed in each release, and when keys changed |
| [`site/README.md`](../site/README.md) | The blog and the live demo (Jekyll, published to GitHub Pages): how to publish a post, how the demo is built and the rules for what a page may show |
| [`backlog.md`](backlog.md) | How the issues are organized: the release plan, the labels and milestones, and the row-by-row key comparison that "key-neutral" means |
| [`roadmap.md`](roadmap.md) | What is planned, what depends on what, and what is deliberately not planned |
| [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md), [`SECURITY.md`](../SECURITY.md) | Conduct and reporting a vulnerability |
| [`.github/pull_request_template.md`](../.github/pull_request_template.md), [`.github/ISSUE_TEMPLATE/`](../.github/ISSUE_TEMPLATE/misparse-or-messy-data.md) | The pull request checklist and the misparse issue template |

Some documentation lives in code and is not repeated here: the scripts in `tools/` and
`benchmarks/` explain themselves in their docstrings, the hand-labeled shapes of the
suite are commented in `tools/benchsuite/hand/shapes.txt`, and the Rust API is on
[docs.rs](https://docs.rs/doorplate). Private notes live in `local-data/`, which is
git-ignored and not part of the repository.

## When you change something, check these

A page that describes the thing you changed is out of date the moment you change it.
Look at this table before you open a pull request, and update every page in the row in
the same pull request. The pull request template asks for it.

| You change | Check |
|---|---|
| A parse rule or a table in `crates/doorplate/data/` | [`usps-pub28-notes.md`](usps-pub28-notes.md) (a row with its source); a golden-corpus case and `passing.txt`; [`how-it-works.md`](how-it-works.md) if the behavior it describes changed; [`CHANGELOG.md`](../CHANGELOG.md). If an input's key changes, the key row below |
| What an input's key is | [`key-format.md`](key-format.md) (a new version, never an edit in place); `tests/corpus/keys.jsonl` and `tools/corpus/emit_expect.py`; the four READMEs; [`how-it-works.md`](how-it-works.md); [`CHANGELOG.md`](../CHANGELOG.md) |
| A warning code | [`how-it-works.md`](how-it-works.md) (the list); the four READMEs; the stubs in `crates/doorplate-py/python/doorplate/__init__.pyi` |
| The API, a CLI flag or an output form (a function, a method, a field, a column) | The four READMEs; an example in `examples/` ([`examples/README.md`](../examples/README.md)); [`how-it-works.md`](how-it-works.md); [`usaddress-compat.md`](usaddress-compat.md) (its feature table); [`reso-mapping.md`](reso-mapping.md) if RESO output changed; [`CHANGELOG.md`](../CHANGELOG.md) |
| Output labels in usaddress's shape (`tag`, `parse_tokens`) | [`usaddress-compat.md`](usaddress-compat.md) and the Python README's "Coming from usaddress" |
| The RESO output | [`reso-mapping.md`](reso-mapping.md) (the table and the choices) and `tests/corpus/reso.jsonl` |
| Accuracy or speed figures, or the benchmark scripts | [`benchmarks.md`](benchmarks.md); [`benchmarks/README.md`](../benchmarks/README.md); the figures in the four READMEs that quote them; [`CHANGELOG.md`](../CHANGELOG.md). The suite's `v1` files are never edited: a fix is a `v2` |
| The benchmark suite (its generator, scoring or composition) | [`benchmark-suite.md`](benchmark-suite.md); [`benchmarks/README.md`](../benchmarks/README.md); [`benchmarks/suite/README.md`](../benchmarks/suite/README.md); [`benchmarks.md`](benchmarks.md) |
| Place data or state data | [`places.md`](places.md) or [`states/fl.md`](states/fl.md); [`data-policy.md`](data-policy.md); [`NOTICE`](../NOTICE) when a source needs credit; [`how-it-works.md`](how-it-works.md) (the lexicon layers) |
| How private data is used, or what leaves `local-data/` | [`data-policy.md`](data-policy.md); [`tools/harness/README.md`](../tools/harness/README.md); [`tools/ingest/README.md`](../tools/ingest/README.md); [`tools/review/README.md`](../tools/review/README.md) |
| The golden corpus format or the way it runs | [`tests/corpus/README.md`](../tests/corpus/README.md); [`how-it-works.md`](how-it-works.md) ("Testing") |
| Build commands, the repository layout, the CI jobs or the release steps | [`AGENTS.md`](../AGENTS.md); [`CLAUDE.md`](../CLAUDE.md); [`CONTRIBUTING.md`](../CONTRIBUTING.md); [`how-it-works.md`](how-it-works.md) ("Repository layout" and "Testing") |
| A version number, the alpha notice or the disclaimer | The four READMEs; `Cargo.toml`; [`CHANGELOG.md`](../CHANGELOG.md); the references pull request in [`CONTRIBUTING.md`](../CONTRIBUTING.md) ("Releasing") |
| Adding, renaming or removing a documentation page | This index; the "Using the library" table in [`AGENTS.md`](../AGENTS.md); [`how-it-works.md`](how-it-works.md) ("Reference pages") |

The four READMEs are the project README and the three package pages (PyPI, crates.io
for the library, crates.io for the command). They are published as they are, so their
links are absolute in the three crate READMEs, and each keeps the statement that the
library does not validate deliverability and the Disclaimer section ([`CONTRIBUTING.md`](../CONTRIBUTING.md),
"Package pages and READMEs").
