# Documentation index

Every piece of documentation in the repository, grouped by topic, and a table of what
to check when you change something. This library formats and parses; it does not
validate that an address exists or can receive mail, and no page here says otherwise.

New to the project? Read the [project README](../README.md), then
[How doorplate works](how-it-works.md). These pages are also published as a searchable site, <https://doorplate.readthedocs.io/>, built on Read the Docs
(`mkdocs.yml`; a page added here needs a `nav` entry there).

## Using the library

| Page | What it covers |
|---|---|
| [`index.md`](index.md), [`getting-started.md`](getting-started.md) | The home page of the site; install, a first parse, what it does not do |
| [`python.md`](python.md), [`command-line.md`](command-line.md), [`rust.md`](rust.md) | The tour for each way of using it: Python, the command, the Rust crate |
| [`dataframes.md`](dataframes.md) | pandas, Polars and DuckDB: a column, a table or a file, with timings |
| [`README.md`](../README.md) | What it is, quickstart, features, working with pandas, Polars, DuckDB and CSV files, the benchmarks at a glance |
| [`crates/doorplate-py/README.md`](../crates/doorplate-py/README.md) | The Python package (PyPI): install, the API, batches and DataFrames, coming from usaddress |
| [`crates/doorplate/README.md`](../crates/doorplate/README.md) | The Rust library (crates.io): install, API, features, batches |
| [`crates/doorplate-cli/README.md`](../crates/doorplate-cli/README.md) | The `doorplate` command: parsing a line, a file or a pipe |
| [`examples/README.md`](../examples/README.md) | Runnable examples: a notebook tour, pandas, Polars and DuckDB pipelines, sample data of several shapes |
| [`usaddress-compat.md`](usaddress-compat.md) | Coming from usaddress: the drop-in `doorplate.compat` module, the output in its shape, the label mapping, what differs, how the two are compared |
| [`python-api.md`](python-api.md) | The Python reference: every function, class and helper of the `doorplate` package, generated from the type stubs (so it describes `main`) |
| [`cli.md`](cli.md) | The command-line reference: the commands, their options, the exit codes and the usage text |
| [`custom-layers.md`](custom-layers.md) | The custom layer and its guide: a demo layer, a template, a prompt for an LLM, then the files, the rules, what it reports, and how a layer can change a key |
| [`anonymizing.md`](anonymizing.md) | Sharing messy data: `doorplate anonymize`, `Anonymizer` in Python and Rust, what it changes and keeps, seeds, the faithfulness check, what it can leak, how well it works |

## How it works, and what it outputs

| Page | What it covers |
|---|---|
| [`how-it-works.md`](how-it-works.md) | The pipeline, the principles, the warnings, the lexicon layers, the tests |
| [`warnings.md`](warnings.md) | What each warning tells you, in two groups, and how often rows that carry it disagree with labeled data |
| [`key-format.md`](key-format.md) | The match key (`k4`) and the slug: the contract, and when a key changes |
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
| [`benchmarks.md`](benchmarks.md), [`speed-and-size.md`](speed-and-size.md) | The results (accuracy; speed, size and memory): the suite, the [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark), speed, size and memory |
| [`docs/running-benchmarks.md`](running-benchmarks.md) | How to run every benchmark, and which one answers which question |
| [`benchmark-suite.md`](benchmark-suite.md) | The benchmark suite's specification: what it holds, how it was built and audited, the rules that keep it fair |
| [`benchmarks/suite/README.md`](../benchmarks/suite/README.md), [`MANIFEST.md`](../benchmarks/suite/v1/MANIFEST.md) | The suite's data folder, and the composition and checksums of `v1` |
| [`docs/tools/harness.md`](tools/harness.md), [`SCHEMA.md`](tools/harness-schema.md) | The harness (parse-rule comparisons, the pre-release full run on private data, runs on any ingested source, scoring against labeled parts, and the shapes worklist) and the columns of a run |
| [`docs/tools/review.md`](tools/review.md) | The review tool: a local page that shows the hard addresses of a harness run to a person, records the verdicts and corrections, and writes a shape-only export that may be shared |
| [`docs/tools/ingest.md`](tools/ingest.md) | The record format every address source is turned into, how to write a spec for a source, and `inventory.py`, the table of what is in `local-data/` (issue #93) |

## Test data

| Page | What it covers |
|---|---|
| [`docs/tests/corpus.md`](tests/corpus.md) | The golden corpus: the record format, how it is run, the baseline |
| [`docs/tests/usaddress-tests.md`](tests/usaddress-tests.md) | usaddress's labeled test files (vendored, MIT) and how they are used |

## Project, process and community

| Page | What it covers |
|---|---|
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | Reporting a misparse, sharing messy data, building and testing, fixing a bug, data changes, the READMEs, releasing |
| [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md) | The tool-neutral guide for AI agents (also a map of the repository), and our own process for Claude Code |
| [`repository.md`](repository.md) | The repository layout and how it is tested |
| [`CHANGELOG.md`](../CHANGELOG.md) | What changed in each release, and when keys changed |
| [`change-checklist.md`](change-checklist.md) | What to check when you change something: the pages to update with each kind of change |
| [`site/README.md`](../site/README.md) | The blog and the live demo (Jekyll, published to GitHub Pages): how to publish a post, how the demo is built and the rules for what a page may show |
| [`api-surface.md`](api-surface.md) | The audit of every public name in Rust, Python and the command line, with one decision each (#135) |
| [`backlog.md`](backlog.md) | How the issues are organized: the release plan, the labels and milestones, and the row-by-row key comparison that "key-neutral" means |
| [`roadmap.md`](roadmap.md) | What is planned, what depends on what, and what is deliberately not planned |
| [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md), [`SECURITY.md`](../SECURITY.md) | Conduct and reporting a vulnerability |
| [`.github/pull_request_template.md`](../.github/pull_request_template.md), [`.github/ISSUE_TEMPLATE/`](../.github/ISSUE_TEMPLATE/misparse-or-messy-data.md) | The pull request checklist and the misparse issue template |

Some documentation lives in code and is not repeated here: the scripts in `tools/` and
`benchmarks/` explain themselves in their docstrings, the hand-labeled shapes of the
suite are commented in `tools/benchsuite/hand/shapes.txt`, and the Rust API is on
[docs.rs](https://docs.rs/doorplate). Private notes live in `local-data/`, which is
git-ignored and not part of the repository.

## When you change something

The table of what to check before a pull request is [`change-checklist.md`](change-checklist.md).
