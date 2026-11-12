# Harness

Parses address sources with doorplate (the US rows of the Netsyms database, or any source
turned into records by `tools/ingest/`) and keeps artifacts for analysis later, in a fresh
session if need be. Everything runs offline; the database and every artifact live in the
git-ignored `local-data/`. Read [`data-policy.md`](../data-policy.md) first: only aggregate
numbers leave `local-data/`, and nothing is committed from it. Look at shapes (letters `a`,
digits `9`) and counts, never at street names or rows.

| Script | Does |
|---|---|
| `run.py` | Prints a plan; with `--confirm` parses the rows in chunks and writes a run directory. `--input` reads a `records.parquet` (any source, in row-offset chunks); `--db` reads the Netsyms SQLite directly |
| `analyze.py` | Summarizes a finished run: totals, warning codes, states, roles, last-line rows, providers, place gaps |
| `compare.py` | Compares two runs (before and after a rule change): totals, warning codes, states |
| `shapes_report.py` | The worklist for a run: warning rates, the share with an `unparsed` remainder, and the top failure shapes per source and role; with `--before RUN`, what changed |
| `label_score.py` | Scores any records file that has `label_*` columns against our parse, or against another file's labels paired by `pair_id` (counts only) |
| `nad_score.py` | The NAD scorecard: makes the NAD sample, then runs `label_score.py` on it |
| `messy_score.py` | The MessyStreets scorecard: parses each web address as one string and compares ZIP5, state, city and street name with the page's own fields, per tier (counts only) |
| `state_patterns.py` | Per-state counts of street patterns (Texas `RR`, `PR 123`, county roads, hyphenated numbers, `URB`, state-route spellings, a trailing number, a last word not in the suffix table) from a records file or the NAD Parquet. Counts only |
| `probes.py`, `probe_scan.py`, `shape_scan.py` | How common each open problem is, and what fails that nobody thought of (below) |
| `test_*.py` | Tests on invented rows (`pytest tools/harness`) |
| `SCHEMA.md` | The artifacts' columns and the comparison rules, copied into every run ([`harness-schema.md`](harness-schema.md)) |

## A rule PR, step by step

1. Environment (once): `uv venv venv`, activate it, `uv pip install maturin pytest usaddress pandas polars duckdb pyarrow nbclient nbformat ipykernel`, then `maturin develop --release` in `crates/doorplate-py`. Rebuild after every Rust change.
2. Change the rule. Add corpus cases with invented addresses ([`corpus.md`](../tests/corpus.md)); `tools/corpus/emit_expect.py` fills the emitter expectations from the spec, so teach it any change to the key. Add a row to [`usps-pub28-notes.md`](../usps-pub28-notes.md). Rerun the corpus test with `UPDATE_CORPUS_BASELINE=1` and commit `tests/corpus/passing.txt`.
3. Compare on the sample (about 2 to 3 minutes a run): `python tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id NAME --confirm`, then `python tools/harness/compare.py BEFORE NAME`. Keep the previous run as BEFORE; old `sample-*` runs can be deleted. The comparison catches side effects the corpus does not (a designator rule once turned `FRONT ST` into a unit).
4. The `flagged/` Parquet files of a run keep each row's key and parsed components, so DuckDB can diff two runs row by row (rows whose key changed, new `unparsed_remainder` rows).
5. Steps 3 and 4 and the seven-source key dump and diff run together with `tools/compare/measure_rule_pr.sh BASE_REF NAME` (see its header; it builds the base in a worktree and deletes it, its venv and the dumps afterwards). It includes `tools/compare/city_diff.py` on the four geocode splits and `tools/compare/oneline_fl.py` for both builds ([`running-benchmarks.md`](../running-benchmarks.md)), the checks for a rule on one-line input; they are cheap, so they run for every rule PR.
6. Full Netsyms runs only after a batch of rules and on the release commit. Ask before any extraction, full run or download.

`compare.py` lists how the totals, warning codes and per-state flagged counts moved, and warns when the two runs are not like for like (a different schema version, input or chunk size). Compare runs of the same schema version with each other.

### Finding the pull request behind a change (bisect)

