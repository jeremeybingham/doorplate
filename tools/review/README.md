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

## The page (`server.py`)

Binds to `127.0.0.1` only (and refuses requests for another host name), logs no requests, and uses
the doorplate WebAssembly build for parsing, so it needs no network and no Python package. Each card
shows the row as the harness parsed it (colored by component, field by field), the warnings, the key,
and a box that starts as the original joined into one line. Edit the box: it is re-parsed as you
type, and says whether the string parses cleanly and whether it keys the same as the original parse.

| Key | Verdict | Meaning |
|---|---|---|
| `1` | `right` | The parse is right; the warning was noise |
| `2` or Enter in the box | `corrected` | It is wrong, and the string in the box is a better one |
| `3` | `unclear` | It is wrong, and I can't tell what it should be |
| `4` | `junk` | Not an address (a name, a placeholder, a number) |
| `5` | `noise` | The source cut it off or mangled it |
| `6` | `skip` | Not now |
| `u` | undo | Take back the last answer |

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

## What it is not

Nothing is trained on the answers. A person's opinion of "the same door" is a lead, not ground truth.
A rule found this way still needs a source (`docs/usps-pub28-notes.md`), a golden-corpus case with an
invented address and a before and after harness run (the rule-PR loop in `tools/harness/README.md`).
This library formats and parses; it does not validate that an address exists or can receive mail.

## Later

Marking the parts of the string and assigning components (a more precise label than a rewrite), using
#105 so real-looking rows can be shared, feeding the answers to `label_score.py` as a labeled source.
