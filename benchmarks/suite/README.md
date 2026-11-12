# The benchmark suite: data

`v1/` holds the records (`compare.jsonl.gz`, `doorplate.jsonl.gz`, `MANIFEST.md` with counts and checksums), and `v2/` holds
a scoring file that reuses them. Run it with `python benchmarks/suite.py all` from the repository root
([how to run it](../../docs/running-benchmarks.md#the-benchmark-suite)); the specification and the fairness rules are in
[`docs/benchmark-suite.md`](../../docs/benchmark-suite.md). A published version is never edited.

Rebuilding (maintainers only): `tools/benchsuite/build.py` reads the private data in `local-data/` and prints its plan first.
