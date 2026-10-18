# CLAUDE.md

@AGENTS.md

Rust-core US address parser (`doorplate`) with a PyO3 Python wrapper. Read
`docs/how-it-works.md` first. The rules that must hold (pure Rust core, never panic,
emitters do not re-parse, the key contract, sources for every rule, private data) and the
build commands are in `AGENTS.md`, imported above; this file holds the process we follow
when working on the project with Claude Code.

## Workflow
- Before finishing a task run `cargo fmt`, `cargo clippy --workspace --all-targets --all-features -- -D warnings` and `cargo test --workspace --all-features`.
- Add a golden-corpus case for every parsing bug fixed (format: `tests/corpus/README.md`). When a change makes more cases pass, rerun the corpus test with `UPDATE_CORPUS_BASELINE=1` and commit `tests/corpus/passing.txt`.
- Parse-rule changes also need a row in `docs/usps-pub28-notes.md` (its source, even when the source is data rather than USPS). Re-run `python3 tools/corpus/emit_expect.py --check tests/corpus/*.jsonl` after changing a rule the corpus emitters follow.
- After changing a table in `crates/doorplate/data/`, run `python3 tools/pub28/verify.py --cache DIR --fetch --emitter` (needs the built Python extension) to compare with the live Pub 28 pages.
- Python: in `crates/doorplate-py`, `maturin develop`, then `pytest crates/doorplate-py/tests`.
- Private data (local exports, the geocode benchmark) stays in `local-data/` (git-ignored); never commit it, and never print personal names from it.
- Four READMEs are published as package pages and must stay in sync with the code and each other: `README.md` (GitHub), `crates/doorplate/README.md` (crates.io), `crates/doorplate-cli/README.md` (crates.io) and `crates/doorplate-py/README.md` (PyPI). When a change touches the API, CLI options, install steps, features, MSRV or Python versions, warning codes, the key format, accuracy figures, or the alpha/help-wanted notices, update every README it affects in the same change. Keep links in the three crate READMEs absolute (crates.io and PyPI do not resolve relative links) and keep the not-a-validator statement in all four.
- New public API (a function, a method, a CLI flag or an output form) also gets an example in `examples/` (the notebook, a pipeline script or `crates/doorplate/examples/`) in the same change; `crates/doorplate-py/tests/test_examples.py` runs them.
- `AGENTS.md` is the tool-neutral guide for agents and contributors. Keep it in step with the code and with this file: when the build commands, the rules that must hold, the layout or the documentation links change, update `AGENTS.md` in the same change, and keep its links relative to the repository root.
- Keep small commits. A pull request holds a reasonable number of related changes; split unrelated work into separate pull requests.
