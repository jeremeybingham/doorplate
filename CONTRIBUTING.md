# Contributing to doorplate

Thanks for helping. The most useful contribution is usually a **misparsed address**. Please follow the [Code of Conduct](CODE_OF_CONDUCT.md); to report a security problem privately, see [`SECURITY.md`](SECURITY.md).

## Reporting a misparse

Open an issue with:

- the input exactly as you gave it (one line, or each field),
- what you expected for each component, and what `doorplate parse "<input>" --pretty`
  printed,
- the version (`python -c "import doorplate; print(doorplate.__version__)"` or the crate
  version),
- where the shape comes from, if you know (a county list, a form), so similar cases
  can be found.

Please use invented or public addresses. Do not paste personal data.

## Sharing messy data

The most valuable thing you can give this project is real, messy addresses: the kind
that come from county exports, mailing lists, forms and old databases. If a sample
parses badly, or you are not sure it parses well, open an issue (the template asks for
the right details) and attach what you can.

If the data is private, anonymize it first; an anonymized sample is just as useful as
long as it keeps the *shape* of each address:

- keep the abbreviations, punctuation, spacing, case, typos and the order of the parts;
- replace personal and business names, and house numbers, with invented ones of the same
  form (`4417` can become `1305`, `A12` can become `B27`);
- replace street and city names with other real or invented names of similar length and
  structure, but keep the words that affect parsing: suffixes (`ST`, `LN`), directionals,
  unit designators, and place names that contain suffix words (`MOUNTAIN VIEW`);
- keep the state, and a ZIP of the same state, when the parse depends on them;
- never send anything that could identify a person.

If you cannot share even that, say so in the issue and describe the shapes in words
(for example "unit written before the street, then the city cut off at 30 characters");
we can work out an anonymization together. You can also send counts: how many of your
rows come back with each warning.

## Building and testing

```sh
cargo fmt --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features

# Python (in a virtualenv with maturin and pytest; `uv venv` and `uv pip install` are fine)
cd crates/doorplate-py && maturin develop --release && cd ../..
pytest crates/doorplate-py/tests
pytest tools/ingest tools/harness tools/review   # the ingest tool (Python 3.11+), the harness and the review tool
```

Rust 1.80 or later; the Python extension needs 1.83. Plain `cargo test` needs no Python.

## Fixing a parsing bug

1. Add a case to the golden corpus (`tests/corpus/`, format in
   `tests/corpus/README.md`) that fails. Use an invented address of the same shape.
2. Fix the rule or the table. The tagger reads tables only through `Lexicons`; there
   is no state-specific logic in it.
3. Add a row to `docs/usps-pub28-notes.md` for a new parser rule, with its source: a
   Pub 28 section, or the shape you observed.
4. Run the corpus with `UPDATE_CORPUS_BASELINE=1` if more cases now pass, and commit
   `tests/corpus/passing.txt`. Run `python3 tools/corpus/emit_expect.py --check
   tests/corpus/*.jsonl`.
5. If the fix changes the key an input produces, it is a key-format change: it needs a
   new key version and an update to `docs/key-format.md`. Say so in the pull request.

## Data changes

What data may be used and committed is in [`docs/data-policy.md`](docs/data-policy.md).

Tables live in `crates/doorplate/data/`. A spelling that Pub 28 does not list goes
in an `observed` list with its evidence and raises `non_standard_abbreviation`. A
state pack addition names its evidence and is add-only (`docs/packs/fl.md`). A change
to a Pub 28 table should be checked with `tools/pub28/verify.py`.

## Package pages and READMEs

Four READMEs are shown on package pages and must not drift apart: `README.md`
(GitHub), `crates/doorplate/README.md` and `crates/doorplate-cli/README.md`
(crates.io), and `crates/doorplate-py/README.md` (PyPI). Each is selected by the
`readme` key in its `Cargo.toml` or `pyproject.toml`. If your change affects the API,
CLI options, install instructions, feature flags, minimum Rust or Python versions,
warning codes, the key format, benchmark figures, or the alpha and help-wanted
notices, update every README it touches in the same pull request. Use absolute
links in the three crate READMEs, since crates.io and PyPI do not resolve relative
ones, and keep the statement that the library does not validate deliverability and the
Disclaimer section.

## Documentation