To attribute a changed reading to the merge that caused it (the release check in [`change-checklist.md`](../change-checklist.md)):

1. List the strings whose reading differs between two builds, OLD and NEW.
2. Take the merges in between: `git log --first-parent OLD..NEW`, oldest first, with OLD as index 0.
3. Build the `doorplate` CLI once per commit you test and cache the binary by short hash (a `git worktree` of the repository; do not edit the checkout).
4. For each string, binary-search the merges for the first one whose reading (the label sequence over its words, from `doorplate parse --usaddress`) differs from OLD's.
5. Check that the found merge's reading equals NEW's. If not, the reading changed more than once: bisect each leg.
6. Count the strings per merge. Print counts only; the strings stay in `local-data/`.

## Reading a run

For a new session, open the run directory and read `README_RUN.md`, `manifest.json` and `SCHEMA.md`. Check that `DONE` exists. The manifest names the commit, doorplate version, data-table hash and the input fingerprint the run used. Then run `analyze.py`, `shapes_report.py` or query the Parquet files with DuckDB.

A shape in the report is a question, not a bug. Before chasing one, sort it:

1. **Out of scope?** A source can mix in addresses the parser is not for: the federal carrier census has Canadian and Mexican rows, and every one of them is flagged. Report the in-scope part alone with `shapes_report.py RUN --provider US`.
2. **Source noise?** Line 2 often holds attention lines, building names and place names, not a unit. The checks run only on the fields a role really has (`SCHEMA.md`: the `unit` check needs `label_unit`), and a pair check drops movers (a different ZIP or house number between the two files).
3. **A flaw in a check?** The harness's own checks have been wrong before: PO box and rural route words counted as street mismatches, a spelled-out unit (`SUITE`) against its abbreviation (`STE`), a state spelled out (`NEW YORK`). Each fix bumped the schema version. When a mismatch rate looks implausible, break it down by address type and shape before blaming the parser.
4. **A parser question?** Reproduce it with an invented address of the same shape. If it does not reproduce, it is a property of the source. If it does, find a source for the rule ([`usps-pub28-notes.md`](../usps-pub28-notes.md)), then follow the rule PR steps above.

Some results look like failures and are by design: `missing_street_number` on a street with no house number (`COUNTY ROAD 12`, `MAIN STREET`), and `multiple_addresses` on two house numbers on one line (`123 456 MAIN ST`).

### The worklist (`shapes_report.py`)

`python tools/harness/shapes_report.py RUN_ID` writes `shapes.md` in the run directory. For each source and role it gives the rows, the share with a warning, with an `unparsed` remainder and with each mismatch; the warning codes by rate; for the rows with an `unparsed` remainder, the shape of the input and of the leftover; for the top three warning codes, the shapes of their inputs; and the style of the failing inputs (case, unit forms, commas, spelled-out types) beside the style of all inputs. A shape turns letters into `a` and digits into `9` and collapses runs, so `123 N OAK ST` is `9 a a a`. The input text comes from the records file in the run's manifest, joined to the flagged rows by `(source, role, record_id)`; a `--db` run has no text, so it gets the leftover shapes only. Counts only, so the report can be quoted.

Two sections answer questions the shapes alone could not: **`street` mismatch: top input shapes**, and **`missing_street_number`: a spelled-out number and a street suffix**, which counts the rows whose line 1 starts with a number word (`ONE` to `TWENTY`) and whose parse found a suffix, by word. It reads the run's own parse, so check the run's commit (`manifest.json`) against the rule you ask about, and rerun before quoting a rate.

For a source that groups its rows (FMCSA's country, Netsyms's original provider), a provider table comes first and `--provider NAME` reports one provider alone (`shapes-NAME.md`). The `unit` mismatch runs only for roles with a `label_unit`.

`--before RUN` adds, per source and role, what changed between two runs of the same input: the totals, the warning codes and the leftover shapes that moved most. The list is a set of questions, not a bug count: each fix still needs an invented corpus case, a source for the rule and a comparison. To see what the failing rows are and say what the right answer is, [`review.md`](review.md) draws rows from the biggest shapes and shows them to a person.

## Running it

