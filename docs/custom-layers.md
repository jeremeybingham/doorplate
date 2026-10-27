# Custom layers

A **custom layer** lets you add your own spellings and words to doorplate without editing the shipped tables: a street
suffix your data spells `TRAYL`, a unit word your county uses, a country word that trails your addresses, or a
state-specific reading of a spelling. It is loaded at run time, checked against the shipped tables, and reported in every
parse it touches. This library formats and parses; it does not validate that an address exists or can receive mail.

**Status (issue #3).** Complete: spellings, word lists, state-scoped readings, places and ZIPs, in the core library (the
`custom-layer` cargo feature), the command line and Python, plus a [demo layer](#the-demo-layer), a
[template](#writing-your-own-layer) to copy and a [prompt for an LLM](#a-prompt-for-an-llm) that drafts a layer from your misparsed
addresses.

Contents: [What a layer is](#what-a-layer-is) · [The demo layer](#the-demo-layer) · [Writing your own layer](#writing-your-own-layer) ·
[A prompt for an LLM](#a-prompt-for-an-llm) · [The files](#the-files) · [Rules](#rules) · [Checking a layer](#checking-a-layer) ·
[Using it from the command line](#using-it-from-the-command-line) · [From Python](#from-python) · [From Rust](#from-rust) ·
[What it reports, and keys](#what-it-reports-and-keys) · [What a layer cannot change](#what-a-layer-cannot-change)

## What a layer is

A layer is a folder of small files (or the text of them, if you load it from code). It is:

- **Add-only.** A layer adds spellings and words. A spelling the shipped tables already have is an error, so a typo or
  a stale entry cannot silently change a shipped reading. The one exception is the state-scoped `overrides.toml`, whose job is
  to read a base spelling differently in one state; even there, a reading the shipped state data already gives is an error.
- **Deterministic.** The same layer text gives the same parse on every platform. Loading the same text twice gives the same layer.
- **Validated at load.** Everything is checked before anything is used. On any problem nothing loads and the error lists all of
  them, each naming its file and entry (`aliases.toml [[suffix]] #2: ...`).
- **Documented by its entries.** Every entry needs an `evidence` or `note` string: where the spelling was seen, or why.
- **Outside the tagger.** The layer is consulted by `Lexicons`, after the shipped tables, so the parser itself does not change.

## The demo layer

[`examples/layers/riverbend-demo/`](../examples/layers/riverbend-demo) is a small working layer for **Riverbend County**, an
invented county in Washington state: two street-suffix spellings (one `observed`, one `variant`), a unit word, a directional,
a country-like trailing word, two places with misspellings, and a ZIP the two places share. Every name, spelling and ZIP in it is
invented. Try it:

```sh
$ doorplate layer check examples/layers/riverbend-demo
ok: layer riverbend-demo 1 (fingerprint fa57dd40301d6dfe)
$ doorplate parse "120 Fern Hollow Trayl, Fern Holow, WA 98991" --display
120 Fern Hollow Trayl
Fern Holow WA 98991
$ doorplate parse "120 Fern Hollow Trayl, Fern Holow, WA 98991" --display --custom-layer examples/layers/riverbend-demo
120 Fern Hollow Trl
Fern Holow WA 98991
```

Without the layer `TRAYL` is part of the street name and `Fern Holow` is an unknown city; with it the suffix is `TRL`, the
place is `FERN HOLLOW` (reported in `place`, with `source: "variant"`), and the key changes from
`k3:S|120||FERN HOLLOW TRAYL|||WA|98991` to `k3:S|120||FERN HOLLOW|TRL||WA|98991`. The notebook
([`examples/quickstart.ipynb`](../examples/quickstart.ipynb), "Your own spellings and places") and
[`examples/custom_layer_example.py`](../examples/custom_layer_example.py) walk through it from Python.

## Writing your own layer

A layer is worth writing when the same misreading shows up many times in your data. One-off typos are not worth an entry.

1. **Find the repeated misreadings.** Parse a sample and look at what the parser could not place. A spelling that is not a shipped
   suffix ends up inside the street name, so tally the first and last words of street names that have no suffix, and the
   words in `unparsed`:

   ```python
   from collections import Counter
   import doorplate

   parsed = doorplate.parse_many(lines)                  # your addresses, one string each
   words = Counter()
   for p in parsed:
       if p.street_name and not p.street_suffix:
           words[p.street_name.split()[-1]] += 1          # `OAK TRAYL`: TRAYL
       if p.street_name:
           words[p.street_name.split()[0]] += 1           # `NRTH LANTERN RD`: NRTH
       words.update((p.unparsed or "").split())           # text that fit nowhere
   print(words.most_common(40))                           # then look up the frequent, unfamiliar ones
   print(Counter(w for p in parsed for w in p.warnings))  # missing_city, non_standard_abbreviation, ...
   ```

   A city that never matches is a place to add; a frequent word before or after the street is a suffix, unit, directional
   or state spelling; a recurring word that is neither address nor recipient (a country, `NONE`, a building word) belongs in a
   word list. Count each candidate in your data and keep its **evidence**: a line count and one invented-or-masked example.
2. **Pick the file.**

   | You see | Add | File |
   |---|---|---|
   | `TRAYL` instead of `TRL`/`TRAIL`, `SUTE` for `STE`, `NRTH` for `N`, a misspelled state | a spelling of the row | `aliases.toml` `[[suffix]]`, `[[unit]]`, `[[directional]]`, `[[state]]` |
   | `POSTBX`, `CNTRY RD 12` | a special word or highway prefix | `aliases.toml` `[[special]]`, `[[highway]]` |
   | a trailing word that is not part of the address, a building word, a stand-in such as `NONE` | a word | `aliases.toml` `[[words]]` (`country`, `building`, `placeholder`, `non_recipient`, ...) |
   | a community or postal name the place list lacks, or a misspelling of one | a place | `places.tsv` |
   | a ZIP the shipped list lacks | a ZIP and its place | `zips.tsv` |
   | a shipped spelling that means something else in one state (`PL` is a plaza in this export) | a state reading | `overrides.toml` |

3. **Copy the template.** [`examples/layers/template/`](../examples/layers/template) has one working entry per table, marked
   `EXAMPLE`, with the options explained in comments. Copy the folder, rename it, set `name` and `version` in `layer.toml`, replace the
   examples with your entries and delete the files and tables you do not use.
4. **Check it.** `doorplate layer check my-layer` lists *every* problem at once, each naming its file and entry. The usual ones:
   a spelling the shipped tables already have (drop it: it already works), two places whose names compare equal (drop the
   variant), a ZIP whose place is unknown (add the place first), and a missing `evidence`.
5. **Test it on your data.** Parse the same sample with and without `--custom-layer` and compare: the entries you meant should
   change rows, and nothing else should. Write the cases you care about as a golden corpus and run
   `doorplate corpus test --dir my-corpus --custom-layer my-layer` whenever the layer changes.
6. **Keep the fingerprint with your keys.** A layer can change a key (see below). Store `layer.fingerprint` beside any stored
   keys and re-key when it changes.

Keep entries small and evidenced. A layer changes how addresses are *read*; it does not make an address exist, and the library
does not validate that one can receive mail.

## A prompt for an LLM

An assistant can draft the layer from a list of misparsed lines. This prompt is written for that: paste it into a chat, then paste
your lines after it. **Review what comes back** (the evidence, and that each spelling is real in your data), save the files in a
folder, and run `doorplate layer check`; the checker's errors are exact, so paste them back to the assistant if there are any.
Do not paste private data into a service you have not cleared; mask names and house numbers first
([`anonymizing.md`](anonymizing.md) shows how, and `doorplate anonymize` does it for a file).

````text
You are helping me write a doorplate custom layer: a folder of small files that teaches the doorplate
US address parser my data's own spellings and places. A layer only ADDS to the shipped tables; it
never replaces or removes anything. Below my message is a list of addresses that parse wrongly, one
per line, and (if I give it) what each should be.

Write the files below. Rules:
- Only add an entry when a spelling or place appears in my lines at least twice, or I tell you it
  is common. Skip one-off typos. Do not invent evidence: `evidence` is a short string saying where
  it was seen and how often, using only what my lines show.
- Spellings are plain text; case, periods and spacing do not matter. Never add a spelling that is
  already a standard USPS Publication 28 suffix, unit, directional or state spelling: it already
  works and the loader rejects it.
- Use these tables, and only these keys.
  aliases.toml
    [[suffix]]       abbr = "TRL"   spellings = ["TRAYL"]   kind = "observed" or "variant"   evidence = "..."
                     (abbr is the standard Pub 28 abbreviation. "variant" means the spelling is standard
                     where I work; "observed" is the default and raises a non_standard_abbreviation warning)
    [[unit]]         abbr = "STE"   spellings = [...]   evidence
    [[directional]]  abbr = one of N S E W NE NW SE SW   spellings = [...]   evidence
    [[state]]        code = "FL" (USPS code)   spellings = [...]   evidence
    [[special]]      form = one of po_box box rural_route highway_contract general_delivery attention
                     spellings = [...]   evidence
    [[highway]]      standard = "COUNTY ROAD" (a standard prefix name)   spellings = [...]   evidence
    [[words]]        list = one of building area city_head non_recipient numbered_street placeholder
                     country place_prefix   words = [...]   evidence
  overrides.toml (a state reads a shipped spelling differently; use sparingly)
    [[suffix]]       state = "OH"   spelling = "PL" (already a shipped spelling)   abbr = "PLZ"   evidence
    [[highway]]      state = "TX"   spelling = "RM" (not a shipped spelling)   highway = "RANCH ROAD"   evidence
  places.tsv (tab-separated, header line, `#` lines skipped)
    columns: state  name  county  kind  variants  evidence
    state = USPS code, name = the standard name, kind = municipality | place | subdivision,
    variants = misspellings separated by ";" (a variant must differ from the name by more than case,
    punctuation or spacing, or it is rejected)
  zips.tsv (tab-separated, header line)
    columns: zip  state  place  shared  evidence      (zip = 5 digits; place must be a real place of
    that state or one in places.tsv; shared = other places using the ZIP, separated by ";")
  layer.toml
    name = "..."   version = "1"   notes = "..."

Output exactly these files, each in its own code block headed by its file name, and leave out any
file with no entries. Then list, in a short bulleted section called "Not added", the spellings
you skipped and why (seen once, already standard, unsure what it stands for). Do not guess what
an unfamiliar word means: put it in "Not added" and ask me.

My addresses (one per line; masked values are fine):
````

The template and the demo layer follow the same file formats, so the assistant can also be given
[`examples/layers/riverbend-demo/`](../examples/layers/riverbend-demo) as a worked example. The prompt is kept in step with the
loader by a test (`crates/doorplate-py/tests/test_custom_layer.py`): it names every table and word list the loader accepts.

## The files

### `layer.toml` (required)

```toml
name = "county-extras"      # 1 to 64 letters, digits, ".", "_" or "-"
version = "2026.10.1"       # yours; reported with every parse
notes = "Spellings seen in the 2026 county export"   # optional
```

### `aliases.toml` (optional): more spellings, more words

Each table adds spellings of a row the shipped tables already have, named by its standard abbreviation or name.

```toml
[[suffix]]                    # a street suffix, by its Pub 28 abbreviation
abbr = "TRL"
spellings = ["TRAYL", "TRAIIL"]
kind = "observed"             # optional: "observed" (default; raises non_standard_abbreviation) or "variant"
evidence = "County export 2026: 41 lines like `120 OAK TRAYL`"

[[unit]]                      # a unit designator, by its abbreviation
abbr = "STE"
spellings = ["SUTE"]
evidence = "..."

[[directional]]               # N, S, E, W, NE, NW, SE or SW
abbr = "N"
spellings = ["NRTH"]
evidence = "..."

[[state]]                     # a state or territory, by its USPS code
code = "FL"
spellings = ["FLORIDDA"]
evidence = "..."

[[special]]                   # a special address word
form = "po_box"              # po_box, box, rural_route, highway_contract, general_delivery or attention
spellings = ["POSTBX"]
evidence = "..."

[[highway]]                   # a highway prefix, by its standard name
standard = "COUNTY ROAD"
spellings = ["CNTRY RD"]
evidence = "..."

[[words]]                     # words for one of the tagger's word lists
list = "country"             # building, area, city_head, non_recipient, numbered_street, placeholder, country or place_prefix
words = ["FOOBARLAND"]
evidence = "..."
```

A spelling is written as you see it; case, periods and spacing do not matter (`P.O. Box` and `po box` are one spelling). It
must have a letter or a digit and at most the lexicon's longest form in words. What the word lists do is in
[`how-it-works.md`](how-it-works.md) ("What a layer can extend"): for example `country` words are dropped from the end of a
line with the `country_ignored` warning, and `building` words end a building name.

### `places.tsv` and `zips.tsv` (optional): places and ZIPs the shipped list lacks

Tab-separated, with a header line naming the columns in any order. Blank lines and lines starting with `#` are skipped.

`places.tsv` adds places (a community, a neighbourhood, a postal name) and their misspellings:

| Column | Meaning |
|---|---|
| `state` | required: the USPS code of a state, DC or territory |
| `name` | required: the place's standard name, as you want it reported (`QUINCEWOOD HEIGHTS`) |
| `county` | optional: its county (also recognized as a county name, with or without `COUNTY`) |
| `kind` | optional: `municipality`, `place` (the default) or `subdivision` |
| `variants` | optional: misspellings and other spellings, separated by `;` |
| `evidence` | required: where the place was seen |

```text
state	name	county	kind	variants	evidence
FL	QUINCEWOOD HEIGHTS	ZEPHYR	place	QUINCEWOD HEIGHTS;QUINCEWOODD HEIGHTS	county export 2026: 212 lines
```

A place is looked up by its comparison key, so case, punctuation and abbreviations do not make a different place
(`Quincewood Hts` and `QUINCEWOOD HEIGHTS` are one place; a variant that differs only that way is an error, since it
is already equal). A name has at most as many words as the place lookup reads.

`zips.tsv` adds ZIP codes the shipped list does not have, each naming its place (which may be a place of the national list,
the shipped state data, or your `places.tsv`):

| Column | Meaning |
|---|---|
| `zip` | required: five digits |
| `state` | required: the state of the places |
| `place` | required: the ZIP's main place |
| `shared` | optional: other places that use the ZIP, separated by `;` |
| `evidence` | required |

A ZIP gives a line with no state its state, and the main and shared places are the ones a city may agree with: a city that is
none of them raises `zip_city_mismatch` when the state has shipped state data (Florida today). A layer does not turn that
check on for a state without state data.

### `overrides.toml` (optional): a state reads a spelling differently

The same shape as a state's own `overrides.toml` ([`states/README.md`](states/README.md)).

```toml
[[suffix]]                    # read a spelling the shipped tables have as another suffix, in one state
state = "OH"
spelling = "PL"               # must already be a shipped suffix spelling
abbr = "PLZ"
evidence = "Ohio county export: `PL` after a name is always a plaza"

[[highway]]                   # add a highway prefix spelling in one state
state = "TX"
spelling = "RM"               # a spelling no shipped prefix has
highway = "RANCH ROAD"        # a shipped prefix's standard name
kind = "variant"              # or "observed" (default)
evidence = "..."
```

The reading applies to an address in that state (its state, or with none, its ZIP's or the `default_state` hint's).

## Rules

| Rule | What happens |
|---|---|
| A spelling or word the shipped tables already have | Error: `... is already in the shipped tables; a layer only adds spellings` |
| A spelling two entries add | Error: `... is already added by another entry` |
| An abbreviation, code or name that is not a shipped row | Error naming the table |
| An unknown key or table in a file | Error listing the keys it knows |
| An entry with no `evidence` or `note` | Error |
| A state override of a spelling the shipped state data already overrides | Error |
| A state override of a spelling the shipped tables do not have | Error: add it under `aliases.toml` instead |
| A place, or a spelling of one, whose key the national list or the shipped state data already has | Error |
| A place or spelling whose key an earlier row (or the same row) already has | Error |
| A ZIP the shipped list already has, or one listed twice; a ZIP that is not five digits | Error |
| A ZIP whose place is not a known place of its state | Error |
| A row of a TSV file with the wrong number of columns, an unknown column, or no `evidence` | Error |
| Invalid TOML | Error naming the file |

A layer entry defaults to `observed`, so a parse that uses it carries `non_standard_abbreviation`, the same as the shipped
`observed` spellings. Use `kind = "variant"` for a spelling that is standard where you work.

## Checking a layer

A layer is a **folder**:

```text
county-extras/
  layer.toml        required: name, version, notes
  aliases.toml      optional
  overrides.toml    optional
  places.tsv        optional
  zips.tsv          optional
  NOTES.md          anything else is ignored (notes, data), except a .toml or .tsv with another name:
                    that is an error, so a misspelling (`alias.toml`, `place.tsv`) cannot leave a file unused
```

```sh
$ doorplate layer check county-extras
ok: layer county-extras 2026.10.1 (fingerprint 2ca8edfe22b5e7fc)
  1 suffix spellings
  1 places
  1 place spellings
  1 ZIPs
A layer can change a key: keep the fingerprint with keys stored under it.
```

On any problem nothing loads, the command exits 2, and standard error lists every problem, each naming its file and entry or
line (`county-extras/aliases.toml [[suffix]] #2: ...`). Fix them all and run it again. `doorplate layer check` is the loop for
writing a layer: edit, check, repeat.

## Using it from the command line

`--custom-layer DIR` goes with `parse`, `parse-file` and `corpus test`:

```sh
doorplate parse "123 Oak Trayl, Miami, FL 33101" --custom-layer county-extras --pretty
doorplate parse - --custom-layer county-extras < addresses.txt
doorplate parse-file in.csv --column address --custom-layer county-extras -o out.csv
doorplate corpus test --dir my-corpus --custom-layer county-extras   # your own golden cases, against your layer
```

Every JSON record carries `provenance.custom_layer` (`{"name", "version", "fingerprint"}`, or `null` when no layer was used). A
layer that cannot be loaded is exit 2 with the problems on standard error. `corpus test` runs a corpus the way you would test any
parser change ([`tests/corpus/README.md`](../tests/corpus/README.md)): write cases with the expected parse, keep a `passing.txt`,
and a layer edit that breaks one fails the run. (The project's own corpus is for the shipped tables; point `--dir` at yours.)

## From Python

```python
import doorplate

layer = doorplate.load_layer("county-extras")        # raises doorplate.LayerError listing every problem
layer.name, layer.version, layer.fingerprint         # ('county-extras', '2026.10.1', '2ca8edfe22b5e7fc')
layer.counts()                                       # {'suffix spellings': 1, 'places': 1, ...}

a = doorplate.parse("123 Oak Trayl, Miami, FL 33101", custom_layer=layer)
a.street_suffix                                      # 'TRL'
a.custom_layer                                       # {'name': 'county-extras', 'version': '2026.10.1', 'fingerprint': ...}
a.to_dict()["provenance"]["custom_layer"]            # the same; None when no layer was used

parser = doorplate.Parser(default_state="FL", custom_layer=layer)
parser.parse_many(lines)                             # a Parser keeps the layer; parse_many releases the GIL
```

`custom_layer=` takes a `doorplate.CustomLayer` or the path of a layer folder (loaded on the spot, so load once and pass the
object when you call often). It is accepted by `Parser`, `parse`, `parse_fields`, `parse_many`, `parse_fields_many`, `tag`,
`parse_tokens`, `address_type`, and by `doorplate.pandas.parse_column`, `doorplate.polars.parse_column`, and
`doorplate.duckdb.register` and `parse_column`. A runnable version is
[`examples/custom_layer_example.py`](../examples/custom_layer_example.py).

## From Rust

```rust
use doorplate::{CustomLayer, LayerSources, ParseOptions, Parser};

let layer = CustomLayer::from_sources(
    &LayerSources::new("name = \"county\"\nversion = \"1\"\n").aliases(
        "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"TRAYL\"]\nevidence = \"county export\"\n",
    ),
)?;
let parser = Parser::with_options(ParseOptions::new().custom_layer(layer))?;
let a = parser.parse("123 Oak Trayl, Miami, FL 33101")?;
assert_eq!(a.street_suffix.map(|s| s.abbr()), Some("TRL"));
assert_eq!(a.diagnostics.custom_layer.map(|l| l.name), Some("county"));
# Ok::<(), Box<dyn std::error::Error>>(())
```

Enable the feature: `doorplate = { version = "...", features = ["custom-layer"] }`. It adds one dependency, the `toml` parser; the
default build has none. `CustomLayer::from_sources` takes the text of the files (`LayerSources` has `aliases`, `overrides`, `places` and `zips`);
`CustomLayer::from_dir(path)` reads a folder, as the command line and Python do, and `CustomLayer::counts()` summarizes one.
A loaded layer lives for the rest of the process (its strings are leaked once, and loading the same text again returns the
same layer), so load it once and reuse it.

## What it reports, and keys

Every parse made with a layer reports it in `Diagnostics::custom_layer`: the layer's `name`, `version` and `fingerprint` (FNV-1a
64 over the files' bytes, 16 hex digits; it changes when any byte changes, comments included). A parse without a layer reports
`None`.

**A layer can change a key.** `123 Oak Trayl` has no suffix without the layer above and has `TRL` with it, and the key differs.
That is not a new key version (`k3` is still the format and the shipped rules are unchanged), but stored keys are only comparable when
they came from the same layer. Store the fingerprint beside the keys, and re-key when it changes
([`key-format.md`](key-format.md), "Stability"). A parse with no layer, or with an empty one, is identical to a build without the
feature: 100,000 sampled rows gave the same keys, USPS lines and warnings, at the same speed.

## What a layer cannot change

The shapes in code (house numbers, ordinals, ZIP and route values, unit value shapes), the input folding and output casing,
the rules that name a table row, the military kinds and post offices (fixed by USPS), and the words that are constants in
`lexicon.rs` for now (the missing-number markers, the unit filler words, the value joiners and the intersection connectors)
([`how-it-works.md`](how-it-works.md), "What a layer can extend"). A layer cannot remove or replace a shipped entry.

## Related pages

[`how-it-works.md`](how-it-works.md) ("Lexicon layers") · [`key-format.md`](key-format.md) · [`api-surface.md`](api-surface.md) ·
[`states/README.md`](states/README.md) (the shipped state data a layer's overrides mirror).
