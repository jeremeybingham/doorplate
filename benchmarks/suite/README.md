# The benchmark suite

A fixed, versioned set of labeled US addresses and one runner that scores doorplate and usaddress on it
under the same modest resource profile. The specification, the sources and the rules that keep it fair are
in [docs/benchmark-suite.md](../../docs/benchmark-suite.md); read the fairness rules before using a result
to decide what to change: the suite is not a work list.

This library formats and parses; it does not validate deliverability. Nothing here says an address exists
or can receive mail, and no record is a real address point.

## Run it

```sh
cargo build --release -p doorplate-cli        # not needed; the runner uses the Python extension
python -m venv .venv && . .venv/bin/activate
pip install maturin usaddress
(cd crates/doorplate-py && maturin develop --release)

python benchmarks/suite.py all --out suite-report.md       # every track, about a minute
python benchmarks/suite.py compare                          # the comparison track only
python benchmarks/suite.py doorplate                        # the doorplate-only track only
python benchmarks/suite.py speed                            # speed and peak memory
```

`--suite DIR` scores another version (a rebuilt copy, or the private twin), `--limit N` runs the first N
records (a quick test), `--min-group N` changes the smallest group a breakdown prints.

## The resource profile

The reference profile is **4 logical CPUs and 8 GB of memory, on Linux**, which a GitHub-hosted
`ubuntu-latest` runner on a public repository and an ordinary laptop both match. The runner applies it
itself: it pins the CPU affinity to 4 CPUs, sets `RAYON_NUM_THREADS=4` and an 8 GB address-space limit
(`RLIMIT_AS`), and its header prints what it got. Speed is reported on 1 thread and on 4, never on all
cores, and the speed figures lead with ratios. Accuracy does not depend on the profile.

On macOS and Windows, run it in Docker: `docker run --cpus=4 --memory=8g ...`. A `workflow_dispatch` job
(`.github/workflows/suite.yml`) runs it on a real runner.

## What is in `v1/`

| File | What |
|---|---|
| `compare.jsonl.gz` | The comparison track: an input string and its gold token labels, in usaddress's label set |
| `doorplate.jsonl.gz` | The doorplate-only track: the same ids, with fields input, several styles of the same record, Pub 28 components and USPS lines |
| `MANIFEST.md` | Composition counts, the build commit, checksums, the hard classes with their quotas and what was built |

The two tracks share record ids and are reported apart: no figure from the doorplate-only track appears
in a doorplate-versus-usaddress table.

## Rebuilding it

Maintainers only: `tools/benchsuite/build.py` needs the private data in `local-data/` (the National
Address Database as Parquet, the TIGER feature names, GeoNames postal codes) and prints its plan before it
does anything. `v1` is never edited after it is published; label errors found later go into `v2`.
