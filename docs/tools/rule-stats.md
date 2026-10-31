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