`docs/README.md` indexes all the documentation by topic, and ends with a table of what to
check when you change something: a parse rule, a key, a warning code, the API or a CLI
option, a figure, the layout, the build commands, a version number. Before you open a pull
request, find your change in that table and update every page in its row in the same pull
request; the pull request checklist asks for it. If you add, rename or remove a page,
update the index (and the table in `AGENTS.md`) too.

## Agent instructions

`AGENTS.md` is the tool-neutral guide for AI coding agents (it is also useful as a map of
the repository); `CLAUDE.md` imports it and adds our own process for Claude Code. If your
change alters the build commands, the rules that must hold, the layout or the
documentation links, update `AGENTS.md` in the same pull request.

## Examples

New public API (a function, a method, a CLI flag or an output form) also gets an
example in `examples/` (the notebook, a pipeline script, or
`crates/doorplate/examples/` for Rust) in the same pull request. Use invented
addresses. `crates/doorplate-py/tests/test_examples.py` runs the scripts and the
notebook, so they cannot go stale silently.

## Rules for the code

- `doorplate` stays pure Rust with no Python dependency; emitters never re-parse or
  change a parse; parsing never panics.
- This library formats and parses; it does not validate deliverability. Keep docs and
  comments consistent with that.
- File names must differ by more than case: macOS and Windows file systems are case-insensitive (`done/` and `DONE` once broke CI).
- Small commits. A pull request holds a reasonable number of related changes (split unrelated work), with a short explanation of why.

## Releasing

Maintainers only. The release issue for a version (#44 for 0.3.0) is the checklist; the steps, in order:

1. **Figures.** If the parser or the tables changed since the figures were taken, rerun `benchmarks/suite.py all` (and `benchmarks/suite.py compare --suite local-data/benchsuite/twin` for the private twin), `benchmarks/accuracy.py` and the speed and size scripts, and update the figures in `docs/benchmarks.md` and in the package READMEs that quote them (`CLAUDE.md` lists the four READMEs). The suite's `v1` files are never edited; a rebuilt suite is `v2`.
2. **Checks on private data.** One full Netsyms run on the release commit, compared with the previous one (`tools/harness/README.md`), and `tools/compare/oneline_fl.py` and `tools/harness/nad_score.py` as regression checks. Ask before extracting the database or starting the run.
3. **CHANGELOG.** Rename `[Unreleased]` to the version and the date, add an empty `[Unreleased]` above it, and say when keys changed (store the key prefix, re-parse to re-key).
4. **One pull request for the references, made last.** The workspace version and the `doorplate` dependency version in `Cargo.toml` (and `Cargo.lock`, with `cargo update -w`), the "Alpha release" notice in the four READMEs, and the docs that say which version is current. Leave history alone (older CHANGELOG entries, the `k1` notes in `docs/key-format.md`). CI and the wheel builds must be green on the merge commit. Optionally start the "Benchmark suite" workflow from the Actions tab, and run "Release crates.io" (a dry run: it packages `doorplate` and stops) and "Release PyPI" (it builds the wheels and the sdist and stops) by hand first.
5. **Tag.** Tag the merge commit `vX.Y.Z`; the tag must equal the workspace version, and the crates.io job fails if it does not. Pushing a `v*` tag runs both release workflows. The `crates-io` and the `pypi` environments each need a manual approval before anything is published. crates.io gets `doorplate`, then `doorplate-cli` (the repository secret `CARGO_REGISTRY_TOKEN`); PyPI gets the abi3 wheels and the sdist through trusted publishing (no token).
6. **After.** Check the crates.io and PyPI pages and install the new version in a clean environment.

The project page is the blog in `site/` (Jekyll), built and deployed by `.github/workflows/pages.yml` on every push to `main` that changes `site/` or the parser (the live demo in `site/demo/` runs the core compiled to WebAssembly, `crates/doorplate-wasm`, which the workflow builds; Pages is enabled with the "GitHub Actions" source). A post in `site/_posts/` is published; `site/_drafts/` is not built. Posts follow the rules in [`site/README.md`](site/README.md): invented addresses, aggregate numbers only, and the statement that the library does not validate deliverability.

## License

By contributing you agree that your work is licensed under the project's terms:
MIT OR Apache-2.0, at the user's option.