`run.py` without `--confirm` only prints the plan (database, rowid range, chunks, run directory, disk used and budget, commit) and exits. Start with the small sample:

```sh
pip install "doorplate[duckdb]"        # DuckDB and PyArrow, for the artifacts and analysis
python tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample              # plan
python tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --confirm    # run
python tools/harness/analyze.py <run-id>
```

Any other source goes through `tools/ingest/` first, then `--input`. The checks run only on the fields a role has, rows with a `last_line` are parsed as one joined string and counted apart (`last_line_rows`, `last_line_crossed`), and the artifacts are broken down by `source`, `role` and `provider`:

```sh
python tools/ingest/ingest.py tools/ingest/specs/netsyms.toml --confirm
python tools/harness/run.py --input local-data/netsyms-2026/records.parquet --confirm
```

On the sample, a run from the Netsyms records and a direct `--db` run give the same totals, warning codes and per-state counts. The full run (after the archive is extracted, which needs a separate go-ahead):

```sh
nohup python tools/harness/run.py --db local-data/netsyms-2026/<extracted>.sqlite \
    --table addresses --confirm > local-data/netsyms-runs/run.out 2>&1 &
tail -f local-data/netsyms-runs/*/progress.log
```

Limits:

- `--budget-gb` (default 60): the run stops cleanly when the database's folder (not counting `.7z` archives) plus all runs exceed it. Finished chunks are kept; repeat the command with `--run-id <id>` to resume.
- `--min-free-gb` (default 20): refuses to start below this much free disk.
- `--threads N`: caps the Rust parse threads.
- A run is resumable at any point: a chunk counts as finished only when its `chunk_status/` marker exists, and every file is written under a temporary name and renamed.

