# Anonymizing address data for sharing

`doorplate anonymize` (the command), `doorplate.Anonymizer` (Python) and `doorplate::Anonymizer` (Rust) rewrite
address-like text so it can go into a bug report, an issue or a test case: the digits and the names change, and the
shape stays. This is obfuscation that keeps the shape, **not anonymity**. Read the output before you share it.

The most useful thing anyone can send this project is real, messy addresses ([`roadmap.md`](roadmap.md)), and
[`CONTRIBUTING.md`](../CONTRIBUTING.md) ("Sharing messy data") asks people to anonymize first: keep the *shape*, swap the
names and numbers. By hand that is slow and easy to get wrong. The tool does the mechanical part, and it works on lines
that do not parse, which are the lines you most want to report. (The benchmark suite has its own procedure for labeled
NAD rows: [`benchmark-suite.md`](benchmark-suite.md), "Anonymization".)

Contents: [What changes and what stays](#what-changes-and-what-stays) · [Using it](#using-it) ·
[Columns, lines and files](#columns-lines-and-files) · [Seeds and consistency](#seeds-and-consistency) ·
[The faithfulness check](#the-faithfulness-check) · [Limits: what it can leak](#limits-what-it-can-leak)

## What changes and what stays

| Part of the text | What happens |
|---|---|
| A run of digits (`123`, `4417`, `0042`) | Other digits of the same length. Never equal to the original. A first digit that was not zero stays non-zero; leading zeros stay |
| A hyphenated number (`41-20`) | Each run changes alone, the hyphen stays: `24-39` |
| A letter next to a number (`12A`, `#4B`) | The digits change, the letter stays (a lone letter always stays) |
| An ordinal (`5TH`, `22ND`) | A new number and the ordinal suffix that fits it (`8TH`, `31ST`) |
| A fraction (`1/2`, `3/4`) | Stays (a single digit either side of a `/`) |
| A word the lexicons know: street suffixes (`ST`, `AVENUE`, `HOLLOW`), directionals, unit designators (`APT`, `STE`), states, `PO BOX`, `RR`, `GENERAL DELIVERY`, highway prefixes, military forms | Stays, in any spelling the lexicon recognizes |
| Any other word of two letters or more (street names, people, businesses, `ATTN` lines, `LLC`) | An invented pronounceable word of the same length and case pattern (`Zephyrmill` becomes `Hadujapigu`). Never a lexicon word, never the original |
| The city and state the parser finds | Stay. The city stays only when the parse found a state or a matched place; on a bare street line a guessed "city" is replaced |
| A ZIP the parser finds | The first three digits stay; the last two change. A ZIP+4 extension changes entirely |
| Punctuation, spacing, case, line breaks | Stay. The output has the same number of characters as the input |

An example, with a fixed seed (all invented; the left column is the input, and the tool prints only the right column):

```text
$ doorplate anonymize --seed 7 < messy.txt
123 N Zephyrmill Ave Apt 4, Miami, FL 33101          ->  316 N Hadujapigu Ave Apt 3, Miami, FL 33116
PO Box 1234, Austin, TX 78701                         ->  PO Box 9070, Austin, TX 78775
ATTN Pat Quinn, 88 Bayview Dr Ste 200                 ->  ATTN Vup Talul, 98 Mivodig Dr Ste 529
41-20 Bayview Ave, Flushing NY 11355                  ->  24-39 Mivodig Ave, Flushing NY 11395
1/2 Pelican Way #12B                                  ->  1/2 Tutewes Way #30B
412 5th St, Marigold Holdings LLC                     ->  556 8th St, Bufarobu Wotihicu HOJ
```

Three things to notice: `Bayview` became `Mivodig` in both lines that had it (the same value gets the same replacement);
`Ave` and `Ste` stayed because the lexicon knows them; and in the last line `LLC` became `HOJ`, which the parser no longer
reads as it read `LLC`, so that value is reported as not faithful.

## Using it

### In the browser

The [Try doorplate page](https://jeremeybingham.github.io/doorplate/demo/#csv) anonymizes a CSV file with the same library
compiled to WebAssembly (`anonymize_batch`): pick the file, choose **Anonymize it**, say which columns hold the address,
tick any other column to mask, and download the result. The file is read in the tab and nothing is uploaded. Differences
from the command line:

- **One random seed for each file**, never shown: the same value gets the same replacement in every row and column. There is no `--seed`.
- **Columns you did not tick are left out** unless you tick "Also keep the columns I did not tick". The page then lists the
  columns it copies as they are, because a name or id column kept as it is defeats the purpose.
- The summary gives the share of values the parser reads the same as before (`faithful`), and says that this is not anonymity.

### Command line

```sh
doorplate anonymize - < lines.txt                       # one value per line, from standard input
doorplate anonymize in.csv --column address -o out.csv  # the named column(s) of a CSV file
doorplate anonymize in.csv --column line1 --column line2 --column zip --seed 7 -o shareable.csv
```

| Option | Meaning |
|---|---|
| `-` or no file | Read standard input, one value per line; write the anonymized lines to standard output |
| `IN.csv --column NAME` | Anonymize that column; repeat `--column` for several. Every other column is copied unchanged. Required for a file, not allowed for standard input |
| `-o OUT` | Write to a file instead of standard output |
| `--seed N` | A whole number: the same seed gives the same output (see [Seeds](#seeds-and-consistency)). Without it the seed is random |

Standard error gets a summary: how many values were anonymized and how many the parser reads the same way afterwards, and
the reminder that this is obfuscation. Blank values are copied and not counted. Line endings in text input come out as `\n`.
Errors never quote a row (a CSV error can name one). Exit codes are those of the other commands: 0 success, 1 a usage error,
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
pandas, anonymize the columns you need and keep the rest (`anonymize_many` wants strings, so fill missing values first):

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
println!("{} (parser reads it the same: {})", r.text, r.faithful);
```

`Anonymized` is `#[non_exhaustive]` (read its fields; do not build one). The anonymizer holds a parser, so build it once and reuse it.

## Columns, lines and files

The unit of work is one text value. Each value is anonymized on its own, so:

- **Several columns** work, and a word that appears in two columns gets the same replacement in both (`ATTN Pat Quinn` on
  line 2 and `Pat Quinn` in an owner column match), so a join or a duplicate check on the output still works.
- **Text with line breaks** in one cell (`9 Willow Way` / `Suite 12`) is one value; the breaks stay.
- **Separate address columns.** Each cell is parsed alone. A state column stays. A ZIP column keeps its first three digits.
  A bare **city** column is replaced, because with no state beside it the text cannot be told from a street name: leave a
  city column out of `--column` to keep it.
- **Several addresses in one cell, or free text around an address** are handled word by word, with no parse needed.
- The `faithful` figure for a name or city column on its own is not informative; read it for whole-address columns.

## Seeds and consistency

The replacement of a value comes from a keyed hash of the seed and the value, so within one seed **the same value always
gets the same replacement** (case-insensitively for words, so `BAYVIEW` and `Bayview` change to the same letters in their
own case). Duplicates stay duplicates, and a dedupe or key test on the output behaves like one on the input.

The default seed is random for every run, so nobody can recompute your replacements from a guess at the input. **A seed you
publish lets anyone test a guess**: they run the tool with your seed on the guessed text and compare. Use `--seed` for a
repeatable test file that holds only invented or already-public text, and leave it out when you are sharing real data.
The mapping does not depend on the standard library's hashers, so it is the same on every platform for one version of the
tool; a later version may add rules, so do not rely on it across versions.

## The faithfulness check

Each value is parsed before and after, and `faithful` says whether the parser reads them alike: the same address type, the
same warnings, the same suffix, directionals, unit designators, state and city, a ZIP of the same length, and the same
*shape* (letters `a`, digits `9`, runs collapsed) for the street number, street name, unit number, PO box, attention line and
leftover text. A value that did not parse before and does not after counts as faithful; one that parsed before and not
after, or the reverse, does not. The CLI prints the share; Python and Rust give it per value.

`faithful` answers "will a bug I saw in the original still show up in the copy?" It is a good sign, not a proof: it compares
what doorplate sees, and a different tool could read the two differently.

## Limits: what it can leak

Read the output against this list before you share it:

1. **Run it without `--seed`**, so the replacements cannot be recomputed. A published seed can be attacked (see [Seeds](#seeds-and-consistency)).
2. **Lexicon words stay.** A street called `PARK`, `HARBOR`, `SUMMIT` or `HOLLOW`, or a person named `Lane` or `Fairfield`
   where the word is a suffix, stays as written. So does a name that is also a state code or a unit designator.
3. **The city, the state and the first three digits of a ZIP stay.** With a rare street shape, that can narrow a record to a small area.
4. **Names in free text that the lexicons know stay.** The tool cannot tell a name from any other unknown word, and it does
   not know what is sensitive in your data.
5. **A trailing country word is replaced** (`USA` at the end of a line becomes an invented word, and the copy is reported as
   not faithful). Remove or keep such a word by hand.
6. **Structure stays.** The length of every word, the order of the parts, the typos, the case and the punctuation are the
   originals. A distinctive format, such as a typo that only one office makes, can identify its source.
7. **Single letters stay** (`C/O`, an initial, a unit letter), and short numbers that look like fractions.

Then read every line that still has a word you do not expect to see (`grep` for the names you know are in the file), and
every line reported as not faithful. Remove lines you cannot make safe, or reduce them to shapes (`doorplate`'s own warning
codes and counts are fine to share). Share a small sample, not the file: ten faithful lines that show the problem are worth
more than ten thousand. If it is still too close to real data, describe the shapes in words and send counts instead
([`CONTRIBUTING.md`](../CONTRIBUTING.md), "Sharing messy data").

For what the project may keep from private data, see [`data-policy.md`](data-policy.md). This tool is for people sharing
*their* data with us; it does not change that policy.

## Measured rates

Measured 2026-10-27 with `doorplate anonymize --seed 1` on samples of the maintainer's private data (counts and rates only).
"Same" is the share of values the parser reads the same afterwards: street lines (line 1) 96.7% to 99.9% by source over
100,000 values each, with no digit run kept except single-digit fractions; line 2 94% to 100% on eight sources (NC voter
80.9% on a small sample of 533).

Caveat: most words of two letters or more that stay are unit words and suffixes (23 words make up 82% of what stays); the
rest are lexicon words that could be names. **Not measured:** personal-name columns (the local record files keep only ids and
address columns), and any text that is not an address. Your data may differ, which is what the check on your own file is for.
Speed: about 100,000 values in 2.2 seconds on one machine, with the parse before and after.

## Related pages

- [`CONTRIBUTING.md`](../CONTRIBUTING.md), "Sharing messy data": what to send and how.
- [`data-policy.md`](data-policy.md): what data the project uses and what may leave `local-data/`.
- [`benchmark-suite.md`](benchmark-suite.md), "Anonymization": the other procedure, for labeled NAD rows.
- [`examples/anonymize_example.py`](../examples/anonymize_example.py) and the [notebook](../examples/quickstart.ipynb).
