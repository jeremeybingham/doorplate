# AGENTS.md

Guidance for AI coding agents and people working with this repository, with
tool-neutral instructions. Claude Code reads `CLAUDE.md`, which imports this file
and adds the project's own process requirements.

`doorplate` parses US addresses into components, USPS Publication 28 and RESO Data
Dictionary 2.0 output, a canonical match key and a slug, with diagnostics. It is a
pure-Rust library (`crates/doorplate`), a command-line tool (`crates/doorplate-cli`)
and a Python package built with PyO3 and maturin (`crates/doorplate-py`). **It formats
and parses; it does not validate that an address exists or can receive mail.** Do not
imply otherwise in docs or code comments.

## Using the library

| You want | Go to |
|---|---|
| Install and a first parse (Python) | [`crates/doorplate-py/README.md`](crates/doorplate-py/README.md) (PyPI: `pip install doorplate`) |
| Install and a first parse (Rust) | [`crates/doorplate/README.md`](crates/doorplate/README.md) (`cargo add doorplate`), API on [docs.rs](https://docs.rs/doorplate) |
| The command-line tool | [`crates/doorplate-cli/README.md`](crates/doorplate-cli/README.md) (`cargo install doorplate-cli`) |
| Runnable examples (notebook, pandas and Polars pipelines, Rust) | [`examples/README.md`](examples/README.md) |
| What the match key is and when it changes | [`docs/key-format.md`](docs/key-format.md) |
| Output fields | [`docs/reso-mapping.md`](docs/reso-mapping.md), `to_usps()`, `to_display()`, `to_long()` |
| The public API surface and the decisions behind each name | [`docs/api-surface.md`](docs/api-surface.md) |
| Coming from usaddress | [`docs/usaddress-compat.md`](docs/usaddress-compat.md) |
| Sharing messy data without sharing the data (`doorplate anonymize`) | [`docs/anonymizing.md`](docs/anonymizing.md) |
| Accuracy and speed, and how to rerun them | [`docs/benchmarks.md`](docs/benchmarks.md), [`benchmarks/README.md`](benchmarks/README.md) (every benchmark and which to run) |
| The benchmark suite: what it holds and the rules that keep it fair (it is not a work list) | [`docs/benchmark-suite.md`](docs/benchmark-suite.md); data in [`benchmarks/suite/`](benchmarks/suite/README.md) |
| How the parser works | [`docs/how-it-works.md`](docs/how-it-works.md) |
| What is planned and what is not | [`docs/roadmap.md`](docs/roadmap.md); how issues are organized: [`docs/backlog.md`](docs/backlog.md) |
| Every page of documentation, by topic, and which pages to check when you change something | [`docs/README.md`](docs/README.md) |
| What data may be used and committed | [`docs/data-policy.md`](docs/data-policy.md) |

Parsing never raises on odd input: it returns a `ParsedAddress` with `warnings` (stable
snake_case codes) and the text it could not place. Only input with no address text at
all is an error. The match key is versioned (`k3:`); store the prefix with stored keys.

## Contributing

Report security problems privately ([`SECURITY.md`](SECURITY.md)); conduct is covered by
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). For everything else start with
[`CONTRIBUTING.md`](CONTRIBUTING.md): reporting a misparse, fixing a parsing bug, data
changes, and the rules for code. The golden corpus
([`tests/corpus/README.md`](tests/corpus/README.md)) is the regression suite; every
parsing bug fixed gets a case. Open issues are the backlog (organized as `docs/backlog.md` says).