The tools that run for minutes print `##progress` lines (the one-line protocol of [tqdm-claude](https://github.com/ExtReMLapin/tqdm-claude/blob/main/PROTOCOL.md): `##progress step=3/7 label=NAME sub=1840/2400`, `pct=45`, `eta=`, `msg=`), flushed, so a wrapper can say how far along a run is: `key_diff.py dump` (stderr) and `dump-all`, `probe_scan.py` and `disable_check.py` (stdout). A tool that does not know the format ignores them.

## How common is each open problem? (`probes.py`)

One probe per open issue: a pattern over line 1 and line 2 (`tools/harness/probes.py`, the registry `PROBES`). Over the ingested records files it counts, per probe and source, the rows whose text has the shape, how many of those the parser flags today (a warning in `unparsed_remainder`, `missing_street_number`, `possibly_truncated`, `missing_unit_number`, `invalid_zip`, or a key without state and ZIP) and, with `--compare`, how many of a sample of them usaddress reads differently. Counts only. `hits(line1, line2, zip, city, state)` also takes the city and state, for the probes on the fields (`city-is-state`, `unit-or-box-in-city`, `city-placeholder`, `null-word-field`); `city-state-zip-twice` and `repeated-state-or-county` are functions over the text. A probe for a closed issue stays in the registry to show the shape fall after the fix.

**Coverage and what "proved" means.** `python tools/harness/probes.py --coverage` (needs `gh`) checks the open issues labeled `area:rules`: each has a probe in the registry or a reason in `NO_PROBE` (research, or a family whose members have the probes); trackers and the docs, tooling, API and architecture issues are skipped. It prints issue numbers and counts only and exits 1 when one has neither. An `area:rules` issue that is filed or promoted gets its probe (or reason) in the next PR of the batch, because the scan hashes the registry at its start and refuses to run while the check fails; a probe added after a scan needs a second pass. Before a release the probe counts are taken twice, on the last release's build and on the release commit (a full Netsyms run into `agg_probes`, and `probes.py` over the seven records files). An **open** issue is proved when its probe counts rows; a **closed** issue is proved when its flagged count fell, or the rows still flagged are explained (a different shape, a record with no state or ZIP, which gives a partial key). A key without state and ZIP counts as flagged, so a probe over a source with many such records shows a flagged share that no rule can lower.

```sh
python tools/harness/probes.py local-data/*/records.parquet --sample 10 --compare 300 --out local-data/backlog-probes/report.json --confirm
python tools/harness/probes.py ... --queue local-data/review/queue-probes.jsonl --queue-top 10 --queue-n 50 --confirm   # a review queue of matches
```

`--exclude-probes a,b` leaves probes out of the queue (already reviewed, or held back) and `--exclude-pr` leaves out Puerto Rico rows (state `PR`, ZIP 006, 007 or 009, or a Spanish street word), so the queue is free of the forms that wait for the Puerto Rico epic. `--compare 0` skips the usaddress comparison for the report when only the queue is wanted.

A pattern is an upper bound: it also matches correct rows. Two things turn "has the shape" into "is wrong": the usaddress disagreement rate (a shape both parsers read alike is probably fine) and the review queue, where a person marks 50 matches per probe (`tools/review/server.py`; verdicts give a precision). The score that orders the issues is in [`backlog.md`](../backlog.md). The same registry is counted by `run.py` into `agg_probes/`, so a full Netsyms run counts every probe over all its rows without keeping text.

### The unsampled scan (`probe_scan.py`)

`probes.py` samples one row in ten of the records files. `tools/harness/probe_scan.py` counts every probe over every row of whole sources, with no sampling, and keeps the identity of each match. It does the cheap part only: the regexes over all rows, and one parser call for the rows that match some probe.

```sh
python tools/harness/probe_scan.py local-data/probe-scan-inputs.txt --limit-chunks 1 --confirm     # smoke test: one chunk per input, for the ETA
tools/harness/run_probe_scan.sh local-data/probe-scan-inputs.txt NAME                                 # the run, in a terminal you can leave (tmux): a banner and a bell say DONE, STOPPED or FAILED
python tools/harness/probe_scan.py --summary local-data/probe-scan/NAME                               # rebuild and print summary.json
```

The list file has one input per line (`#` starts a comment): a records file, the raw NAD file (mapped as in `tools/ingest/specs/nad.toml`), or the Netsyms SQLite database (`table=addresses country=US`). Without `--confirm` it prints the plan, including whether `probes.py --coverage` passes; a run refuses to start when it does not. A run directory `local-data/probe-scan/<run-id>/` holds:

| File | Content |
|---|---|
| `manifest.json` | the commit, the sha256 of `probes.py`, the doorplate version, the inputs (size, mtime, row range), the options, the times |
| `counts/*.parquet` | one file per chunk: `source, role, state, probe, kind, n`; `kind` is `rows`, `flagged` or `partial_key`; the probe `__rows__` counts all rows. Sum `n` across chunks |
| `hits/*.parquet` | one file per chunk: `source, role, record_id, state, probe, flagged, text_hash, rk`. No address text; read the text back from the input by `record_id` to build a review queue |
| `chunk_status/*.json`, `progress.log`, `status.json` | one status per chunk; a log line per chunk with rows, rate, elapsed time and ETA, a heartbeat every minute (free disk, worker memory); `status.json` is rewritten after each chunk for `watch cat` |
| `summary.json`, `DONE` | totals per probe and source, the probes below 20 rows; written on success |

Per probe and chunk at most `--hit-cap` (1000) matches are kept in `hits/`, the ones with the lowest `rk` (a seeded hash in [0, 1)), so a capped probe is still a random sample; the exact count is in `counts/`. `record_id` is the record id of a records file, the file row number of the raw NAD file, or the SQLite rowid, and can repeat across inputs: key on `source`, `record_id` and the input. A run resumes with the same `--run-id` (chunks with a status file are skipped; exit status 3 means stopped or some chunks failed), stops cleanly after the chunks in progress on SIGINT or SIGTERM, and refuses to resume when `probes.py` has changed. Reader errors print the exception type only. The NC snapshot overlaps the current NC file: scan it in a run of its own and report it apart, never added to the total. Workers are spawned, not forked, because DuckDB does not survive a fork. Add a probe when an issue is opened, with its pattern, size and harm; remove it when the issue closes.

### The leftover-shape scan (`shape_scan.py`)

The probe scan counts shapes someone thought of. `tools/harness/shape_scan.py` needs no idea in advance: it parses every row of the same inputs file (about 9 minutes for 289M rows on 13 workers) and counts, per source and state, the shape of the input and of the leftover text for each failure warning (`unparsed_remainder`, `missing_street_number`, `missing_street_name`, `missing_unit_number`, `possibly_truncated`, `multiple_addresses`, `ambiguous_street_number`, `second_line_in_street`). A shape turns numbers into `9` and words outside the lexicon tables into `a`, so no name or street appears. `python tools/harness/shape_scan.py INPUTS.txt --run-id NAME --confirm`, then `--summary local-data/shape-scan/NAME` for the ranked table; the run directory holds `counts/` (one Parquet file per chunk), `summary.json` and `DONE`. Resume with the same `--run-id`. Run it after a batch of rules and on the release commit: a shape with a large count and no probe or issue is a finding.

- `--mode roundtrip` writes the USPS lines of every row with a key, parses them again and compares the property and unit keys with the originals (the invariant of the corpus test `usps_output_round_trips_to_the_same_key`), counting the shapes of the rows that do not read back (run directory `local-data/roundtrip-scan/`). A row with no city (`missing_city`) cannot read back reliably, since its USPS last line is a state and a ZIP alone; read the counts for rows with a city first.
- `--mode words` counts the lone alphabetic words that are all of line 2 and were left unparsed, and `--mode numword` the number-and-word line 2 (`1 STORY`) by the kind of street before it and what the parser did with it (run directory `local-data/word-scan/`). Both keep words, so read only the frequent ones.

## Scoring against a source's labels

### `label_score.py` and `nad_score.py`

Some sources label the parts of each address (NAD, the NC voter snapshot), which the Netsyms rows do not. `label_score.py` parses a records file (`tools/ingest/`) and compares our predirectional, postdirectional, suffix, unit, house number and street name with the labels wherever a label is present. It prints counts only, per source and role: the rows labeled, the rows where we differ, the top (label -> ours) pairs for the lexicon fields, the top shapes for the others, and the top states. Like `run.py`, it prints a plan until `--confirm`.

```sh
python tools/harness/label_score.py local-data/nad-2026/records.parquet --confirm
```

- **`--by-warning`** adds a table per source and role: for each warning code the rows that carry it and, for each field, the labeled rows among them and the share where we differ (a row with several warnings counts under each; the first line is every row, the baseline). [`warnings.md`](../warnings.md) reads these numbers; regenerate them after a rule change with `label_score.py RECORDS --by-warning --confirm`.
- **Label conventions the scorer applies.** A label's `EXT` post-modifier is the suffix (`MAIN ST EXT`: type `ST`, modifier `EXT`; Pub 28 appendix C1 lists `EXT` as a primary suffix); the scorer compares our suffix with the modifier and accepts the name with its type spelled out. A suffix inside the label's name with no type (`OAK ST`) is the same name as our `OAK` + `ST`. A labeled unit whose value is nowhere in the text we parsed is the source's, not a miss, and is counted apart (`labeled units are nowhere in the text`).
- **`--examples FILE`** writes the disagreements to a tab-separated file instead of the terminal: source, role, field, record id, pair id, and the label and our value. FILE must be under `local-data/` (git-ignored; ids are private). It keeps at most `--examples-max` (default 5) per distinct label -> ours pair or shape pair. Open the records by id by hand and report only the finding:

  ```sh
  python tools/harness/label_score.py local-data/nc-voter-2026/records_current.parquet \
      --labels local-data/nc-voter-2026/records_snapshot.parquet \
      --examples local-data/harness-112/examples.tsv --confirm
  ```

- **Same address in two forms.** With `--labels OTHER.parquet`, the labels come from another file and rows are paired by `(role, pair_id)` (ids unique in both files). Our parse of the first file's one-line form is scored against the other file's labels, and reported as a pair score. For the NC voter file, the as-entered street of the current file against the county-entered parts of the March snapshot (the command above without `--examples`). The files can be months apart, so a voter who moved would show as a disagreement: pairs whose ZIP codes differ are dropped and counted (`--any-zip` keeps them).
- **NAD.** `nad_score.py` draws a random 1,000,000-row sample of the NAD text file (one pass, about 3 minutes, `--make-sample --confirm`), builds its records with `tools/ingest/specs/nad.toml` when they are missing, and runs `label_score.py` on the four fields it always scored. Run it after a street or unit rule changes:

  ```sh
  python tools/harness/nad_score.py --make-sample --confirm   # once; writes local-data/nad-2026/sample1m.parquet
  python tools/harness/nad_score.py
  ```

Read the figures with care: many providers put the suffix inside the name and leave the type empty (those rows are skipped, since there is no label to compare), and `Unit` is spelled out (`Apartment 4`). A source's labels are its providers' choices, not ground truth: a disagreement is a question, not a bug count. The figures are in [`warnings.md`](../warnings.md) and [`benchmarks.md`](../benchmarks.md).

### MessyStreets (`messy_score.py`)

[MessyStreets](https://github.com/EdGaere/MessyStreets) (Gaere and von Wangenheim, ACM SIGSPATIAL '26, DOI 10.1145/3841645.3843362; cite it with any score) is 3 tiers of 10,000 verbatim web addresses from schema.org markup. Its labels are the page's own fields, not hand-checked. The score table is in [`benchmarks.md`](../benchmarks.md#other-checks).

**Rules of use** ([`data-policy.md`](../data-policy.md), `local-data/messy-streets/NOTICE.md`): local, aggregates only, nothing from the rows in the repository; the terms were accepted by the owner (Web Data Commons says "research purposes only"). **Gold and silver are held-out checks**: they are scored in bulk and never read, never queued. **Raw is the work list**: it may be read (`full-ok.txt` lists `messy-streets`, for the raw queue only) and feeds rule issues like any source.

```sh
python tools/ingest/ingest.py tools/ingest/specs/messy-streets.toml --confirm    # US-like rows only: gold, silver, raw roles
python tools/harness/messy_score.py --confirm                                    # retake for each release; --joined scores the cleaned fields
python tools/review/compare_sample.py local-data/messy-streets/records.parquet --role raw --out local-data/review/queue-compare-messy.jsonl --confirm
python tools/review/server.py local-data/review/queue-compare-messy.jsonl
```

The data are the three `release_*_10k_final.jsonl.gz` files from the MessyStreets repository root, in `local-data/messy-streets/` (`NOTICE.md` has the hashes). The markup holds the literal strings `NaN`, `undefined`, `null`, `none` and `n/a` for a missing field and HTML entities such as `&amp;`; the ingest spec turns the strings into nulls and decodes the entities. `messy_score.py` parses each address's one `input` string and compares ZIP5, state, city and street name with the markup; the queue joins the street lines, city, state and ZIP as the harness does. Misses are questions, not bug counts: a page's locality can be a neighbourhood or county.

## Determinism checks (`phase_g_check.py`)

`python tools/compare/phase_g_check.py wasm-native --wasm FILE.wasm --exe target/release/doorplate` parses a seeded sample (default 10M rows, `--seed`, from the key-comparison sources) with the WebAssembly build the review page and the demo run (`parse_batch` in Node, fields mode, through `tools/compare/wasm_batch.mjs`) and with the native `doorplate parse-file`, and compares all 30 output columns. `python tools/compare/phase_g_check.py threads [--workers 13]` sends the same sample through `parse_fields_many` with `RAYON_NUM_THREADS=1` and `=13` and compares the key, the unit-level key, the warnings and the four unit fields. Build first: `cargo build --release -p doorplate-cli` and `cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release`; `threads` uses the `doorplate` installed in the Python that runs it. Both work in chunks (`--chunk`, 500,000 rows), keep one chunk on disk under `local-data/phase-g/` and delete it, print counts only (rows that differ, and which columns) and exit 0 (no difference), 1 (differences) or 2 (could not run). Expected: 0 differing rows. About 20 minutes each on 10M rows. `--error-log FILE` keeps the full traceback of a failed check in a local file (a DuckDB message can quote rows, so the output names only the exception type). The native CSV is read with its dialect fixed (comma, `"` quote and escape), because DuckDB's guesser once took an apostrophe for the escape character.
