# Review: a person looks at the hard addresses

Issue #122. A harness run tells us which shapes of address fail (`tools/harness/shapes_report.py`),
and an invented address can reproduce each one. It cannot tell us what the **right answer** is for a
messy real row; a person can. This tool shows one hard row at a time and records what the person
says, so the answers can be read later for new shapes and rules. Read `docs/data-policy.md` first:
the queue and the answers hold real addresses and stay in `local-data/`.

**Which queue to build: the comparison queue by default.** A flagged queue (`sample.py`) holds only rows doorplate already
flagged, so it cannot show a row doorplate got wrong and passed without a warning. The comparison queue (`compare_sample.py`) samples rows at
random and queues the ones where usaddress reads the string differently, silent ones first, so it finds those, and its give-up class
covers most of what a flagged queue would show. In the FCC round (#225), 43 of the 105 silent rows were real misses with no warning. Use a
flagged queue only for a stated reason (for example, a source where usaddress does poorly), and say so on #225. Before building a queue for a
source, read the "quirks" in its `INVENTORY.md` and choose roles to match (the NY corporations' CEO line 1 is a person's name, so that role is
left out). Take the roles one at a time with `--role` and merge the pieces if one queue should mix them.

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
correct string, Enter saves it), `5` can't tell, `6` not an address, `9` dual, `o` foreign address, `p` Puerto Rico (the full list is in the table below). `export.py --table` prints counts by class
and label pair for each verdict (labels and counts only), and the shape-only export keeps the class, the differing label pairs and
usaddress's labels in order, never a token. The "usaddress right" groups become issues through the same loop as #125.

**Limit.** Disagreement finds where the parsers differ, not every place doorplate is wrong: a row both read wrongly in the same
way is not queued. The first queue (FMCSA US carriers): of 193,511 distinct sampled strings 5,057 disagree (2.6%), 2,975 silent, 1,754
give-ups and 328 control; the biggest silent groups are `OccupancyIdentifier`/`StreetName`, `PlaceName`/`StreetName` and
`StreetName`/`OccupancyIdentifier`.

## The precision queue (`probe_queue.py`): how many of a probe's matches are wrong?

A probe counts a text shape, which is an upper bound; the unsampled scan (`probe_scan.py`, [harness](harness.md)) counts it exactly and keeps the identity of each match.
`tools/review/probe_queue.py SCAN_DIR INPUTS.txt --probe NAME [--probe NAME ...] [--n 50] --confirm` turns those matches into one comparison queue per probe
(`local-data/review/probe-queues/queue-NAME.jsonl`), reading the text back from the input by `record_id`. The sample is the matches with the lowest `rk`, a random
draw, taken in turns across the sources with no source above 40% of the queue, so a large source cannot fill it; every card names its source, so a precision
is weighted back by the probe's matches per source (the scan's `counts/`). Rows where usaddress agrees stay in (a precision needs them); rows that look like
Puerto Rico and rows whose id is in an earlier review (`--exclude-answers`) are left out. Review it like any comparison queue, with its own answers file:
`server.py local-data/review/probe-queues/queue-NAME.jsonl --answers local-data/review/answers-probe-NAME.jsonl`. `rows x precision` is the number that
orders the issues ([backlog](../backlog.md)).

## The page (`server.py`)

