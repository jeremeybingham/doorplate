# Netsyms harness

Parses the US rows of the Netsyms address database with doorplate and keeps artifacts for
analysis later, in a fresh session if need be. Everything runs offline; the database and
every artifact live in the git-ignored `local-data/`. Read `docs/data-policy.md` first: only
aggregate numbers leave `local-data/`, and nothing is committed from it.

| Script | Does |
|---|---|
| `run.py` | Prints a plan; with `--confirm` parses the rows in rowid chunks and writes a run directory |
| `analyze.py` | Summarizes a finished run: totals, warning codes, states, sources, place gaps |
| `compare.py` | Compares two runs (before and after a rule change): totals, warning codes, states |
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

