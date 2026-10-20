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
| `label_score.py` | Scores any records file that has `label_*` columns against our parse, or against another file's labels paired by `pair_id` (counts only) |
| `nad_score.py` | The NAD scorecard: makes the NAD sample, then runs `label_score.py` on it |
| `test_run.py`, `test_label_score.py` | Tests on invented rows (`pytest tools/netsyms`) |
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

## Label scoring (`label_score.py`, and `nad_score.py` for NAD)

Some sources label the parts of each address (NAD, the NC voter snapshot), which the Netsyms
rows do not. `label_score.py` parses a records file (`tools/ingest/`) and compares our
predirectional, postdirectional, suffix, unit, house number and street name with the labels
wherever a label is present. It prints counts only, per source and role: the rows labeled, the
rows where we differ, the top (label -> ours) pairs for the lexicon fields, the top shapes
(letters `a`, digits `9`) for the others, and the top states. Like `run.py`, it prints a plan
until `--confirm`.

```sh
python tools/netsyms/label_score.py local-data/nad-2026/records.parquet --confirm
```

**Same address in two forms.** With `--labels OTHER.parquet`, the labels come from another file and
rows are paired by `(role, pair_id)` (ids unique in both files). Our parse of the first file's
one-line form is scored against the other file's labels, and reported as a pair score. For the
NC voter file, the as-entered street of the current file against the county-entered parts of
the March snapshot:

```sh
python tools/netsyms/label_score.py local-data/nc-voter-2026/records_current.parquet \
    --labels local-data/nc-voter-2026/records_snapshot.parquet --confirm
```

The files can be months apart, so a voter who moved would show as a disagreement. Pairs whose
ZIP codes differ are dropped and counted (`--any-zip` keeps them). On a 50,000-row slice that
guard dropped 2.8% of pairs and cut the disagreement rates by about two thirds.

**NAD.** `nad_score.py` draws a random 1,000,000-row sample of the NAD text file (one pass, about 3
minutes, `--make-sample --confirm`), builds its records with `tools/ingest/specs/nad.toml` when
they are missing, and runs `label_score.py` on the four fields it always scored. Run it after a
street or unit rule changes:

```sh
python tools/netsyms/nad_score.py --make-sample --confirm   # once; writes local-data/nad-2026/sample1m.parquet
python tools/netsyms/nad_score.py
```

Read the figures with care: many providers put the suffix inside the name and leave the type empty
(those rows are skipped, since there is no label to compare), and `Unit` is spelled out
(`Apartment 4`). On the 2026-10-19 sample (NAD r24, seed 7) we differ from a labeled value in 0.11% of
suffixes, 0.69% of predirectionals, 0.14% of postdirectionals (0.50% before the city-copy fix, #29)
and 3.6% of units (mostly a spelled-out designator, a lone letter, or a bare number after a
one-word street). `label_score.py` reproduces the previous `nad_score.py` exactly on this sample
(212,150 / 72,054 / 915,429 / 132,763 labeled; 1,473 / 100 / 976 / 4,805 differing) in 15 seconds
instead of 2 minutes. A source's labels are its providers' choices, not ground truth: a
disagreement is a question, not a bug count.