**Documentation.** [`docs/README.md`](docs/README.md) indexes all the documentation by topic and has
a table of what to check when you change something. Look at it before you finish a
change: find the thing you changed in that table and update every page in its row in the
same change (a rule, a key, a warning code, an API or CLI option, a figure, the layout or
the build commands all have related pages). When you add, rename or remove a page, update
the index and the table above, and the navigation in `mkdocs.yml` when the page is in `docs/` (the documentation
site is built on Read the Docs; CI runs `pip install -r docs/requirements.txt && mkdocs build --strict`, which fails on a
broken link, a missing anchor or a page that is in `docs/` but not in the nav). The Python reference
(`docs/python-api.md`) is generated from the docstrings in `crates/doorplate-py/python/doorplate/__init__.pyi`, so a new
Python name gets a docstring there and a `:::` entry on that page, and a new CLI option gets a line in `docs/cli.md`;
`pytest tools/docs` checks both.

## Build and test

```sh
cargo fmt
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features
(cd fuzz && cargo +nightly check --bins)   # outside the workspace: check it after a change to a public type

# Python (in a virtualenv with maturin and pytest)
cd crates/doorplate-py && maturin develop --release && cd ../..
pytest crates/doorplate-py/tests
pytest tools/ingest tools/harness tools/review tools/compare   # the ingest tool (Python 3.11+), the harness, the review tool and the key comparison

# The benchmark suite (needs usaddress; the extension built with --release)
python benchmarks/suite.py all
```

**Resources.** Builds, tests, the harness, the key comparison and the data tools use all the cores and memory
the machine has. Only the benchmark suite's runner (`benchmarks/suite.py`) and a speed figure you intend to quote pin
the reference profile (4 CPUs, 8 GB; [`benchmarks/README.md`](benchmarks/README.md)).

Plain `cargo test` needs no Python. Rust 1.80 or later; the Python extension needs 1.83. CI also uploads Rust line coverage to Codecov (informational; `codecov.yml`).

## Rules that must hold

- `doorplate` stays pure Rust with no Python dependency. PyO3 lives only in `doorplate-py`.
- Never panic on input. Parsing always returns a `ParsedAddress` with diagnostics.
- Emitters read `ParsedAddress`; they never re-parse or mutate it.
- All lexicon access goes through the `Lexicons` interface. No state-specific logic in the tagger.
- The canonical key format is a public contract. A change to what an input produces
  needs a new version prefix (`k4`) and an update to `docs/key-format.md`; never edit
  `k3` in place. `k3` is cut with 0.4.0 from a closed list of rules (`docs/backlog.md`) and is frozen from there: a
  key-affecting change is a `k4`. The frozen `k2` keys the cut was measured against are in
  `local-data/keycompare/checkpoint-1819acd`.
- Every USPS or RESO rule implemented must be traceable to a source in `docs/`
  (`docs/usps-pub28-notes.md`, `docs/reso-mapping.md`).
- Private data (local exports, the [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark), the Netsyms database) stays in
  `local-data/` (git-ignored). Never commit it and never print personal names from it.
  Examples and tests use invented addresses. The full rules are in
  [`docs/data-policy.md`](docs/data-policy.md).

## Where things are

- `crates/doorplate/src/`: `clean`, `tokenize`, `tagger/`, `classify`, `assemble`,
  `lexicon`, `emit/` (`usps`, `reso`, `key`, `slug`, `usaddress`, `display`), `parser`, `anonymize`, `layer`.
- `crates/doorplate/data/`: the Pub 28 tables, the national place list and state data.
- `tests/corpus/`: the golden corpus. `examples/`: runnable examples.
- `docs/`: design notes and the sources of every rule. `tools/`: verification, fuzzing,
  corpus, comparison, the harness (`tools/harness/`, offline, private data) and the
  ingest tool that turns any address source into one record format (`tools/ingest/`; `tools/review/`, a local page where a person labels the hard rows of a run, #122; specs for
  private sources live with their data in `local-data/`; `inventory.py` there tabulates what is in `local-data/`). `site/`: the blog and the live demo, published to GitHub Pages (`site/README.md`); `crates/doorplate-wasm/`: the core compiled to WebAssembly for the demo. `benchmarks/`: speed, accuracy and size scripts, and the benchmark suite (`benchmarks/suite.py`, its data in `benchmarks/suite/v1/`, which is frozen; its generator, `tools/benchsuite/`, needs private data).
