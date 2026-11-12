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

If the data is private, anonymize it first. `doorplate anonymize` (or `doorplate.Anonymizer` in Python) replaces digits, names and unknown
words with others of the same length and case and keeps suffixes, directionals, unit designators, state, city and the first three ZIP digits.
**It is obfuscation that keeps the shape, not anonymity**: read the output before you send it, and drop what still identifies someone
([`docs/anonymizing.md`](docs/anonymizing.md) says what it keeps and what it can leak). By hand, the same rules apply; an anonymized sample is just
as useful as long as it keeps the *shape* of each address:

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

The commands (`cargo fmt`, `clippy`, `cargo test`, `maturin develop` and `pytest`) are in [`AGENTS.md`](AGENTS.md#build-and-test). Rust 1.80 or
later; the Python extension needs 1.83. Plain `cargo test` needs no Python. Only the benchmark suite's runner pins a reference profile
(4 CPUs, 8 GB; [`docs/running-benchmarks.md`](docs/running-benchmarks.md)). Codecov line coverage is informational: a map of code the tests do not reach, not a gate.

## Fixing a parsing bug

1. Add a case to the golden corpus (`tests/corpus/`, format in
   `docs/tests/corpus.md`) that fails. Use an invented address of the same shape.
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
state-data addition names its evidence and is add-only (`docs/states/fl.md`). A change
to a Pub 28 table should be checked with `tools/pub28/verify.py`.

## Package pages and READMEs

Four READMEs are shown on package pages and must not drift apart: `README.md` (GitHub), `crates/doorplate/README.md` and
`crates/doorplate-cli/README.md` (crates.io), and `crates/doorplate-py/README.md` (PyPI). If your change affects the API, CLI options, install
steps, features, minimum Rust or Python versions, warning codes, the key format, figures, or the alpha and help-wanted notices, update every README it
touches in the same pull request. Links in the three crate READMEs are absolute (crates.io and PyPI do not resolve relative ones), and each keeps the
Disclaimer section. They are short on purpose: the detail lives in the tours in
`docs/`, and a README keeps its install lines, a quickstart and a two-row headline of figures copied from [`docs/benchmarks.md`](docs/benchmarks.md).

## Documentation

Find your change in [`docs/change-checklist.md`](docs/change-checklist.md) and update every page in its row in the same pull request;
[`docs/README.md`](docs/README.md) indexes all the pages. Adding, renaming or removing a page also updates the index, the table in `AGENTS.md` and the
`nav` in `mkdocs.yml`. Check the site with `pip install -r docs/requirements.txt && mkdocs build --strict` (it fails on a broken link, a missing anchor
or a page missing from the nav; write links to files outside `docs/` as ordinary relative links, `tools/docs/links.py` rewrites them).
New public API also gets an example in `examples/` (the notebook, a pipeline script or `crates/doorplate/examples/`), run by
`crates/doorplate-py/tests/test_examples.py`. If your change alters the build commands, the rules that must hold, the layout or the documentation
links, update [`AGENTS.md`](AGENTS.md) (the tool-neutral agent guide; `CLAUDE.md` imports it) in the same pull request.

**Writing docs.** Keep pages short. Each fact lives on one page and the others link to it (figures: `benchmarks.md` and `speed-and-size.md`; warnings:
`warnings.md`; label conventions: `usaddress-compat.md`; rule sources: `usps-pub28-notes.md`; data rules: `data-policy.md`). Start a page with the
answer, not a description of the page. Leave build history, commit hashes and "decided on DATE" to `CHANGELOG.md`, the issues and git; give figures
one line, `Figures: 0.6.0 (abc1234), measured 2026-11-NN.` Name an issue only where a reader would follow it (an open issue, or the source of a rule).
Use invented examples only.

## Rules for the code

- `doorplate` stays pure Rust with no Python dependency; emitters never re-parse or
  change a parse; parsing never panics.
- This library formats and parses; it does not validate deliverability. Keep docs and
  comments consistent with that.
- File names must differ by more than case: macOS and Windows file systems are case-insensitive (`done/` and `DONE` once broke CI).
- Small commits. A pull request holds a reasonable number of related changes (split unrelated work), with a short explanation of why.

## Releasing

Maintainers only. The release issue for a version is the checklist. A 0.5.x patch is cut from `release/0.5.x`, not from `main` (which carries the unreleased key changes): cherry-pick the fix there, run the steps below, and port the CHANGELOG entry back to `main`. In order:

1. **Figures.** If the parser or the tables changed since the figures were taken, rerun `benchmarks/suite.py all` (and `benchmarks/suite.py compare --suite local-data/benchsuite/twin` for the private twin), `benchmarks/accuracy.py` and the speed and size scripts, and update the figures in `docs/benchmarks.md`, `docs/speed-and-size.md` and the READMEs that quote them. The suite's `v1` files are never edited; a rebuilt suite is `v2`.
2. **Checks on private data.** One full Netsyms run on the release commit, compared with the previous one (`docs/tools/harness.md`), and `tools/compare/oneline_fl.py` and `tools/harness/nad_score.py` as regression checks. Ask before extracting the database or starting the run.
3. **CHANGELOG.** Rename `[Unreleased]` to the version and the date, add an empty `[Unreleased]` above it, and say when keys changed (store the key prefix, re-parse to re-key). Bring `docs/roadmap.md` and `docs/backlog.md` up to date in the same pull request and tick the tracker (`docs/backlog.md`, "Keeping it current"); `python tools/docs/issue_states.py` shows what no longer fits.
4. **One pull request for the references, made last.** The workspace version and the `doorplate` dependency version in `Cargo.toml` (and `Cargo.lock`, with `cargo update -w`; `main` carries a `-dev` suffix until this pull request sets the release version, which the tag must equal), the "Alpha release" notice in the four READMEs, and the docs that say which version is current. Leave history alone (older CHANGELOG entries, the version table in `docs/key-format.md`). CI and the wheel builds must be green on the merge commit. Run "Release crates.io" and "Release PyPI" by hand first as dry runs (they package and stop).
5. **Tag.** Tag the merge commit `vX.Y.Z`; the tag must equal the workspace version, and the crates.io job fails if it does not. Pushing a `v*` tag runs both release workflows. The `crates-io` and the `pypi` environments each need a manual approval before anything is published. crates.io gets `doorplate`, then `doorplate-cli` (the repository secret `CARGO_REGISTRY_TOKEN`); PyPI gets the abi3 wheels and the sdist through trusted publishing (no token).
6. **After.** Check the crates.io and PyPI pages and install the new version in a clean environment. Then the documentation site: activate the new tag's version on Read the Docs, check that `stable` builds, and change the opening of `docs/python-api.md`, which says it describes `main`, to say it describes the release.

The project page is the blog in `site/` (Jekyll), built and deployed by `.github/workflows/pages.yml` on every push to `main` that changes `site/` or the parser (the live demo in `site/demo/` runs the core compiled to WebAssembly, `crates/doorplate-wasm`, which the workflow builds; Pages is enabled with the "GitHub Actions" source). A post in `site/_posts/` is published; `site/_drafts/` is not built. Posts follow the rules in [`site/README.md`](site/README.md): invented addresses and aggregate numbers only.

## License

By contributing you agree that your work is licensed under the project's terms:
MIT OR Apache-2.0, at the user's option.
