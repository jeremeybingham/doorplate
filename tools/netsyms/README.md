# Netsyms harness

Parses address sources with doorplate (the US rows of the Netsyms database, or any source
turned into records by `tools/ingest/`) and keeps artifacts for analysis later, in a fresh
session if need be. Everything runs offline; the database and
every artifact live in the git-ignored `local-data/`. Read `docs/data-policy.md` first: only
aggregate numbers leave `local-data/`, and nothing is committed from it.

| Script | Does |
|---|---|
| `run.py` | Prints a plan; with `--confirm` parses the rows in chunks and writes a run directory. `--input` reads a `records.parquet` (any source, in row-offset chunks); `--db` reads the Netsyms SQLite directly |
| `analyze.py` | Summarizes a finished run: totals, warning codes, states, roles, last-line rows, providers, place gaps |
| `compare.py` | Compares two runs (before and after a rule change): totals, warning codes, states |
| `test_run.py` | Tests on invented rows (`pytest tools/netsyms`) |
| `SCHEMA.md` | The artifacts' columns and the comparison rules (copied into every run) |

## Safe by default

`run.py` without `--confirm` only prints the plan (database, rowid range, chunks, run
directory, disk used and budget, commit) and exits. Start with the small sample:

```sh
pip install "doorplate[duckdb]"        # DuckDB and PyArrow, for the artifacts and analysis
python tools/netsyms/run.py --db local-data/netsyms-2026/sample.sqlite --table sample              # plan
python tools/netsyms/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --confirm    # run
python tools/netsyms/analyze.py <run-id>
```

Any other source goes through `tools/ingest/` first, then `--input`. The checks run only on
the fields a role has, rows with a `last_line` are parsed as one joined string and counted
apart (`last_line_rows`, `last_line_crossed`; #93 option A), and the artifacts are broken down
by `source`, `role` and `provider`:

```sh
python tools/ingest/ingest.py tools/ingest/specs/netsyms.toml --confirm
python tools/netsyms/run.py --input local-data/netsyms-2026/records.parquet --confirm
```

On the sample, a run from the Netsyms records and a direct `--db` run give the same totals,
warning codes and per-state counts (`compare.py` shows no change).

The full run (after the archive is extracted, which needs a separate go-ahead):

```sh
nohup python tools/netsyms/run.py --db local-data/netsyms-2026/<extracted>.sqlite \
    --table addresses --confirm > local-data/netsyms-runs/run.out 2>&1 &
tail -f local-data/netsyms-runs/*/progress.log
```

## Limits

- `--budget-gb` (default 60): the run stops cleanly when the database's folder (not counting
  `.7z` archives) plus all runs exceed it. Finished chunks are kept; repeat the command with `--run-id <id>` to resume.
- `--min-free-gb` (default 20): refuses to start below this much free disk.
- `--threads N`: caps the Rust parse threads.
- A run is resumable at any point: a chunk counts as finished only when its `chunk_status/` marker
  exists, and every file is written under a temporary name and renamed.

## For a new session

Open the run directory and read `README_RUN.md`, `manifest.json` and `SCHEMA.md`. Check that
`DONE` exists. Then run `analyze.py` or query the Parquet files with DuckDB. The manifest names
the commit, doorplate version, data-table hash and the input fingerprint the run used.

## After a rule change

Rerun the harness on the same database (a new run id), then `python tools/netsyms/compare.py <before> <after>`. The report lists how the totals, warning codes and per-state flagged counts moved, and warns when the two runs are not like for like (a different schema version, input or chunk size). Schema version 2 changed the `street` rule, so compare version-2 runs with each other.

## A rule PR, step by step

1. Environment (once): `uv venv venv`, activate it, `uv pip install maturin pytest usaddress pandas polars duckdb pyarrow nbclient nbformat ipykernel`, then `maturin develop --release` in `crates/doorplate-py`. Rebuild after every Rust change.
2. Change the rule. Add corpus cases with invented addresses (`tests/corpus/README.md`); `tools/corpus/emit_expect.py` fills the emitter expectations from the spec, so teach it any change to the key. Add a row to `docs/usps-pub28-notes.md`. Rerun the corpus test with `UPDATE_CORPUS_BASELINE=1` and commit `tests/corpus/passing.txt`.
3. Compare on the sample (about 2 to 3 minutes a run): `python tools/netsyms/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id NAME --confirm`, then `python tools/netsyms/compare.py BEFORE NAME`. Keep the previous run as BEFORE; old `sample-*` runs can be deleted. The comparison catches side effects the corpus does not (a designator rule once turned `FRONT ST` into a unit).
4. The `flagged/` Parquet files of a run keep each row's key and parsed components, so DuckDB can diff two runs row by row (rows whose key changed, new `unparsed_remainder` rows). Look at shapes (letters `a`, digits `9`) and counts, never at street names (`docs/data-policy.md`).
5. For a rule on one-line input, also run `tools/compare/city_diff.py` on the geocode splits and `tools/compare/oneline_fl.py` (`benchmarks/README.md`).
6. Full Netsyms runs (about 20 minutes) only after a batch of rules and on the release commit. Ask before any extraction, full run or download.

## The NAD scorecard (`nad_score.py`)

The National Address Database labels the parts of each address (`docs/data-policy.md`), which the
Netsyms rows do not. `nad_score.py` draws a random 1,000,000-row sample of the NAD text file (one
pass, about 3 minutes, `--make-sample --confirm`), parses `AddNo_Full` + `StNam_Full` as line 1 and
`SubAddress` as line 2, and compares our predirectional, postdirectional, suffix and unit with NAD's
wherever NAD has a non-empty label. It prints counts only. Run it after a street or unit rule changes:

```sh
python tools/netsyms/nad_score.py --make-sample --confirm   # once; writes local-data/nad-2026/sample1m.parquet
python tools/netsyms/nad_score.py
```

Read it with care: many providers put the suffix inside the name and leave the type empty (those rows
are skipped, since NAD has no label to compare), and `Unit` is spelled out (`Apartment 4`). On
the 2026-10-19 sample (NAD r24, seed 7) we differ from a labeled value in 0.11% of suffixes, 0.69% of
predirectionals, 0.14% of postdirectionals (0.50% before the city-copy fix, #29) and 3.7% of units
(mostly a spelled-out designator, a lone letter, or a bare number after a one-word street).

