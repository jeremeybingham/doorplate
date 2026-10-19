# The benchmark suite: data

`v1/` is the data of the benchmark suite: a fixed, versioned set of labeled US addresses. **How to run it**,
the two tracks, the strata and the resource profile are in
[`benchmarks/README.md`](../README.md#the-benchmark-suite); the specification, the sources and the rules that
keep it fair are in [`docs/benchmark-suite.md`](../../docs/benchmark-suite.md). Read the fairness rules before
using a result to decide what to change: the suite is not a work list.

This library formats and parses; it does not validate deliverability. Nothing here says an address exists or
can receive mail, and no record is a real address point.

```sh
python benchmarks/suite.py all          # from the repository root
```

## What is in `v1/`

| File | What |
|---|---|
| `compare.jsonl.gz` | The comparison track: an input string and its gold token labels, in usaddress's label set |
| `doorplate.jsonl.gz` | The doorplate-only track: the same ids, with fields input, several styles of the same record, Pub 28 components and USPS lines |
| `MANIFEST.md` | Composition counts, the build commit, checksums, the hard classes with their quotas and what was built |

The two tracks share record ids and are reported apart: no figure from the doorplate-only track appears in a
doorplate-versus-usaddress table. `v1` is never edited after it was published; label errors found later go
into `v2`.

## Rebuilding it

Maintainers only: `tools/benchsuite/build.py` needs the private data in `local-data/` (the National Address
Database as Parquet, the TIGER feature names, GeoNames postal codes) and prints its plan before it does
anything. The hand-labeled shapes are in `tools/benchsuite/hand/`.
