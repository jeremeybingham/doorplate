# Netsyms harness

Parses the US rows of the Netsyms address database with doorplate and keeps artifacts for
analysis later, in a fresh session if need be. Everything runs offline; the database and
every artifact live in the git-ignored `local-data/`. Read `docs/data-policy.md` first: only
aggregate numbers leave `local-data/`, and nothing is committed from it.

| Script | Does |
|---|---|
| `run.py` | Prints a plan; with `--confirm` parses the rows in rowid chunks and writes a run directory |
| `analyze.py` | Summarizes a finished run: totals, warning codes, states, sources, place gaps |
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

- `--budget-gb` (default 55): the run stops cleanly when the database's folder (not counting
  `.7z` archives) plus all runs exceed it. Finished chunks are kept; repeat the command with `--run-id <id>` to resume.
- `--min-free-gb` (default 20): refuses to start below this much free disk.
- `--threads N`: caps the Rust parse threads.
- A run is resumable at any point: a chunk counts as finished only when its `done/` marker
  exists, and every file is written under a temporary name and renamed.

## For a new session

Open the run directory and read `README_RUN.md`, `manifest.json` and `SCHEMA.md`. Check that
`DONE` exists. Then run `analyze.py` or query the Parquet files with DuckDB. The manifest names
the commit, doorplate version, data-table hash and the input fingerprint the run used.