Binds to `127.0.0.1` only (and refuses requests for another host name), logs no requests, and uses
the doorplate WebAssembly build for parsing, so it needs no network and no Python package. Each card
shows the original row as one line that never changes (with a Copy button), then how doorplate read it as a horizontal line of chips like
usaddress's below it (colored by component; for a row of separate fields a bar separates the fields), the warnings, the key,
and a box that starts as the original joined into one line (**Reset**, key `r`, puts the original back).
A row of separate fields is parsed as fields at the top but as one line in the box and in the usaddress comparison, and the two can
differ (#294); when the keys differ the card shows the one-line reading too. Edit the box: it is re-parsed as you
type, and says whether the string parses cleanly and whether it keys the same as the original parse.

**Is the parser current? (#246).** The page parses with the WebAssembly build, which `maturin develop` does not rebuild, so it can fall
behind the source without anyone noticing (the second review ran a build five days old, library `0.3.0`, and 20 of 150 cards showed a
parse that `main` no longer gives). `server.py` compares the build's time with the newest file under `crates/doorplate/src`,
`crates/doorplate/data` and `crates/doorplate-wasm/src` and, when the source is newer, prints a warning at start-up and shows a red
banner on the page with the build command; `--strict` refuses to start instead. The header always shows the parser the page runs
(`parser 0.5.0, key k4`): check it before a queue, and rebuild with `cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release`
(a few seconds when little changed). The check goes by file times, so touching a source file also trips it; rebuilding clears it.

| Key | Verdict | Meaning |
|---|---|---|
| `1` | `right`, warning `fair` | The components are right, and the warning rightly flags something doubtful (a true range, a cut-off line) |
| `2` | `right`, warning `noise` | The components are right and there is nothing to flag |
| `3` or Enter in the box | `corrected` | It is wrong, and the string in the box is a better one |
| `4` | `unclear` | It is wrong, and I can't tell what it should be |
| `5` | `junk` | Not an address (a name, a placeholder, a number) |
| `0` (comparison queue) | `usaddress_right` with a correction | usaddress's reading was right, and there is also a better string for doorplate: both are kept, and it is scored as `usaddress_right` |
| `o` | `foreign` | Not a US address (another country) |
| `p` | `puerto_rico` | A Puerto Rico address. The row is also copied, in queue format, to `puerto-rico-queue.jsonl` beside the answers (`--pr-queue` to change it), the queue for the Puerto Rico epic (#332); an undo takes it out again, and a row is copied once |
| `8` (`9` in a comparison queue) | `dual` | The row holds a dual or multiple address (a street and a PO Box, or several): a different signal from `junk` |
| `i` | `insufficient` | Some valid address parts, but wrong, extra or odd text around them, and not enough to put together one door (checked, for example, on a map: the real address could not be reached from what the row says). Not `junk` (no address at all), not `noise` (cut off by the source), not `unclear` (the reviewer can't tell the fix) |
| `m` | `map_checked` | You looked the row up on a real map and it is understandable but no rule can fix it (a misspelled street name that collides with a suffix, numbers out of order that no logic can parse). Saves the current labels (the button is in "Mark the parts instead", with a reason: `name_suffix`, `numbers_out_of_order` or `other`; labels are optional in the data) and your note. Scored as neither right nor wrong: these rows are evidence for what **cannot** be a rule |
| `t` | (no answer) | "Try these labels": builds fields from the current labels (street parts to line 1, units to line 2, city, state, ZIP), parses them and shows the chips, warnings, key and the Pub 28 lines, with whether the key equals the original parse's |
| `l` | `labeled` | Jump to "Mark the parts instead" (always on the page), to mark the parts yourself instead of rewriting the string (below) |
| `y` (comparison queue) | `labeled`, `usaddress_right` set | Save the labels as they stand and record that usaddress was right too (below) |

A correct parse and a fair warning are separate judgments, so a right parse always says which: a
true range of house numbers is `right` with a `fair` warning; a fine parse with a spurious warning
is `right` with a `noise` warning (a candidate for a warning rule to change, #102).
| `f` | edit | Jump to the correction box (it is not focused, so the number keys choose a verdict); Escape leaves it |
| `r` | reset | Put the original one-line string back in the correction box |
| `u` | undo | Take back the last answer |

**A rule queue (#524).** `rule_queue.py` builds a queue of the rows one rule decides: it runs the `rule_disable` example (the rule-stats build, `docs/tools/rule-stats.md`) over a sample file of `source, line 1, line 2, city, state, ZIP` rows with nothing disabled and again with `DOORPLATE_DISABLE` naming the rule's tagger call sites, keeps the rows whose key, warnings or unparsed text change, and draws `--n` of them in turns across the sources. The card shows doorplate as it reads the row now and, under it, the reading without the rule. The verdicts are `1` right with the rule (`rule_right`), `2` right without it (`rule_off_right`), `3` both right, `4` both wrong (with a correction), `5` I can't tell, `6` not an address, `9` dual, and `i`, `o`, `p`, `m` as always. `python tools/review/rule_queue.py --name NAME --score` prints the verdict counts and the share of the changed sample rows where the reading without the rule is right, weighted by source (each card carries how many sample rows the rule changed in each source). That share times the rows the rule touches is what a wrong decision costs. The sample is a hash-ordered draw, not row order; a source with many changed rows (the IRS file for care-of lines) dominates the weighted share, so read the per-source counts.

**On a letter.** Under the correction box an "On a letter" card draws an envelope for each reading, with the Pub 28 delivery lines (`usps.line1`, `line2`, last line) where they would be printed and a placeholder name line: doorplate's reading of the row, the string in the correction box (when its key differs from the original's) and the current labels (after "Try these labels"). The lines are the library's output; the card does not check that the address exists.

**Nothing you type is dropped.** The note is saved with every verdict. Text left in the correction box under a verdict that is not a correction
(for example "I can't tell" on a row you could not fix, or "usaddress right" after you had typed a better string) is saved as `draft`, with
`draft_parse` (the page's parse of it), when it differs from the original. A draft is never scored as a correction: `corrected` is only set by
`corrected` and `both_wrong`. The shape-only export shows a draft as a shape with whether it parses cleanly and keys the same
(`draft`, `draft_warnings`, `draft_clean`, `draft_same_key`), and the full-text export prints it on its own line,
"draft (an attempt, not saved as a correction)". Answers made before this change have no `draft`.

**An unchanged correction (#222).** Two rows in the first review were saved as `corrected` with the box unchanged, meaning "the parse
is right". Saving a correction whose text is the unchanged original now asks first: parse right with the warning fair, parse right with
the warning noise (or, on a comparison row, doorplate right or both right), or "save it as a correction anyway". The server refuses an
unchanged correction unless the request says `unchanged_ok`.

**Marking the parts (`l`, #222).** For a parse that is wrong in a few places, use the "Mark the parts instead" section (always shown). The one-line string is
shown as words, each in the part the parser gave it (anything it did not place is `Not placed`). Click a word (Shift-click to
extend), choose a part, press Assign, and Save labels. The answer is `labeled` with `labeled_text` and `labels`: `[{start, end,
component}]`, offsets into `labeled_text`, in order and not overlapping; the components are the page's names (`StreetNumber`,
`StreetName`, `Attention`, ...). The shape-only export keeps the parts and the shape of each (`["StreetNumber", "9"]`), the
full-text export the words. A labeled answer is a labeled string and can later feed `label_score.py` (deferred, see #222).

**Labels, and usaddress was right too (`y`, #461).** On a comparison card, some rows cannot be fixed in the correction box: usaddress puts a
missed unit designator or a building name in the right slot and doorplate does not, and no one-line string says so. The panel then has a
second button, **Save labels, usaddress right too**, with a choice of how right: *basically right* (`"mostly"`, one part differs) or *fully
right* (`"full"`, its whole reading equals your labels). The answer is the same `labeled` answer with `usaddress_right: "mostly"` or `"full"`; the
server accepts the field only on a `labeled` answer to a comparison row, and an old answer or a plain **Save labels** has no field and claims
nothing about usaddress. The comparison table (`export.py`) counts such a row under *usaddress right* (so the shape group shows that usaddress
won there) and the answer is still a labeled string for everything else; the shape-only export keeps the grade and the shapes of the labels,
never a word, and the full-text export heads the entry `labeled (usaddress right: mostly)`. Press `y` to save with the grade chosen in the list.

Answers go to `local-data/review/answers.jsonl`, one object per line: the time, the id, the input, the
shape group, the verdict, the correction and your note, and the parse of the original and of the
correction (key, warnings, components, spans, the doorplate version). For the later machine read each answer also keeps: `original_line`
(the row as one line), `oneline_parse` (the parse of that line, beside `parse`, the parse as the harness read the row), `attempts` (up to
ten strings tried in the box, each with its key, warnings and whether it parsed cleanly, so abandoned attempts are not lost), `elapsed_ms` on
the card and, on a `labeled` answer, `parser_labels` (what the parser gave before you changed it). The full-text export prints the
one-line parse when it differs and each attempt. `noise` and `skip` are no longer offered; older answers keep them. The notes row keeps the last 20 notes. The file is append-only (an undo adds
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
real-looking row; the `anon` option of the full-text export (below) uses it for a source of private people.

## The full-text export (`export.py --full`): for the maintainer's own session

A shape is often not enough to see a rule: which words were deleted, and what the note says. For the
sources listed in `full-ok.txt` (now every ingested source: all are public records, `docs/data-policy.md`), `--full` writes `local-data/review/answers-full.md`: the original
lines, the parse, the corrected string and its parse, the note verbatim, and a word-level description
of the edit (`deleted leading "ACME LLC"`). It reads `local-data/review/full-ok.txt`, one source per
line:

```
irs-eo-bmf    mask=line2     # the care-of name field is reduced to its shape
fmcsa-census                 # nothing masked
nc-voter-current anon keep=CPO,CPU,UNX   # private people's addresses: every word replaced, these kept
```

- **Only listed sources are written;** with none listed, nothing is. The default stays shape-only. The owner has listed every
  ingested source; `mask=` and `anon` below remain available, and are no longer needed for the sources already listed.
- **`mask=`** names input fields (`line1`, `line2`, `city`, `state`, `zip`, `last_line`) whose words become
  their shape everywhere in that row's entry: the lines, the parse, the correction, the note and the edit
  description. Words that also appear in an unmasked field (`SMITH` in a street name), and address
  vocabulary (`C/O`, `ATTN`, `PO BOX`, `APT`), are kept, so a street line and a care-of marker stay
  readable while a name does not.
- **`anon`** (with an optional `keep=WORD,WORD`) is for a source whose lines hold private people's addresses and
  names in places we cannot predict, such as the NC voter file's mailing lines (#225). Each row is parsed as
  it is, then shown after `doorplate anonymize` (`docs/anonymizing.md`): street, unit and name words become invented
  words of the same shape, house numbers change, a ZIP keeps its first three digits, and the city and state stay. The
  replacement is the same in the lines, the parse, the correction, the note and the edit description, and
  comes from a random seed for each export. Address vocabulary and the `keep` words stay as written, so the
  words a review is about (`CPO`, `UNX`) stay readable; the parse is the real one, so a rule is seen as it
  behaved. Limits are the anonymizer's (`docs/anonymizing.md`, "Limits"): a name that is also a lexicon word
  (`Lane`, `Hill`) stays, and the city and state remain. It needs the `doorplate` Python package.
- **It stays in `local-data/`:** the command refuses an output path outside it. Reading the file in a
  Claude Code session sends its text to the model provider, which is why the transcript is not shared unedited
  (`docs/data-policy.md`, principle 4).
- **Write-back stays shapes, always:** what is learned goes into issues, pull requests and docs as counts,
  shapes and invented examples. Nothing from a real row or a note that quotes one reaches the repository,
  an issue or a comment.

## What it is not

Nothing is trained on the answers. A person's opinion of "the same door" is a lead, not ground truth.
A rule found this way still needs a source (`docs/usps-pub28-notes.md`), a golden-corpus case with an
invented address and a before and after harness run (the rule-PR loop in `docs/tools/harness.md`).
This library formats and parses; it does not validate that an address exists or can receive mail.

## Later

Using #105 so real-looking rows can be shared, and feeding the answers to `label_score.py` as a labeled
source (both #222).
