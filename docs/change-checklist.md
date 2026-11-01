# When you change something, check these

A page that describes the thing you changed is out of date the moment you change it.
Look at this table before you open a pull request, and update every page in the row in
the same pull request. The pull request template asks for it.

| You change | Check |
|---|---|
| A parse rule or a table in `crates/doorplate/data/` | [`usps-pub28-notes.md`](usps-pub28-notes.md) (a row with its source); a golden-corpus case and `passing.txt`; [`how-it-works.md`](how-it-works.md) if the behavior it describes changed; [`CHANGELOG.md`](../CHANGELOG.md). If an input's key changes, the key row below |
| What an input's key is | [`key-format.md`](key-format.md) (a new version, never an edit in place); `tests/corpus/keys.jsonl` and `tools/corpus/emit_expect.py`; the four READMEs; [`how-it-works.md`](how-it-works.md); [`CHANGELOG.md`](../CHANGELOG.md) |
| A warning code | [`how-it-works.md`](how-it-works.md) (the list); [`warnings.md`](warnings.md) (the meaning and the measured rate; regenerate with `label_score.py --by-warning`); the four READMEs; the stubs in `crates/doorplate-py/python/doorplate/__init__.pyi` |
| The API, a CLI flag or an output form (a function, a method, a field, a column) | The four READMEs and the guides ([`python.md`](python.md), [`command-line.md`](command-line.md), [`rust.md`](rust.md), [`dataframes.md`](dataframes.md)); an example in `examples/` ([`examples/README.md`](../examples/README.md)); [`how-it-works.md`](how-it-works.md); [`usaddress-compat.md`](usaddress-compat.md) (its feature table); [`reso-mapping.md`](reso-mapping.md) if RESO output changed; [`CHANGELOG.md`](../CHANGELOG.md) |
| The custom layer (its files, rules, loader or provenance) | [`custom-layers.md`](custom-layers.md) (and its LLM prompt, kept in step with the loader by `test_custom_layer.py`); `examples/layers/` (the demo and the template: `doorplate layer check` both) and the notebook section; [`key-format.md`](key-format.md) ("Stability"); [`how-it-works.md`](how-it-works.md) ("Lexicon layers"); [`api-surface.md`](api-surface.md); the four READMEs once the CLI and Python take a layer; [`CHANGELOG.md`](../CHANGELOG.md) |
| The anonymizer (what it changes or keeps, its options, the faithfulness check, the measured rates) | [`anonymizing.md`](anonymizing.md); [`CONTRIBUTING.md`](../CONTRIBUTING.md) ("Sharing messy data"); the issue template; the CLI and Python READMEs; `examples/anonymize_example.py` and the notebook section; [`api-surface.md`](api-surface.md); [`data-policy.md`](data-policy.md) if what may be shared changes |
| A Python function, method or property (its signature or what it does) | The docstring in [`__init__.pyi`](../crates/doorplate-py/python/doorplate/__init__.pyi) (the source of [`python-api.md`](python-api.md); `tools/docs` tests that every public name has one) and the Rust doc comment in `src/lib.rs` |
| A CLI command or option | The `USAGE` text in `crates/doorplate-cli/src/main.rs` and [`cli.md`](cli.md) (`tools/docs` tests that every option is described); the CLI README |
| The demo page or its CSV section (`site/demo/`, `crates/doorplate-wasm`) | [`site/README.md`](../site/README.md); the privacy text on the page and in [`command-line.md`](command-line.md) (it must stay true: no third-party scripts, nothing uploaded); `tools/docs/test_demo_csv.py` (Node; run in CI) and `tools/docs/smoke_demo_csv.py` (a headless browser; run by hand after a change to the page); the columns come from `json::COLUMNS`, shared with `parse-file` |
| A page added, renamed or removed in `docs/` | This index; the `nav` in [`mkdocs.yml`](../mkdocs.yml) (CI builds the site with `mkdocs build --strict`); the table in [`AGENTS.md`](../AGENTS.md) |
| Output labels in usaddress's shape (`tag`, `parse_tokens`, `doorplate.compat`) | [`usaddress-compat.md`](usaddress-compat.md); the Python and root READMEs' "Coming from usaddress"; `examples/usaddress_migration.py` |
| The RESO output | [`reso-mapping.md`](reso-mapping.md) (the table and the choices) and `tests/corpus/reso.jsonl` |
| Accuracy or speed figures, or the benchmark scripts | [`benchmarks.md`](benchmarks.md); [`docs/running-benchmarks.md`](running-benchmarks.md); the figures in the four READMEs that quote them; [`CHANGELOG.md`](../CHANGELOG.md). The suite's `v1` files are never edited: a fix is a `v2` |
| The benchmark suite (its generator, scoring or composition) | [`benchmark-suite.md`](benchmark-suite.md); [`docs/running-benchmarks.md`](running-benchmarks.md); [`benchmarks/suite/README.md`](../benchmarks/suite/README.md); [`benchmarks.md`](benchmarks.md) |
| Place data or state data | [`places.md`](places.md) or [`states/fl.md`](states/fl.md); [`data-policy.md`](data-policy.md); [`NOTICE`](../NOTICE) when a source needs credit; [`how-it-works.md`](how-it-works.md) (the lexicon layers) |
| How private data is used, or what leaves `local-data/` | [`data-policy.md`](data-policy.md); [`docs/tools/harness.md`](tools/harness.md); [`docs/tools/ingest.md`](tools/ingest.md); [`docs/tools/review.md`](tools/review.md) |
| The golden corpus format or the way it runs | [`docs/tests/corpus.md`](tests/corpus.md); [`repository.md`](repository.md) ("Testing") |
| Build commands, the repository layout, the CI jobs or the release steps | [`AGENTS.md`](../AGENTS.md); [`CLAUDE.md`](../CLAUDE.md); [`CONTRIBUTING.md`](../CONTRIBUTING.md); [`repository.md`](repository.md) ("Repository layout" and "Testing") |
| A version number, the alpha notice or the disclaimer | The four READMEs; `Cargo.toml`; [`CHANGELOG.md`](../CHANGELOG.md); the references pull request in [`CONTRIBUTING.md`](../CONTRIBUTING.md) ("Releasing") |
| A batch of issues closes, an issue is filed, or a release is cut | [`roadmap.md`](roadmap.md) ("Released", "Next", the lists, "Last reviewed"); [`backlog.md`](backlog.md) (the milestone table, the labels, "Last reviewed"); the boxes of the release trackers; the label descriptions on GitHub; every open issue has a milestone and its labels; then `python tools/docs/issue_states.py` |
| Adding, renaming or removing a documentation page | The index ([`README.md`](https://github.com/jeremeybingham/doorplate/blob/main/docs/README.md)); the `nav` in [`mkdocs.yml`](../mkdocs.yml); the "Using the library" table in [`AGENTS.md`](../AGENTS.md) |

The four READMEs are the project README and the three package pages (PyPI, crates.io
for the library, crates.io for the command). They are published as they are, so their
links are absolute in the three crate READMEs, and each keeps the statement that the
library does not validate deliverability and the Disclaimer section ([`CONTRIBUTING.md`](../CONTRIBUTING.md),
"Package pages and READMEs").
