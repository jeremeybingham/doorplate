# Rule firing counts

A research tool for the rule audit (#401): which tagger and tokenizer rules fire, how often, and in how many inputs. It is a cargo
feature that is off by default (`rule-stats`), so a normal build, the wheels and the crate are unchanged. The counts are of call
sites, not of rules by name: every `self.set(...)`, `self.warn(...)` and `self.decide(...)` of the tagger is recorded with the file and
line of its caller (`#[track_caller]`), and the tokenizer's post-passes and readings by name.

```
cargo run --release -p doorplate --features rule-stats --example rule_stats -- INPUTS > run.tsv
python tools/rules/rule_stats.py run.tsv [more.tsv ...] [--rare N]
```

`INPUTS` holds one input per line: a one-line address, or five tab-separated fields (line 1, line 2, city, state, ZIP) for
`parse_fields`. The report merges runs, scans the tagger source for every call site, and lists the sites that never fired, the tokenizer
rules that did, and the sites that fired in at most N inputs. Output is counts and source lines; no input text.

A site that never fires in a run is not yet a dead rule: it is a candidate for the deletion check (disable it alone, then run the
golden corpus, `passing.txt` and the key diff against the frozen keys). Read the result against the data the run covered: the corpus
and the suite's inputs cover the rules that have a test; the key sources show which rules matter on real addresses.

## Over the key sources

`tools/rules/run_sources.py` runs the same count over the records files of the key comparison (`local-data/keycompare/sources.txt`): it parses
a random sample (default 2,000,000 rows per source, a fixed seed; `--sample 0` for every row) with `parse_fields` on one thread and writes one TSV per
source into `OUTDIR`, which `rule_stats.py` merges with the others. The extension must be built with the feature, in a venv of its own so the
other tools keep the normal build:

```
uv venv /tmp/venv-rs && uv pip install -p /tmp/venv-rs/bin/python maturin duckdb pyarrow
(cd crates/doorplate-py && VIRTUAL_ENV=/tmp/venv-rs PATH=/tmp/venv-rs/bin:$PATH maturin develop --release --features rule-stats)
/tmp/venv-rs/bin/python -I tools/rules/run_sources.py local-data/rule-stats/sample2m
```

The sample of 2,000,000 rows covers four of the seven sources whole (IRS, Netsyms, the amateur radio file and NAD have fewer rows) and takes about 15 minutes.
Only counts are written. The records are fields, so this exercises the pre-split path; the one-line path is covered by the corpus and the suite.

`--oneline` joins each row's fields into one line (`line 1, line 2, city, state ZIP`) and uses `parse()`, so the one-line paths (the last line read
from the right) run on real text; `--default-state XX` parses under that default state with the state and ZIP left out, which is the only way the
default-state rules run.

