# Review: a person looks at the hard addresses

Issue #122. A harness run tells us which shapes of address fail (`tools/harness/shapes_report.py`),
and an invented address can reproduce each one. It cannot tell us what the **right answer** is for a
messy real row; a person can. This tool shows one hard row at a time and records what the person
says, so the answers can be read later for new shapes and rules. Read `docs/data-policy.md` first:
the queue and the answers hold real addresses and stay in `local-data/`.

```sh
python tools/harness/run.py --input local-data/<source>/records.parquet --confirm     # a run, as usual
python tools/review/sample.py RUN_ID --confirm                  # the queue (without --confirm: the plan)
cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release   # the parser the page runs
python tools/review/server.py                                   # then open http://127.0.0.1:8765/
python tools/review/export.py                                   # the shape-only file that may be shared
pytest tools/review                                             # tests (invented rows)
```

Python 3.11 or later for `sample.py` (it uses the harness and DuckDB); the server and the export
need only the standard library.

## The queue (`sample.py`)

Takes the rows a run flagged with a warning or an `unparsed` remainder, groups them by failure shape
(the shape of the input lines and the warning codes, as the shapes report does), and keeps up to
`--per-shape` (2) random rows from each of the biggest groups, up to `--limit` (150). The first row of
every group comes before the second row of any, so a hundred reviews cover the biggest shapes instead
of the same one many times. `--seed` makes the sample repeatable; `--source` and `--role` narrow it.
The queue is `local-data/review/queue.jsonl`; each line carries the input lines (and city, state,
ZIP), the group's shape, warnings and size.

**It reads harness runs of real sources only.** It refuses the benchmark suite and the geocode
benchmark: `docs/benchmark-suite.md` says the suite is not a work list, and the geocode splits were read
while rules were written, so review answers on them would tune the parser to the score. Adding
benchmark rows needs a decision recorded on issue #122 first.

A repeated input (same lines, city, state and ZIP) is queued once. `--group coarse` groups by the warnings and the shape
of line 1's first word instead of the whole input shape: a second pass on a source, when `--per-shape 2` never used its second
row because every group was a different shape (#132).

## The comparison queue (`compare_sample.py`): where does doorplate lose to usaddress?

There is no ground truth on a real source, so this finds rows where doorplate and usaddress **disagree** and lets a person say
who was right. The rows where usaddress is right are the classes where doorplate chooses badly; "both right" separates a real
error from a labeling convention. It reads a source's `records.parquet` (not a harness run), samples `--rows` (200,000, about
25 seconds of usaddress) rows with `--seed`, joins each to one line as the harness does, and compares the two parses token by token
on coarse labels (the rules of `tools/compare/compare_usaddress.py` and `docs/usaddress-compat.md`: the street parts fold into
one, `Subaddress*` is `Occupancy*`, and the labels doorplate does not model, such as `Recipient` and `LandmarkName`, are not
scored). It needs `usaddress` in the environment (`uv pip install usaddress`).

```sh
python tools/review/compare_sample.py local-data/fmcsa-census-2026/records.parquet --provider US          # the plan
python tools/review/compare_sample.py local-data/fmcsa-census-2026/records.parquet --provider US --confirm
python tools/review/server.py local-data/review/queue-compare.jsonl                                         # then review as usual
python tools/review/export.py --table                                                                       # who was right, by label pair
```

Disagreements fall in three classes, queued in this order (the shares are `--silent 0.7` and `--giveup 0.2`; the rest is control):

| Class | Meaning |
|---|---|
| `silent` | doorplate raised no warning and left nothing unplaced, but usaddress reads a part differently: the riskiest |
| `giveup` | doorplate warned or left text unplaced, while usaddress produced a full-looking parse (a house number or box, a place and a state) |
| `control` | the rest of the disagreements |

Within a class the rows are grouped by the pair of labels that differ (doorplate `StreetName`, usaddress
`OccupancyIdentifier`), the biggest groups first, `--per-group` (2) rows each. A class with too few rows gives its quota to the
next. A repeated input is skipped, and so is a string in `--exclude-training FILE` (usaddress's training strings, one per line,
lowercase with whitespace collapsed; `tools/compare/training_overlap.py` fetches them for the test files). The queue stores usaddress's
parse of each row, so the page needs no usaddress. It refuses the benchmark suite, the geocode benchmark and usaddress's test files,
and `--out` must be under `local-data/`.

