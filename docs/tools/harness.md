# Harness

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
| `shapes_report.py` | The worklist for a run: warning rates, the share with an `unparsed` remainder, and the top failure shapes per source and role; with `--before RUN`, what changed |
| `state_patterns.py` | Per-state counts of street patterns (Texas `RR`, `PR 123`, county roads, hyphenated numbers, `URB`, state-route spellings, a trailing number, a last word not in the suffix table) from a records file or the NAD Parquet: the evidence for the state rules (#53). Counts only |
| `test_run.py`, `test_label_score.py`, `test_shapes_report.py`, `test_state_patterns.py` | Tests on invented rows (`pytest tools/harness`) |
| `SCHEMA.md` | The artifacts' columns and the comparison rules (copied into every run) |

## Safe by default

`run.py` without `--confirm` only prints the plan (database, rowid range, chunks, run
directory, disk used and budget, commit) and exits. Start with the small sample:

```sh
pip install "doorplate[duckdb]"        # DuckDB and PyArrow, for the artifacts and analysis
python tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample              # plan
python tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --confirm    # run
python tools/harness/analyze.py <run-id>
```

Any other source goes through `tools/ingest/` first, then `--input`. The checks run only on
the fields a role has, rows with a `last_line` are parsed as one joined string and counted
apart (`last_line_rows`, `last_line_crossed`; #93 option A), and the artifacts are broken down
by `source`, `role` and `provider`:

```sh
python tools/ingest/ingest.py tools/ingest/specs/netsyms.toml --confirm
python tools/harness/run.py --input local-data/netsyms-2026/records.parquet --confirm
```

On the sample, a run from the Netsyms records and a direct `--db` run give the same totals,
warning codes and per-state counts (`compare.py` shows no change).

The full run (after the archive is extracted, which needs a separate go-ahead):

```sh
nohup python tools/harness/run.py --db local-data/netsyms-2026/<extracted>.sqlite \
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

Rerun the harness on the same database (a new run id), then `python tools/harness/compare.py <before> <after>`. The report lists how the totals, warning codes and per-state flagged counts moved, and warns when the two runs are not like for like (a different schema version, input or chunk size). Schema version 2 changed the `street` rule, so compare version-2 runs with each other.

## A rule PR, step by step

1. Environment (once): `uv venv venv`, activate it, `uv pip install maturin pytest usaddress pandas polars duckdb pyarrow nbclient nbformat ipykernel`, then `maturin develop --release` in `crates/doorplate-py`. Rebuild after every Rust change.
2. Change the rule. Add corpus cases with invented addresses (`docs/tests/corpus.md`); `tools/corpus/emit_expect.py` fills the emitter expectations from the spec, so teach it any change to the key. Add a row to `docs/usps-pub28-notes.md`. Rerun the corpus test with `UPDATE_CORPUS_BASELINE=1` and commit `tests/corpus/passing.txt`.
3. Compare on the sample (about 2 to 3 minutes a run): `python tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id NAME --confirm`, then `python tools/harness/compare.py BEFORE NAME`. Keep the previous run as BEFORE; old `sample-*` runs can be deleted. The comparison catches side effects the corpus does not (a designator rule once turned `FRONT ST` into a unit).
4. The `flagged/` Parquet files of a run keep each row's key and parsed components, so DuckDB can diff two runs row by row (rows whose key changed, new `unparsed_remainder` rows). Look at shapes (letters `a`, digits `9`) and counts, never at street names (`docs/data-policy.md`).
5. For a rule on one-line input, also run `tools/compare/city_diff.py` on the geocode splits and `tools/compare/oneline_fl.py` (`docs/running-benchmarks.md`).
6. Full Netsyms runs (about 20 minutes) only after a batch of rules and on the release commit. Ask before any extraction, full run or download.

## The worklist (`shapes_report.py`)

`python tools/harness/shapes_report.py RUN_ID` turns a finished run into a ranked list of failure
**shapes** and writes it to `shapes.md` in the run directory. For each source and role it gives the
rows, the share with a warning, with an `unparsed` remainder and with each mismatch; the warning
codes by rate; for the rows with an `unparsed` remainder, the shape of the input and of the
leftover; for the top three warning codes, the shapes of their inputs; and the style of the failing
inputs (case, unit forms, commas, spelled-out types: `line_styles` of `tools/benchsuite/shapes.py`)
beside the style of all inputs. A shape turns letters into `a` and digits into `9` and collapses
runs, so `123 N OAK ST` is `9 a a a`. The input text comes from the records file in the run's
manifest, joined to the flagged rows by `(source, role, record_id)`; a `--db` run has no text, so it
gets the leftover shapes only. Counts only, so the report can be quoted (`docs/data-policy.md`).

Two sections answer the two questions the shapes alone could not (#112). **`street` mismatch: top input shapes** lists the
forms behind the `street` check. **`missing_street_number`: a spelled-out number and a street suffix** counts the rows of that
code whose line 1 starts with a number word (`ONE` to `TWENTY`) and whose parse found a suffix, by word. It only measures, and it
reads the run's own parse: a run made before #129 (spelled-out numbers read as house numbers, 2026-10-24) still counts the rows
that rule now fixes. Check the run's commit (`manifest.json`) against the rule you are asking about. On the `s9-*` runs
(commit `140ccf72`, 2026-10-20, schema 7, before the `k3` rules) it was 15,120 NY registry rows; parsing those same 15,120 rows
with the 2026-10-27 build, 1,523 still have no house number, mostly where the number word is part of a street name
(`ONE HOLLOW ...`, `ONE WEST ...`, `ONE PARK ...`, `ONE UNION ...`). The `street` mismatch rates of those runs (FMCSA US
carriers 2.5% and 2.9%, NY corporations 1.0% to 2.6%, Netsyms 0.28%) are likewise of the old build: rerun before quoting them.

To see what the failing rows actually are, and to say what the right answer is, `tools/review/` draws a few rows from each of the biggest shapes of a run and shows them to a person (`docs/tools/review.md`, issue #122).

For a source that groups its rows (FMCSA's country, Netsyms's original provider), a provider table
comes first and `--provider NAME` reports one provider alone (`shapes-NAME.md`), so foreign rows do
not hide a source's US findings. The `unit` mismatch runs only for roles with a `label_unit` (a
source that says its line 2 is a unit); elsewhere line 2 holds attention lines and building names.

`--before RUN` adds, per source and role, what changed between two runs of the same input: the
totals, the warning codes and the leftover shapes that moved most. Use it as the "before and after"
of a rule PR. The list is a set of questions, not a bug count: each fix still needs an invented
corpus case, a source for the rule (`docs/usps-pub28-notes.md`), the rule and a comparison.

## Reading a run: triage first

A shape in the report is a question, not a bug. Before chasing one, sort it:

1. **Out of scope?** A source can mix in addresses the parser is not for: the federal carrier
   census has Canadian and Mexican rows, and every one of them is flagged. Report the in-scope
   part alone with `shapes_report.py RUN --provider US`.
2. **Source noise?** Line 2 often holds attention lines, building names and place names, not a
   unit. The checks only run on the fields a role really has (`SCHEMA.md`: the `unit` check needs
   `label_unit`), and a pair check drops movers (a different ZIP or house number between the two
   files).
3. **A flaw in a check?** The harness's own checks have been wrong before: PO box and rural route
   words counted as street mismatches, a spelled-out unit (`SUITE`) against its abbreviation
   (`STE`), a state spelled out (`NEW YORK`). Each fix bumped the schema version (version 8: an ordinal compares as its number, `5TH` equals `5`). When a mismatch
   rate looks implausible, break it down by address type and shape before blaming the parser.
4. **A parser question?** Reproduce it with an invented address of the same shape. If it does not
   reproduce, it is a property of the source. If it does, find a source for the rule
   (`docs/usps-pub28-notes.md`), then follow the rule PR steps above.

Some results look like failures and are by design: `missing_street_number` on a street with no
house number (`COUNTY ROAD 12`, `MAIN STREET`), and `multiple_addresses` on two house numbers on
one line (`123 456 MAIN ST`, see the rule row in `docs/usps-pub28-notes.md`). Look at shapes and
counts, never at rows (`docs/data-policy.md`).

## Label scoring (`label_score.py`, and `nad_score.py` for NAD)

Some sources label the parts of each address (NAD, the NC voter snapshot), which the Netsyms
rows do not. `label_score.py` parses a records file (`tools/ingest/`) and compares our
predirectional, postdirectional, suffix, unit, house number and street name with the labels
wherever a label is present. It prints counts only, per source and role: the rows labeled, the
rows where we differ, the top (label -> ours) pairs for the lexicon fields, the top shapes
(letters `a`, digits `9`) for the others, and the top states. Like `run.py`, it prints a plan
until `--confirm`.

```sh
python tools/harness/label_score.py local-data/nad-2026/records.parquet --confirm
```

**How reliable is each warning (`--by-warning`, #102).** Adds a table per source and role: for each warning code
the rows that carry it and, for each field, the labeled rows among them and the share where we differ (a row with
several warnings counts under each; the first line is every row, the baseline). Counts only. The page that reads
these numbers is [`docs/warnings.md`](../warnings.md); regenerate them after a rule change with
`label_score.py RECORDS --by-warning --confirm`.

**Label conventions the scorer applies (#112).** A label's `EXT` post-modifier is the suffix (`MAIN ST EXT`: type `ST`,
modifier `EXT`; Pub 28 appendix C1 lists `EXT` as a primary suffix, and we read `100 MAIN ST EXT` as the street `MAIN STREET`
with the suffix `EXT`); the scorer compares our suffix with the modifier and accepts the name with its type spelled out. A
suffix inside the label's name with no type (`OAK ST`) is the same name as our `OAK` + `ST`. A labeled unit whose value is
nowhere in the text we parsed is the source's, not a miss, and is counted apart (`labeled units are nowhere in the text`). On
the NC pair score (5,630,889 pairs, 2026-10-27) these took the suffix differences from about 3,000 to 1,292 (0.02%; about
1,700 were `EXT`), the name from 2.33% to 2.05% and the unit from 0.58% to 0.39%. What is left is mostly the source: in the
sampled suffix swaps (`CT` to `DR` 141 pairs, `DR` to `RD` 107, `RD` to `DR` 95) our suffix is a word of the as-entered line in
over 90% of the sampled pairs and the county's label is not, and the 33 postdirectional `E` read as `SE` have `SE` in the
text in 38 of 40 sampled: the as-entered file and the county snapshot disagree, and we follow the text. The NAD unit figure is in the NAD paragraph below.

**Looking at examples (`--examples FILE`).** Writes the disagreements to a tab-separated file instead of the terminal: source,
role, field, record id, pair id, and the label and our value. FILE must be under `local-data/` (git-ignored; ids are
private). It keeps at most `--examples-max` (default 5) per distinct label -> ours pair or shape pair, so rare pairs appear.
Open the records by id by hand and report only the finding (`docs/data-policy.md`):

```sh
python tools/harness/label_score.py local-data/nc-voter-2026/records_current.parquet \
    --labels local-data/nc-voter-2026/records_snapshot.parquet \
    --examples local-data/harness-112/examples.tsv --confirm
```

**Same address in two forms.** With `--labels OTHER.parquet`, the labels come from another file and
rows are paired by `(role, pair_id)` (ids unique in both files). Our parse of the first file's
one-line form is scored against the other file's labels, and reported as a pair score. For the
NC voter file, the as-entered street of the current file against the county-entered parts of
the March snapshot:

```sh
python tools/harness/label_score.py local-data/nc-voter-2026/records_current.parquet \
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
python tools/harness/nad_score.py --make-sample --confirm   # once; writes local-data/nad-2026/sample1m.parquet
python tools/harness/nad_score.py
```

Read the figures with care: many providers put the suffix inside the name and leave the type empty
(those rows are skipped, since there is no label to compare), and `Unit` is spelled out
(`Apartment 4`). On the 2026-10-19 sample (NAD r24, seed 7) scored on 2026-10-27 with the quieter scorer (#112) we differ from a labeled value
in 0.08% of suffixes, 0.69% of predirectionals, 0.14% of postdirectionals (0.50% before the city-copy fix, #29)
and 3.17% of units (it was 3.6% with the old scorer). The scorer does not compare spelled-out designators, so they are not the
cause: 4,206 of the 132,763 labeled units are rows where we found no unit, and 3,494 of those (83%) carry `unparsed_remainder`,
the unit text left over (digit-led text 35%, a word or a single letter we do not read as a designator 38%, condo words
`CND`, `COND`, `CONDO` 13%, `SITE` and `CAMPSITE` 6%; the rest `UNIT`, `APARTMENT`, `FLOOR`, `BUILDING` and `LEFT` followed by text we
do not read). The lead is in its own issue. `label_score.py` reproduces the previous `nad_score.py` exactly on this sample
(212,150 / 72,054 / 915,429 / 132,763 labeled; 1,473 / 100 / 976 / 4,805 differing) in 15 seconds
instead of 2 minutes (with the scorer's later conventions: 1,473 / 100 / 753 / 4,206 differing). A source's labels are its providers' choices, not ground truth: a
disagreement is a question, not a bug count.
