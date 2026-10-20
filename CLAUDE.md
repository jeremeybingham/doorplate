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
- `docs/README.md` indexes all the documentation by topic and has a table "When you change something, check these". Before finishing any change, find it in that table and update every related page in the same change; when you add, rename or remove a page, update the index. A change that touches a rule, a key, a warning code, the API, a figure or the layout almost always has related pages.
- `AGENTS.md` is the tool-neutral guide for agents and contributors. Keep it in step with the code and with this file: when the build commands, the rules that must hold, the layout or the documentation links change, update `AGENTS.md` in the same change, and keep its links relative to the repository root.
- Ask before any major process: extracting the Netsyms archive, a full Netsyms run, a download, or anything that runs over about a minute or writes over about 1 GB. The harness scripts (`tools/netsyms/`) print a plan and need `--confirm`; show the plan and wait for a go-ahead. Small checks (tests, the 12-second sample comparison, read-only counts) need no approval.
- For each parse-rule PR: the tests above plus a before/after comparison on `local-data/netsyms-2026/sample.sqlite` with `tools/netsyms/compare.py`. Full Netsyms runs happen once after a batch of rules and on the release commit.
- Rebuild the extension (`maturin develop --release`) after every Rust change.
- A parse-rule PR also runs the sample comparison and, for a rule on one-line input, the checks in `benchmarks/README.md` (`tools/compare/city_diff.py` and `tools/compare/oneline_fl.py`): a rule tuned on the geocode benchmark alone once broke spelled-out postdirectionals. The loop is in `tools/netsyms/README.md`.
- Keep it simple: there are no users yet, so no compatibility shims or migration tooling. Summarize decisions and next steps when asked, and do not start new work until the owner says so.
- Keep small commits. A pull request holds a reasonable number of related changes; split unrelated work into separate pull requests.

## Local notes

This machine's shell, tools and data (the shell, `uv`, a `gh` workaround, where the private data is) are in
`local-data/SESSION.md`. It is git-ignored, so a fresh clone does not have it; the rules above do not depend on it.

@local-data/SESSION.md
