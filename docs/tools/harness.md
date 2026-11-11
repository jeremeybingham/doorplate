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
| `messy_score.py` | The MessyStreets scorecard (#323): parses each web address as one string and compares ZIP5, state, city and street name with the page's own fields, per tier (counts only) |
| `shapes_report.py` | The worklist for a run: warning rates, the share with an `unparsed` remainder, and the top failure shapes per source and role; with `--before RUN`, what changed |
| `state_patterns.py` | Per-state counts of street patterns (Texas `RR`, `PR 123`, county roads, hyphenated numbers, `URB`, state-route spellings, a trailing number, a last word not in the suffix table) from a records file or the NAD Parquet: the evidence for the state rules (#53). Counts only |
| `test_run.py`, `test_label_score.py`, `test_messy_score.py`, `test_shapes_report.py`, `test_state_patterns.py` | Tests on invented rows (`pytest tools/harness`) |
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
5. Steps 3 and 5 and the seven-source key dump and diff run together with `tools/compare/measure_rule_pr.sh BASE_REF NAME` (see its header; about 15 minutes, builds the base in a worktree and deletes it, its venv and the dumps afterwards). It includes `tools/compare/city_diff.py` on the four geocode splits and `tools/compare/oneline_fl.py` for both builds (`docs/running-benchmarks.md`), the checks for a rule on one-line input; they are cheap, so they run for every rule PR.
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

Two sections answer the two questions the shapes alone could not. **`street` mismatch: top input shapes** lists the
forms behind the `street` check. **`missing_street_number`: a spelled-out number and a street suffix** counts the rows of that
code whose line 1 starts with a number word (`ONE` to `TWENTY`) and whose parse found a suffix, by word. It only measures, and it
reads the run's own parse: a run made before the spelled-out-number rule (spelled-out numbers read as house numbers) still counts the rows
that rule now fixes. Check the run's commit (`manifest.json`) against the rule you are asking about. Most rows that still have no house number are
ones where the number word is part of a street name (`ONE HOLLOW ...`, `ONE WEST ...`, `ONE PARK ...`, `ONE UNION ...`). Rates from an old run
are of the old build: rerun before quoting them.

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

## How common is each open problem? (`probes.py`, #298)

One probe per open issue: a pattern over line 1 and line 2 (`tools/harness/probes.py`, the registry `PROBES`). Over the ingested records files
it counts, per probe and source, the rows whose text has the shape, how many of those the parser flags today (a warning in
`unparsed_remainder`, `missing_street_number`, `possibly_truncated`, `missing_unit_number`, `invalid_zip`, or a key without state and ZIP) and, with
`--compare`, how many of a sample of them usaddress reads differently. Counts only.
`hits(line1, line2, zip, city, state)` also takes the city and state, for the probes on the fields (`city-is-state`, `unit-or-box-in-city`, `city-placeholder`, `null-word-field`); `city-state-zip-twice` and `repeated-state-or-county` are functions over the text. The registry covers the open issues; a probe for a closed issue stays in it to show the shape fall after the fix.

**Coverage and what "proved" means.** `python tools/harness/probes.py --coverage` (needs `gh`) checks the open issues labeled `area:rules`: each has a probe in the registry or a reason in `NO_PROBE` (research, or a family whose members have the probes); trackers and the docs, tooling, API and architecture issues are not text shapes and are skipped. It prints issue numbers and counts only and exits 1 when one has neither. The rule: an `area:rules` issue that is filed or promoted gets its probe (or reason) in the next PR of the batch, because the scan hashes the registry at its start and refuses to run while the check fails; a probe added after a scan needs a second pass (#465). Before a release the probe counts are taken twice, on the last release's build and on the release commit (a full Netsyms run into `agg_probes`, and `probes.py` over the seven records files). An **open** issue is proved when its probe counts rows (the shape exists in the data); a **closed** issue is proved when its flagged count fell, or the rows still flagged are explained (a different shape, a record with no state or ZIP, which gives a partial key). A key without state and ZIP counts as flagged, so a probe over a source with many such records shows a flagged share that no rule can lower.

```sh
python tools/harness/probes.py local-data/*/records.parquet --sample 10 --compare 300 --out local-data/backlog-probes/report.json --confirm
python tools/harness/probes.py ... --queue local-data/review/queue-probes.jsonl --queue-top 10 --queue-n 50 --confirm   # a review queue of matches
```

`--exclude-probes a,b` leaves probes out of the queue (already reviewed, or held back) and `--exclude-pr` leaves out Puerto Rico rows (state `PR`, ZIP 006, 007 or 009, or a Spanish street word; `is_puerto_rico`), so the queue is free of the forms that wait for the Puerto Rico epic and its own queue. `--compare 0` skips the usaddress comparison for the report when only the queue is wanted (the queue still compares each card).

A pattern is an upper bound: it also matches correct rows. Two things turn "has the shape" into "is wrong": the usaddress disagreement rate
(a shape both parsers read alike is probably fine) and the review queue, where a person marks 50 matches per probe (`tools/review/server.py`
on the queue, then the verdicts give a precision). The score that orders the issues is in `docs/backlog.md`, "Ordering by how common". The same
registry is counted by `run.py` into `agg_probes/` (schema version 9), so a full Netsyms run counts every probe over all its rows without keeping text.

### The unsampled scan (`probe_scan.py`, #465)

`probes.py` samples one row in ten of the records files; a shape that occurs a few hundred times is then counted in steps of ten.
`tools/harness/probe_scan.py` counts every probe over every row of whole sources, with no sampling, and keeps the identity of each
match. It does the cheap part only: the regexes over all rows, and one parser call for the rows that match some probe (to say whether
the parse is flagged). It does not parse the other rows.

```sh
python tools/harness/probe_scan.py local-data/probe-scan-inputs.txt --limit-chunks 1 --confirm     # smoke test: one chunk per input, for the ETA
tools/harness/run_probe_scan.sh local-data/probe-scan-inputs.txt NAME                                 # the run, in a terminal you can leave (tmux): a banner and a bell say DONE, STOPPED or FAILED
python tools/harness/probe_scan.py --summary local-data/probe-scan/NAME                               # rebuild and print summary.json
```

The list file has one input per line (`#` starts a comment): a records file, the raw NAD file (mapped as in `tools/ingest/specs/nad.toml`),
or the Netsyms SQLite database (`table=addresses country=US`). A smoke test on one chunk of 11 inputs (9.0M rows) took 52 seconds on 11 workers.
Without `--confirm` it prints the plan, including whether `probes.py --coverage` passes; a run refuses to start when it does not, because the
manifest hashes `probes.py` and a probe added later would need a second pass. A run directory `local-data/probe-scan/<run-id>/` holds:

| File | Content |
|---|---|
| `manifest.json` | the commit, the sha256 of `probes.py`, the doorplate version, the inputs (size, mtime, row range), the options, the times |
| `counts/*.parquet` | one file per chunk: `source, role, state, probe, kind, n`; `kind` is `rows`, `flagged` or `partial_key`; the probe `__rows__` counts all rows. Sum `n` across chunks |
| `hits/*.parquet` | one file per chunk: `source, role, record_id, state, probe, flagged, text_hash, rk`. No address text; read the text back from the input by `record_id` to build a review queue |
| `chunk_status/*.json`, `progress.log`, `status.json` | one status per chunk; a log line per chunk with rows, rate, elapsed time and ETA, a heartbeat every minute (free disk, worker memory); `status.json` is rewritten after each chunk for `watch cat` |
| `summary.json`, `DONE` | totals per probe and source, the probes below 20 rows; written on success |

Per probe and chunk at most `--hit-cap` (1000) matches are kept in `hits/`, the ones with the lowest `rk` (a seeded hash in [0, 1)), so a capped
probe is still a random sample; the exact count is in `counts/`. `record_id` is the record id of a records file, the file row number of the
raw NAD file, or the SQLite rowid. `record_id` of different inputs can repeat: key on `source` and `record_id` and the input. A run resumes
with the same `--run-id` (chunks with a status file are skipped; exit status 3 means stopped or some chunks failed), stops cleanly after the chunks in progress on SIGINT or SIGTERM, and
refuses to resume when `probes.py` has changed. Reader errors print the exception type only. The NC snapshot overlaps the current NC file:
scan it in a run of its own and report it apart, never added to the total. Workers are spawned, not forked, because DuckDB does not
survive a fork.
Add a probe when an issue is opened, with its pattern, size and harm; remove it when the issue closes.

## Progress lines in the long-running tools (#524)

### The leftover-shape scan (`shape_scan.py`, #524)

The probe scan counts shapes someone thought of. `tools/harness/shape_scan.py` needs no idea in advance: it parses every row of the same inputs file (about 9 minutes for 289M rows on 13 workers) and counts, per source and state, the shape of the input and of the leftover text for each failure warning (`unparsed_remainder`, `missing_street_number`, `missing_street_name`, `missing_unit_number`, `possibly_truncated`, `multiple_addresses`, `ambiguous_street_number`, `second_line_in_street`). A shape turns numbers into `9` and words outside the lexicon tables into `a`, so no name or street appears. `python tools/harness/shape_scan.py INPUTS.txt --run-id NAME --confirm`, then `--summary local-data/shape-scan/NAME` for the ranked table; the run directory holds `counts/` (one Parquet file per chunk), `summary.json` and `DONE`. Resume with the same `--run-id`. Run it after a batch of rules and on the release commit: a shape with a large count and no probe or issue is a finding. `--mode roundtrip` is the same tool with a different question: for every row with a key it writes the USPS lines, parses them again and compares the property and unit keys with the originals (the invariant of the corpus test `usps_output_round_trips_to_the_same_key`), counting the shapes of the rows that do not read back (run directory `local-data/roundtrip-scan/`). `--mode words` counts the lone alphabetic words that are all of line 2 and were left unparsed, and `--mode numword` the number-and-word line 2 (`1 STORY`) by the kind of street before it and what the parser did with it (run directory `local-data/word-scan/`); both keep words, so read only the frequent ones (#545, #531). A row with no city (`missing_city`) cannot read back reliably, since its USPS last line is a state and a ZIP alone; read the counts for rows with a city first.

The tools that run for minutes print `##progress` lines (the one-line protocol of [tqdm-claude](https://github.com/ExtReMLapin/tqdm-claude/blob/main/PROTOCOL.md): `##progress step=3/7 label=NAME sub=1840/2400`, `pct=45`, `eta=`, `msg=`), flushed, next to their usual output, so a wrapper can say how far along a run is without reading its log by eye: `key_diff.py dump` (rows of the source, `sub`), `key_diff.py dump-all` (the source, `step`), `probe_scan.py` (`pct` per finished chunk) and `disable_check.py` (call site `sub`). The lines go to stderr in `dump` (its own progress is there) and stdout elsewhere. A tool that does not know the format ignores them.

## MessyStreets (`messy_score.py`, #323)

[MessyStreets](https://github.com/EdGaere/MessyStreets) (Gaere and von Wangenheim, ACM SIGSPATIAL '26, DOI 10.1145/3841645.3843362; cite it with any
score) is 3 tiers of 10,000 verbatim addresses from websites' schema.org markup (the December 2024 Web Data Commons extract), multinational. It is
a source of web business addresses, a kind none of our registries cover. Its labels are the page's own fields (not hand-checked) plus, for gold
and silver, the street name of an OpenStreetMap or OpenAddresses record that the address was matched to; there are no token labels.

**Rules of use** (`docs/data-policy.md`, `local-data/messy-streets/NOTICE.md`): local, aggregates only, nothing from the rows in the repository;
the terms were accepted by the owner (Web Data Commons says "research purposes only"; whether a parser evaluation counts is
asked in #395). **Gold and silver are held-out checks**: they are scored in bulk and never read, never queued. **Raw is the work list**: it may be
read (`full-ok.txt` lists `messy-streets`, for the raw queue only) and feeds rule issues like any source.

**To repeat it.**

```sh
# 1. Data (once): the three release_*_10k_final.jsonl.gz files from the repository root, in local-data/messy-streets/ (NOTICE.md has the hashes)
python tools/ingest/ingest.py tools/ingest/specs/messy-streets.toml --confirm    # US-like rows only: gold, silver, raw roles
# 2. Score (a second; retake it for each release and put the table in docs/benchmarks.md)
python tools/harness/messy_score.py --confirm
# 3. The review round on raw (the state of the reviews is in #225)
python tools/review/compare_sample.py local-data/messy-streets/records.parquet --role raw --out local-data/review/queue-compare-messy.jsonl --confirm
python tools/review/server.py local-data/review/queue-compare-messy.jsonl
```

**Missing-value strings.** The markup has the literal strings `NaN`, `undefined`, `null`, `none` and `n/a` for a missing field (a data
pipeline wrote them) and HTML entities such as `&amp;`. The ingest spec now turns the strings into nulls and decodes the entities; before, the review
queue joined them into the one-line string (`... IL NaN`), and 13.1% of the raw US rows (303 of 2,315) read as give-ups for that reason: 405 rows had
text left unparsed, 194 after cleaning. The first review round (`queue-compare-messy`, 150 cards) was mostly that; the round on cleaned rows is
`queue-compare-messy2`. `--joined` scores the cleaned fields (`docs/benchmarks.md`).

`messy_score.py` parses each address's one `input` string (street, locality, region, ZIP, country joined) and compares ZIP5, state, city and street
name with the markup; the queue instead uses the street lines, city, state and ZIP joined as the harness does. A literal `nan` in the markup counts as
a missing label. Misses are questions, not bug counts: a page's locality can be a neighbourhood or county, and the rates are not an accuracy claim.

**What it found so far.** On the raw tier (2,316 US-like rows): a unit word in the street field 9.3% (city agreement 83%); the street field repeating the
city, state or ZIP 2 to 8% (city agreement 6 to 28%; the paper's Table 1 shows the same shape): see #397; non-Latin text in the street 0.3%; no literal
`\n` escapes in the US rows. The paper has no US-only numbers; its Table 1 is seven illustrative gold examples, not a failure count.

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
on the NC pair score (5,630,889 pairs) these took the suffix differences from about 3,000 to 1,292 (0.02%; about
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
(`Apartment 4`). On a sample (NAD r24, seed 7), scored with the quieter scorer, we differ from a labeled value
in 0.08% of suffixes, 0.69% of predirectionals, 0.14% of postdirectionals (0.50% before the city-copy fix)
and 3.17% of units (it was 3.6% with the old scorer). The scorer does not compare spelled-out designators, so they are not the
cause: 4,206 of the 132,763 labeled units are rows where we found no unit, and 3,494 of those (83%) carry `unparsed_remainder`,
the unit text left over (digit-led text 35%, a word or a single letter we do not read as a designator 38%, condo words
`CND`, `COND`, `CONDO` 13%, `SITE` and `CAMPSITE` 6%; the rest `UNIT`, `APARTMENT`, `FLOOR`, `BUILDING` and `LEFT` followed by text we
do not read). The lead is in its own issue. `label_score.py` reproduces the previous `nad_score.py` exactly on this sample
(212,150 / 72,054 / 915,429 / 132,763 labeled; 1,473 / 100 / 976 / 4,805 differing) in 15 seconds
instead of 2 minutes (with the scorer's later conventions: 1,473 / 100 / 753 / 4,206 differing). A source's labels are its providers' choices, not ground truth: a
disagreement is a question, not a bug count.

## Determinism checks: WebAssembly against native, one thread against many (`phase_g_check.py`, #567)

`python tools/compare/phase_g_check.py wasm-native --wasm FILE.wasm --exe target/release/doorplate` parses a seeded sample (default 10M rows, `--seed`, from the key-comparison sources) with the WebAssembly build the review page and the demo run (`parse_batch` in Node, fields mode, through `tools/compare/wasm_batch.mjs`) and with the native `doorplate parse-file`, and compares all 30 output columns. `python tools/compare/phase_g_check.py threads [--workers 13]` sends the same sample through `parse_fields_many` with `RAYON_NUM_THREADS=1` and `=13` and compares the key, the unit-level key, the warnings and the four unit fields. Build first: `cargo build --release -p doorplate-cli` and `cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release`; `threads` uses the `doorplate` installed in the Python that runs it. Both work in chunks (`--chunk`, 500,000 rows), keep one chunk on disk under `local-data/phase-g/` and delete it, print counts only (rows that differ, and which columns) and exit 0 (no difference), 1 (differences) or 2 (could not run). Expected: 0 differing rows. About 20 minutes each on 10M rows; the away run (#566, phase G) calls both. `--error-log FILE` keeps the full traceback of a failed check in a local file (a DuckDB message can quote rows, so the output names only the exception type). The native CSV is read with its dialect fixed (comma, `"` quote and escape): left to DuckDB's guesser, the 10M check of the 2026-11-07 away run stopped on an apostrophe taken for the escape character (#579). First result: wasm-native on 10,000,000 rows, seed 1, build `origin/main` 4c98ed7: 0 rows differ (1,000, 100,000 and 1,000,000 rows also 0).
