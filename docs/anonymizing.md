# Anonymizing address data for sharing

`doorplate anonymize` (the command), `doorplate.Anonymizer` (Python) and `doorplate::Anonymizer` (Rust) rewrite
address-like text so it can go into a bug report, an issue or a test case: the digits and the names change, and the
shape stays. It was added in 0.4.x (issue #105). This library formats and parses; it does not validate that an address
exists or can receive mail, and the anonymizer does not make a real address safe: **it is obfuscation that keeps the
shape, not anonymity.** Read the output before you share it.

Contents: [Why it exists](#why-it-exists) · [What changes and what stays](#what-changes-and-what-stays) ·
[Using it](#using-it) · [Columns, lines and files](#columns-lines-and-files) · [Seeds and consistency](#seeds-and-consistency) ·
[The faithfulness check](#the-faithfulness-check) · [Limits: what it can leak](#limits-what-it-can-leak) ·
[Before you share](#before-you-share) · [How well it works](#how-well-it-works) · [Decisions](#decisions) ·
[Related pages](#related-pages)

## Why it exists

The most useful thing anyone can send this project is real, messy addresses ([`roadmap.md`](roadmap.md)), and
[`CONTRIBUTING.md`](../CONTRIBUTING.md) ("Sharing messy data") asks people to anonymize private data first: keep the
*shape*, swap the names and numbers. Doing that by hand is slow and easy to get wrong, so people send less, or send
something that still identifies someone. The tool does the mechanical part, and it works on lines that do not parse,
which are the lines you most want to report.

It is not the benchmark suite's anonymization ([`benchmark-suite.md`](benchmark-suite.md), "Anonymization"). That one
works on labeled, split NAD fields and keeps only common streets. This one works token by token on raw text, with no
parse needed, and keeps what decides how the parser reads a line.

## What changes and what stays

| Part of the text | What happens |
|---|---|
| A run of digits (`123`, `4417`, `0042`) | Other digits of the same length. Never equal to the original. A first digit that was not zero stays non-zero; leading zeros stay |
| A hyphenated number (`41-20`) | Each run changes alone, the hyphen stays: `24-39` |
| A letter next to a number (`12A`, `#4B`) | The digits change, the letter stays (a lone letter always stays) |
| An ordinal (`5TH`, `22ND`) | A new number and the ordinal suffix that fits it (`8TH`, `31ST`) |
| A fraction (`1/2`, `3/4`) | Stays (a single digit either side of a `/`) |
| A word the lexicons know: street suffixes (`ST`, `AVENUE`, `HOLLOW`), directionals, unit designators (`APT`, `STE`), states, `PO BOX`, `RR`, `GENERAL DELIVERY`, highway prefixes, military forms | Stays, in any spelling the lexicon recognizes |
| Any other word of two letters or more (street names, people, businesses, `ATTN` lines, `LLC`) | An invented pronounceable word of the same length and the same case pattern (`Zephyrmill` becomes `Hadujapigu`). Never a lexicon word, never the original |
| The city and state the parser finds in the text | Stay. The city stays only when the parse found a state or a matched place; on a bare street line a guessed "city" is replaced |
| A ZIP the parser finds | The first three digits stay; the last two change. A ZIP+4 extension changes entirely |
| Punctuation, spacing, case, line breaks | Stay. The output has the same number of characters as the input |

An example, with a fixed seed (all invented):

```text
$ doorplate anonymize --seed 7 < messy.txt
123 N Zephyrmill Ave Apt 4, Miami, FL 33101          ->  316 N Hadujapigu Ave Apt 3, Miami, FL 33116
PO Box 1234, Austin, TX 78701                         ->  PO Box 9070, Austin, TX 78775
RR 2 Box 15, Dalton, GA 30720                         ->  RR 7 Box 24, Dalton, GA 30739
ATTN Pat Quinn, 88 Bayview Dr Ste 200                 ->  ATTN Vup Talul, 98 Mivodig Dr Ste 529
41-20 Bayview Ave, Flushing NY 11355                  ->  24-39 Mivodig Ave, Flushing NY 11395
9120 Oak Hollow County Road 7                         ->  7812 Fir Hollow County Road 4
1/2 Pelican Way #12B                                  ->  1/2 Tutewes Way #30B
412 5th St, Marigold Holdings LLC                     ->  556 8th St, Bufarobu Wotihicu HOJ
```

(The left column is the input and the right column is the output; the tool prints only the right column.) Three
things to notice: `Bayview` became `Mivodig` in both lines that had it (the same value gets the same replacement);
`Hollow` stayed because it is a street suffix in the lexicon; and in the last line `LLC` became `HOJ`, which the parser
no longer reads as it read `LLC`, so that value is reported as not faithful.

## Using it

### Command line

```sh
doorplate anonymize - < lines.txt                       # one value per line, from standard input
doorplate anonymize in.csv --column address -o out.csv  # the named column(s) of a CSV file
doorplate anonymize in.csv --column line1 --column line2 --column zip --seed 7 -o shareable.csv
```

| Option | Meaning |
|---|---|
| `-` or no file | Read standard input, one value per line; write the anonymized lines to standard output |
| `IN.csv --column NAME` | Anonymize that column; repeat `--column` for several. Every other column is copied unchanged. A `--column` is required for a file, and not allowed for standard input |
| `-o OUT` | Write to a file instead of standard output |
| `--seed N` | A whole number: the same seed gives the same output (see [Seeds](#seeds-and-consistency)). Without it the seed is random |

Standard error gets a summary: how many values were anonymized and how many the parser reads the same way afterwards,
plus the reminder that this is obfuscation. Blank values are copied and not counted. Line endings in text input come
out as `\n`. Errors say what went wrong and never quote a row (a CSV error can name one): `could not read a row of
FILE`, `--column: no column named "x" in FILE`. Exit codes are those of the other commands: 0 success, 1 a usage error,
2 an input that could not be used.

### Python

```python
import doorplate

a = doorplate.Anonymizer(seed=7)              # seed=None picks a random one; a.seed reads it back
r = a.anonymize("123 N Zephyrmill Ave Apt 4, Miami, FL 33101")
r.text        # '316 N Hadujapigu Ave Apt 3, Miami, FL 33116'
r.faithful    # True: the parser reads it the same way

rows = a.anonymize_many(lines)                # a list of Anonymized, in order; releases the GIL
shareable = [r.text for r in rows]

doorplate.anonymize("55 Bayview Dr")          # just the text, with a new random seed each call
```

`Anonymized` has `text` and `faithful`; its `repr` hides the text, so a log line or a notebook cell does not print it. With
pandas, anonymize the columns you need and keep the rest (`anonymize_many` wants a list of strings, so fill missing
values first):

```python
a = doorplate.Anonymizer(seed=7)
for col in ("line1", "line2", "zip"):
    df[col] = [r.text for r in a.anonymize_many(df[col].fillna("").astype(str).tolist())]
```

A runnable version is [`examples/anonymize_example.py`](../examples/anonymize_example.py), and the
[notebook](../examples/quickstart.ipynb) has a section on it.

### Rust

```rust
let a = doorplate::Anonymizer::with_seed(7);          // Anonymizer::new() picks a random seed
let r = a.anonymize("123 N Zephyrmill Ave Apt 4, Miami, FL 33101");
assert!(r.text.contains(" N ") && r.text.contains(", FL 331") && !r.text.contains("Zephyrmill"));
println!("{} (parser reads it the same: {})", r.text, r.faithful);
```

`Anonymized` is `#[non_exhaustive]` (read its fields; do not build one). The anonymizer holds a parser, so build it once
and reuse it.

## Columns, lines and files

The unit of work is one text value. Each value is anonymized on its own, so:

- **Several columns** (`--column owner --column line1 --column line2`) work, and a word that appears in two columns gets
  the same replacement in both (`ATTN Pat Quinn` on line 2 and `Pat Quinn` in an owner column match), so a join or a
  duplicate check on the output still works.
- **Text with line breaks** in one cell (`9 Willow Way` / `Suite 12`) is one value; the breaks stay.
- **Separate address columns.** Each cell is parsed alone, without its neighbours. A state column stays (`FL` is a
  state). A ZIP column keeps its first three digits. A bare **city** column is replaced, because with no state beside it
  the text cannot be told from a street name: leave a city column out of `--column` to keep it.
- **Several addresses in one cell, or free text around an address** are handled word by word, with no parse needed.
- The `faithful` figure for a name or city column on its own is not informative (a bare name parses as whatever it
  parses as); read it for whole-address columns.

## Seeds and consistency

The replacement of a value comes from a keyed hash of the seed and the value, so within one seed **the same value always
gets the same replacement** (case-insensitively for words, so `BAYVIEW` and `Bayview` change to the same letters in
their own case). Duplicates stay duplicates, and a dedupe or key test on the output behaves like one on the input.

The default seed is random for every run (the operating system's randomness, the clock and a counter), so nobody can
recompute your replacements from a guess at the input. **A seed you publish lets anyone test a guess**: they run the
tool with your seed on the guessed text and compare. Use `--seed` for a repeatable test file that holds only invented or
already-public text, and leave it out when you are sharing real data. The mapping does not depend on the standard library's hashers, so it is the same on every platform for one version of
the tool; a later version may add rules, so do not rely on it across versions.

## The faithfulness check

Each value is parsed before and after, and `faithful` says whether the parser reads them alike: the same address type,
the same warnings, the same suffix, directionals, unit designators, state and city, a ZIP of the same length, and the same
*shape* (letters `a`, digits `9`, runs collapsed) for the street number, street name, unit number, PO box, attention
line and leftover text. A value that did not parse before and does not after counts as faithful; one that parsed before
and not after, or the reverse, does not. The CLI prints the share; Python and Rust give it per value.

`faithful` is the answer to "will a bug I saw in the original still show up in the copy?" It is a good sign, not a
proof: it compares what doorplate sees, and a different tool could read the two differently.

## Limits: what it can leak

The tool says what it keeps because those are the places it can fail you:

- **Lexicon words stay.** A street called `PARK`, `HARBOR`, `SUMMIT` or `HOLLOW`, or a person named `Lane` or `Fairfield`
  where the word is a suffix, stays as written. The same holds for a name that is also a state code or a unit
  designator.
- **The city and the state stay**, and so do the first three digits of a ZIP. Together with a rare street shape that can
  narrow a record to a small area.
- **A name in free text that the lexicons happen to know stays.** Names the lexicons do not know are replaced, but
  the tool cannot tell a name from any other word it does not know, and it does not know what is sensitive in your data.
- **A trailing country word is replaced.** `USA` at the end of a line is not a lexicon word, so it changes to an invented
  word, and the parser then reads the copy differently (reported as not faithful). Remove or keep such a word by hand.
- **Single letters stay** (`C/O`, an initial, a unit letter), and short numbers that look like fractions.
- **Structure stays.** The length of every word, the order of the parts, the typos, the case and the punctuation are the
  originals. A distinctive format (a typo that only one office makes) can identify its source.
- **It is not reversible by design, but a published seed can be attacked.** See [Seeds](#seeds-and-consistency).
- **It does not understand meaning.** An invented word can, by chance, be an ordinary or an unpleasant word; the check
  against the lexicons only keeps it from being one of the parser's words.

## Before you share

1. Run it without `--seed`, so the replacements cannot be recomputed.
2. **Read the output.** Look at every line that still has a word you do not expect to see (`grep` for the names you know
   are in the file), and at the lines reported as not faithful.
3. Remove lines you cannot make safe, or reduce them to shapes (`doorplate`'s own warning codes and counts are fine to share).
4. Share a small sample, not the file. Ten faithful lines that show the problem are worth more than ten thousand.
5. If it is still too close to real data, describe the shapes in words and send counts instead
   ([`CONTRIBUTING.md`](../CONTRIBUTING.md), "Sharing messy data").

For the project's own use of private data (what may be committed, what may be said) see [`data-policy.md`](data-policy.md):
this tool is for people sharing *their* data with us, and it does not change that policy. Examples in issues and docs are
still invented.

## How well it works

Measured on 2026-10-27 with `doorplate anonymize --seed 1` on samples of the local sources
(the maintainer's private `local-data/`, which is not in the repository; the numbers are counts and rates).
"Same" is the share of values the parser reads the same afterwards.

**Street lines (line 1), 100,000 values per source:** the parser reads the output the same as the input for
CA unclaimed 96.7%, NY corporations 97.2%, Netsyms 98.3%, carrier census 99.6%, IRS 99.6%, Texas TDLR 99.8%, NC voter
99.9%, FCC amateur 99.9% and NAD 99.9%. No digit run stayed as it was except single-digit fractions.

**Line 2 (sampled values), eight sources:** IRS 100.0% (64,097 values), FCC 99.9% (2,033), Netsyms 99.6% (23,485), Texas
TDLR 99.6% (9,221), NY corporations 98.7% (24,094), CA unclaimed 94.9% (10,437), NAD 94.2% (15,555), NC voter 80.9% (533,
a small sample). No digit run stayed.

**What stays, by words of two letters or more.** On line 2, 32% of such words stayed overall: 4% in the IRS file, where line 2
is mostly names, and 82 to 90% in NAD, Netsyms and NY corporations, where it is mostly unit words. Twenty-three words
(`APT`, `SUITE`, `STE`, `UNIT`, `BOX`, `PO`, `FLOOR`, `AVE`, `ST`, ...) make up 82% of what stays; the other 18% is 13,397
occurrences of 1,112 distinct lexicon words, which are the ones that could be a name. On street lines, more than half the
words stayed (54% to 67% by source, measured before the final city fix, which lowered it slightly), nearly all suffixes,
directionals, cities and states.

**Speed:** about 100,000 values in 2.2 seconds on one machine, including the parse before and after.

**Not measured:** personal-name columns (the local record files keep only ids and address columns), and any text that is
not an address. These numbers are for US addresses in the formats the sources use; yours may differ, which is what the
check on your own file is for.

## Decisions

Open to overruling; the table with the reasons is in [`api-surface.md`](api-surface.md) ("Added in 0.4.x: the
anonymizer").

- It is a public API in the core, the Python package and the command line (the owner's choice, 2026-10-27).
- Replacement words are invented pronounceable words (consonant, vowel, ...), never a lexicon word.
- The same value gets the same replacement for a seed; the default seed is random per run.
- Free text is strict: every word of two letters or more that is not a lexicon word is replaced.
- The city and the first three ZIP digits stay; no swap within the state (it would need place data for every state and
  would change the city/street split the parser makes).

## Related pages

- [`CONTRIBUTING.md`](../CONTRIBUTING.md), "Sharing messy data": what to send and how.
- [`data-policy.md`](data-policy.md): what data the project uses and what may leave `local-data/`.
- [`benchmark-suite.md`](benchmark-suite.md), "Anonymization": the other procedure, for labeled NAD rows.
- [`api-surface.md`](api-surface.md): the names, and the decisions.
- [`examples/anonymize_example.py`](../examples/anonymize_example.py) and the [notebook](../examples/quickstart.ipynb).
- [`CHANGELOG.md`](../CHANGELOG.md).