On the page a comparison row shows doorplate's parse, usaddress's as chips, and the label pairs that differ. The verdicts are `1`
doorplate right, `2` usaddress right, `3` both right (another convention; one verdict, by decision on #132), `4` both wrong (type the
correct string, Enter saves it), `5` can't tell, `6` not an address, `7` source noise, `8` skip. `export.py --table` prints counts by class
and label pair for each verdict (labels and counts only), and the shape-only export keeps the class, the differing label pairs and
usaddress's labels in order, never a token. The "usaddress right" groups become issues through the same loop as #125.

**Limit.** Disagreement finds where the parsers differ, not every place doorplate is wrong: a row both read wrongly in the same
way is not queued. The first queue (FMCSA US carriers, 2026-10-27): of 193,511 distinct sampled strings 5,057 disagree (2.6%), 2,975 silent, 1,754
give-ups and 328 control; the biggest silent groups are `OccupancyIdentifier`/`StreetName`, `PlaceName`/`StreetName` and
`StreetName`/`OccupancyIdentifier`.

## The page (`server.py`)

Binds to `127.0.0.1` only (and refuses requests for another host name), logs no requests, and uses
the doorplate WebAssembly build for parsing, so it needs no network and no Python package. Each card
shows the row as the harness parsed it (colored by component, field by field), the warnings, the key,
and a box that starts as the original joined into one line. Edit the box: it is re-parsed as you
type, and says whether the string parses cleanly and whether it keys the same as the original parse.

