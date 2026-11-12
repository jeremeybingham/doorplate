# When you change something, check these

A page that describes the thing you changed is out of date the moment you change it.
Look at this table before you open a pull request, and update every page in the row in
the same pull request. The pull request template asks for it.

| You change | Check |
|---|---|
| A parse rule or a table in `crates/doorplate/data/` | [`usps-pub28-notes.md`](usps-pub28-notes.md) (a row with its source); a corpus case and `passing.txt`; [`how-it-works.md`](how-it-works.md); [`CHANGELOG.md`](../CHANGELOG.md); the key row if a key changes |
| What an input's key is | [`key-format.md`](key-format.md) (a new version, never an edit in place); `tests/corpus/keys.jsonl`, `tools/corpus/emit_expect.py`; the four READMEs; [`how-it-works.md`](how-it-works.md); [`CHANGELOG.md`](../CHANGELOG.md) |
| A warning code | [`warnings.md`](warnings.md) (meaning and measured rate; `label_score.py --by-warning`); [`how-it-works.md`](how-it-works.md) (the list); the four READMEs; `__init__.pyi` |
| The API, a CLI flag or an output form | The four READMEs and the guides ([`python.md`](python.md), [`command-line.md`](command-line.md), [`rust.md`](rust.md), [`dataframes.md`](dataframes.md)); an example in `examples/`; [`api-surface.md`](api-surface.md); [`usaddress-compat.md`](usaddress-compat.md) (feature table); [`reso-mapping.md`](reso-mapping.md) if RESO output changed; [`CHANGELOG.md`](../CHANGELOG.md) |
| The custom layer (files, rules, loader, provenance) | [`custom-layers.md`](custom-layers.md) (its LLM prompt is checked by `test_custom_layer.py`); `examples/layers/` (`doorplate layer check` both) and the notebook; [`key-format.md`](key-format.md) ("Stability"); [`how-it-works.md`](how-it-works.md) ("Lexicon layers"); the four READMEs; [`CHANGELOG.md`](../CHANGELOG.md) |
| The anonymizer (what it changes or keeps, options, the faithfulness check) | [`anonymizing.md`](anonymizing.md); [`CONTRIBUTING.md`](../CONTRIBUTING.md) ("Sharing messy data"); the issue template; the CLI and Python READMEs; `examples/anonymize_example.py` and the notebook; [`data-policy.md`](data-policy.md) if what may be shared changes |
| A Python function, method or property | Its docstring in [`__init__.pyi`](../crates/doorplate-py/python/doorplate/__init__.pyi) (the source of [`python-api.md`](python-api.md); `tools/docs` tests every public name) and the Rust doc comment in `src/lib.rs` |
| A CLI command or option | The `USAGE` text in `crates/doorplate-cli/src/main.rs` and [`cli.md`](cli.md) (`tools/docs` tests every option); the CLI README |
| The demo page or its CSV section (`site/demo/`, `crates/doorplate-wasm`) | [`site/README.md`](../site/README.md); the privacy text on the page and in [`command-line.md`](command-line.md) (no third-party scripts, nothing uploaded); `tools/docs/test_demo_csv.py` (CI) and `smoke_demo_csv.py` (by hand); the sample CSV is written by `tools/docs/make_sample_csv.py` (change the generator, not the file); `json::COLUMNS` is shared with `parse-file` |
| A page added, renamed or removed in `docs/` | The index ([`README.md`](https://github.com/jeremeybingham/doorplate/blob/main/docs/README.md)); the `nav` in [`mkdocs.yml`](../mkdocs.yml) (CI builds the site with `mkdocs build --strict`); the table in [`AGENTS.md`](../AGENTS.md); grep for the old path and its section names |
| Output labels in usaddress's shape (`tag`, `parse_tokens`, `doorplate.compat`) | [`usaddress-compat.md`](usaddress-compat.md); the Python and root READMEs' "Coming from usaddress"; `examples/usaddress_migration.py` |
| The output fields (components, key, warnings) or a comparison with libpostal (what libpostal's labels map to, the Senzing model, the measured figures) | [`libpostal-compat.md`](libpostal-compat.md) (the mapping table lists doorplate's field names; the figures, once measured, go in [`benchmarks.md`](benchmarks.md) and [`speed-and-size.md`](speed-and-size.md)) |
| The RESO output | [`reso-mapping.md`](reso-mapping.md) (the table and the choices) and `tests/corpus/reso.jsonl` |
| Accuracy or speed figures, or the benchmark scripts | [`benchmarks.md`](benchmarks.md) and [`speed-and-size.md`](speed-and-size.md); [`running-benchmarks.md`](running-benchmarks.md); the READMEs that quote them; [`CHANGELOG.md`](../CHANGELOG.md). The suite's `v1` files are never edited: a fix is a `v2` |
| A release, or a change that moves a geocode or fastaddress figure | The release tolerance below; the per-build table and "Reading the figures across versions" in [`benchmarks.md`](benchmarks.md#reading-the-figures-across-versions) (a new build is a new column) |
| The benchmark suite (its generator, scoring or composition) | [`benchmark-suite.md`](benchmark-suite.md); [`docs/running-benchmarks.md`](running-benchmarks.md); [`benchmarks/suite/README.md`](../benchmarks/suite/README.md); [`benchmarks.md`](benchmarks.md) |
| Place data or state data | [`places.md`](places.md) or [`states/fl.md`](states/fl.md); [`data-policy.md`](data-policy.md); [`NOTICE`](../NOTICE) when a source needs credit; [`how-it-works.md`](how-it-works.md) (the lexicon layers) |
| How private data is used, or what leaves `local-data/` | [`data-policy.md`](data-policy.md); [`docs/tools/harness.md`](tools/harness.md); [`docs/tools/ingest.md`](tools/ingest.md); [`docs/tools/review.md`](tools/review.md) |
| The golden corpus format or the way it runs | [`docs/tests/corpus.md`](tests/corpus.md); [`repository.md`](repository.md) ("Testing") |
| Build commands, the repository layout, the CI jobs or the release steps | [`AGENTS.md`](../AGENTS.md); [`CLAUDE.md`](../CLAUDE.md); [`CONTRIBUTING.md`](../CONTRIBUTING.md); [`repository.md`](repository.md) ("Repository layout" and "Testing") |
| A version number, the alpha notice or the disclaimer | The four READMEs; `Cargo.toml`; [`CHANGELOG.md`](../CHANGELOG.md); the references pull request in [`CONTRIBUTING.md`](../CONTRIBUTING.md) ("Releasing") |
| A batch of issues closes, an issue is filed, or a release is cut | [`roadmap.md`](roadmap.md) ("Next", the lists, "Last reviewed"); [`backlog.md`](backlog.md); the boxes of the trackers; every open issue has a milestone and labels; then `python tools/docs/issue_states.py`. A new `area:rules` issue also gets a probe in [`tools/harness/probes.py`](../tools/harness/probes.py) or a reason in `NO_PROBE` (`probes.py --coverage` must exit 0) |

The four READMEs are the project README and the three package pages. Links in the three crate READMEs are absolute, and each keeps the
not-a-validator statement and the Disclaimer section ([`CONTRIBUTING.md`](../CONTRIBUTING.md), "Package pages and READMEs").

## Release tolerance for the benchmarks

The runs are deterministic, so this is a policy, not a noise margin. Before a release:

1. List the strings that changed on the geocode `dev` and `test` splits and on the five fastaddress files between the last release and the candidate.
2. Attribute each lost string to the pull request that made it (the bisect method is in [`tools/harness.md`](tools/harness.md)).
3. **The release is blocked** if geocode `dev` loses more than **60 strings net** (0.1 point of 60,522) that are not attributed to a decided convention or a
   recorded trade-off, or if **any** fastaddress `clean` string is lost without an attribution.

60 catches one rule's loss of the size seen so far (single-cause classes run from 15 to 143 strings) and lets smaller ones through to be attributed.
Decided conventions are not argued again: a letter A to D after the house number is a unit, compass heads of a listed city, building names, `EXT` and
`BUS` ([`usaddress-compat.md`](usaddress-compat.md#label-conventions)).
