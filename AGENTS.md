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
| Coming from usaddress | [`docs/usaddress-compat.md`](docs/usaddress-compat.md) |
| Accuracy and speed, and how to rerun them | [`docs/benchmarks.md`](docs/benchmarks.md), [`benchmarks/README.md`](benchmarks/README.md) |
| How the parser works | [`docs/how-it-works.md`](docs/how-it-works.md) |
| What is planned and what is not | [`docs/roadmap.md`](docs/roadmap.md) |

Parsing never raises on odd input: it returns a `ParsedAddress` with `warnings` (stable
snake_case codes) and the text it could not place. Only input with no address text at
all is an error. The match key is versioned (`k1:`); store the prefix with stored keys.

## Contributing

Report security problems privately ([`SECURITY.md`](SECURITY.md)); conduct is covered by
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). For everything else start with
[`CONTRIBUTING.md`](CONTRIBUTING.md): reporting a misparse, fixing a parsing bug, data
changes, and the rules for code. The golden corpus
([`tests/corpus/README.md`](tests/corpus/README.md)) is the regression suite; every
parsing bug fixed gets a case. Open issues are the backlog.

## Build and test

```sh
cargo fmt
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features

# Python (in a virtualenv with maturin and pytest)
cd crates/doorplate-py && maturin develop --release && cd ../..
pytest crates/doorplate-py/tests
```

Plain `cargo test` needs no Python. Rust 1.80 or later; the Python extension needs 1.83.

## Rules that must hold

- `doorplate` stays pure Rust with no Python dependency. PyO3 lives only in `doorplate-py`.
- Never panic on input. Parsing always returns a `ParsedAddress` with diagnostics.
- Emitters read `ParsedAddress`; they never re-parse or mutate it.
- All lexicon access goes through the `Lexicons` interface. No state-specific logic in the tagger.
- The canonical key format is a public contract. A change to what an input produces
  needs a new version prefix (`k2`) and an update to `docs/key-format.md`; never edit
  `k1` in place.
- Every USPS or RESO rule implemented must be traceable to a source in `docs/`
  (`docs/usps-pub28-notes.md`, `docs/reso-mapping.md`).
- Private data (local exports, the geocode benchmark) stays in `local-data/`
  (git-ignored). Never commit it and never print personal names from it. Examples and
  tests use invented addresses.

## Where things are

- `crates/doorplate/src/`: `clean`, `tokenize`, `tagger/`, `classify`, `assemble`,
  `lexicon`, `emit/` (`usps`, `reso`, `key`, `slug`, `usaddress`, `display`), `parser`.
- `crates/doorplate/data/`: the Pub 28 tables, the national place list and state packs.
- `tests/corpus/`: the golden corpus. `examples/`: runnable examples.
- `docs/`: design notes and the sources of every rule. `tools/`: verification, fuzzing,
  corpus and comparison scripts. `benchmarks/`: speed, accuracy and size scripts.