**Is the parser current? (#246).** The page parses with the WebAssembly build, which `maturin develop` does not rebuild, so it can fall
behind the source without anyone noticing (the second review ran a build five days old, library `0.3.0`, and 20 of 150 cards showed a
parse that `main` no longer gives). `server.py` compares the build's time with the newest file under `crates/doorplate/src`,
`crates/doorplate/data` and `crates/doorplate-wasm/src` and, when the source is newer, prints a warning at start-up and shows a red
banner on the page with the build command; `--strict` refuses to start instead. The header always shows the parser the page runs
(`parser 0.4.0, key k3`): check it before a queue, and rebuild with `cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release`
(a few seconds when little changed). The check goes by file times, so touching a source file also trips it; rebuilding clears it.

| Key | Verdict | Meaning |
|---|---|---|
| `1` | `right`, warning `fair` | The components are right, and the warning rightly flags something doubtful (a true range, a cut-off line) |
| `2` | `right`, warning `noise` | The components are right and there is nothing to flag |
| `3` or Enter in the box | `corrected` | It is wrong, and the string in the box is a better one |
| `4` | `unclear` | It is wrong, and I can't tell what it should be |
| `5` | `junk` | Not an address (a name, a placeholder, a number) |
| `6` | `noise` | The source cut it off or mangled it |
| `7` | `skip` | Not now |
| `l` | `labeled` | Mark the parts yourself instead of rewriting the string (below) |

A correct parse and a fair warning are separate judgments, so a right parse always says which: a
true range of house numbers is `right` with a `fair` warning; a fine parse with a spurious warning
is `right` with a `noise` warning (a candidate for a warning rule to change, #102).
| `]` and `[` | move words | Move the next word of line 1 to the care-of line, or back one (below) |
| `f` | edit | Jump to the correction box (it is not focused, so the number keys choose a verdict); Escape leaves it |
| `u` | undo | Take back the last answer |

**Move words to the care-of line (`]`, `[`, #222).** About 40 of the 92 corrections in the first review were a retype of the
whole string to move welded leading words (`ZEPHYR HOLDINGS LLC 20 OAK ST` is a name and a street, #127). `]` moves the next word
of line 1 to the care-of line and re-parses the box live; `[` takes one back. If line 2 is a care-of line (it starts with `%`,
`C/O`, `ATTN`) the words are appended to it (`% PAT QUINCE ZEPHYR HOLDINGS LLC`), if there is no line 2 a new `% WORDS` line follows
line 1, and if line 2 is something else (a unit) the care-of part goes between them. Line 1 always keeps at least one word. Edit the
box afterwards as usual, then Enter.

**An unchanged correction (#222).** Two rows in the first review were saved as `corrected` with the box unchanged, meaning "the parse
is right". Saving a correction whose text is the unchanged original now asks first: parse right with the warning fair, parse right with
the warning noise (or, on a comparison row, doorplate right or both right), or "save it as a correction anyway". The server refuses an
unchanged correction unless the request says `unchanged_ok`.

**Marking the parts (`l`, #222).** For a parse that is wrong in a few places, open "Mark the parts instead". The one-line string is
shown as words, each in the part the parser gave it (anything it did not place is `Not placed`). Click a word (Shift-click to
extend), choose a part, press Assign, and Save labels. The answer is `labeled` with `labeled_text` and `labels`: `[{start, end,
component}]`, offsets into `labeled_text`, in order and not overlapping; the components are the page's names (`StreetNumber`,
`StreetName`, `Attention`, ...). The shape-only export keeps the parts and the shape of each (`["StreetNumber", "9"]`), the
full-text export the words. A labeled answer is a labeled string and can later feed `label_score.py` (deferred, see #222).

Answers go to `local-data/review/answers.jsonl`, one object per line: the time, the id, the input, the
shape group, the verdict, the correction and your note, and the parse of the original and of the
correction (key, warnings, components, the doorplate version). The file is append-only (an undo adds
a marker), answered rows are not shown again, and a session can stop and resume.

## The export (`export.py`): what may leave `local-data/`

Writes `local-data/review/shapes.jsonl`: one line per standing answer with every address and note
reduced to its shape (letters `a`, digits `9`, runs collapsed: `% JOHN SMITH` is `% a a`), plus the
verdict, the warning codes, the component names with their value shapes, the shape of the key, whether
the correction parses cleanly and keys the same, the group size, the version and the day. No values,
no record ids, no time of day, and no source name unless `--with-source` (a private source may not be
named). A pair such as `% a a` corrected to `a a` shows a rule without saying whose address it was.
The test (`test_export.py`) checks that nothing but shapes, codes and names comes out.

It is not anonymized text, so it does not replace the anonymizing tool of #105 for sharing a
real-looking row (a later version can use it).

## The full-text export (`export.py --full`): for the maintainer's own session

A shape is often not enough to see a rule: which words were deleted, and what the note says. For the
sources the owner has cleared, `--full` writes `local-data/review/answers-full.md`: the original
lines, the parse, the corrected string and its parse, the note verbatim, and a word-level description
of the edit (`deleted leading "ACME LLC"`). It reads `local-data/review/full-ok.txt`, one source per
line:

```
irs-eo-bmf    mask=line2     # the care-of name field is reduced to its shape
fmcsa-census                 # nothing masked
```

- **Only listed sources are written;** with none listed, nothing is. The default stays shape-only.
- **`mask=`** names input fields (`line1`, `line2`, `city`, `state`, `zip`, `last_line`) whose words become
  their shape everywhere in that row's entry: the lines, the parse, the correction, the note and the edit
  description. Words that also appear in an unmasked field (`SMITH` in a street name), and address
  vocabulary (`C/O`, `ATTN`, `PO BOX`, `APT`), are kept, so a street line and a care-of marker stay
  readable while a name does not.
- **It stays in `local-data/`:** the command refuses an output path outside it. Reading the file in a
  Claude Code session sends its text to the model provider, which is why it is an exception to
  `docs/data-policy.md` and why each source is cleared by hand.
- **Write-back stays shapes:** what is learned goes into issues, pull requests and docs as counts,
  shapes and invented examples.

## What it is not

Nothing is trained on the answers. A person's opinion of "the same door" is a lead, not ground truth.
A rule found this way still needs a source (`docs/usps-pub28-notes.md`), a golden-corpus case with an
invented address and a before and after harness run (the rule-PR loop in `docs/tools/harness.md`).
This library formats and parses; it does not validate that an address exists or can receive mail.

## Later

Using #105 so real-looking rows can be shared, and feeding the answers to `label_score.py` as a labeled
source (both #222).
