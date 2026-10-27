# Custom layers

A **custom layer** lets you add your own spellings and words to doorplate without editing the shipped tables: a street
suffix your data spells `TRAYL`, a unit word your county uses, a country word that trails your addresses, or a
state-specific reading of a spelling. It is loaded at run time, checked against the shipped tables, and reported in every
parse it touches. This library formats and parses; it does not validate that an address exists or can receive mail.

**Status (issue #3).** This page describes the first part: spellings, word lists and state-scoped readings, in the core
library (the `custom-layer` cargo feature). Places and ZIPs, the command line (`--custom-layer`, `doorplate layer check`),
Python (`Parser(custom_layer=...)`), a demo layer and a guide for writing one (with an LLM prompt) follow in the next parts
of the same issue, and this page grows with them.

Contents: [What a layer is](#what-a-layer-is) · [The files](#the-files) · [Rules](#rules) · [Using it from Rust](#using-it-from-rust) ·
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
| Invalid TOML | Error naming the file |

A layer entry defaults to `observed`, so a parse that uses it carries `non_standard_abbreviation`, the same as the shipped
`observed` spellings. Use `kind = "variant"` for a spelling that is standard where you work.

## Using it from Rust

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
default build has none. The core takes text, so you read the files yourself (the command line and Python will).
A loaded layer lives for the rest of the process (its few strings are leaked once, and loading the same text again returns the
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
