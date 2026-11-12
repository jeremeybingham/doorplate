# How doorplate works

## What it is for

`doorplate` turns a US address, written as one line or as separate fields, into:

1. **Components** (street number, directionals, street name, suffix, units, city,
   state, ZIP and the less common shapes below), each with its position in the
   original text.
2. **Normalized output** in USPS Publication 28 form and RESO Data Dictionary 2.0
   field names, mixed-case and spelled-out display forms for showing an address to a
   person (not Pub 28 forms), and usaddress-shaped labels.
3. **Identifiers for databases**: a stable match key and a URL-safe slug.
4. **Diagnostics**: warnings and the text it could not place, so bulk users can
   send doubtful rows to review.

It is a Rust library with no runtime dependencies, a command-line tool (which
also parses CSV files) and a Python package (PyO3, abi3 wheels for Python 3.10 and
later, with pandas, Polars and DuckDB helpers). Nothing is downloaded at run time.

**What it does not do.** It formats and parses; it does not validate, geocode, match fuzzily, correct addresses or
handle international addresses. When the place list finds a city, the parsed `city` stays what the input said and the
match is reported beside it (`place`).

## The pipeline

```
raw input
  -> clean      whitespace, accents, punctuation, uppercase; a map back to the original
  -> tokenize   tokens with original spans; lines and comma segments; glued tokens split
  -> classify   token shapes and longest-match lexicon lookups
  -> tagger     rules and place lookups
  -> assemble   ParsedAddress, component spans, warnings
  -> emitters   USPS, RESO, key, slug, display and long forms, usaddress tags (read-only)

Lexicons (Pub 28 tables, national places, state data) are read by classify, the
tagger and assemble.
```

Each stage keeps spans: `clean` maps every byte back to the original input; `tokenize` splits on whitespace and
treats commas and semicolons as strong segment boundaries, splitting glued tokens only when unambiguous (`101BRADDOCK`,
`APT.1285`); `classify` applies shape tests and longest-match lexicon lookups; the `tagger` reads the last line (ZIP,
state, city) first, right to left, then the delivery line from both ends (Pub 28 section 231), using the place list to
find a city on a line with no commas; `assemble` builds the `ParsedAddress`, looks up standard values and raises
warnings. Emitters read the parsed address and nothing else.

With separate fields (`parse_fields`, or `parse_fields_many` for columns), each field is tagged on its own and the
field is a strong signal: the city field is the city. When city, state and ZIP
are all empty, `line1` and `line2` are read like one line, so a street line plus
a `CITY, ST ZIP` line still works. When `line1` itself ends with the state field's
two letters and a five-digit ZIP (`214 N PARK AVE OAKLAND NE 68045`) and there is no
`line2`, it holds the last line: it is read as one line and the city, state and ZIP
fields give way (#614).

## Principles

- **Deterministic.** The same input gives the same output on every platform.
- **Never panics on input.** Parsing always returns a `ParsedAddress` with
  diagnostics. Only input with no address text at all is an error. Property tests
  and fuzz targets check this; the size of the real-data runs is in [`data-policy.md`](data-policy.md).
- **Spans are preserved.** Components keep their byte range in the original
  input (and the field, for separate fields).
- **Lexicons behind one interface.** The tagger never reads a table directly:
  everything goes through `Lexicons`, which merges the Pub 28 tables, the national
  place list and any state data. There is no state-specific logic in the tagger.
- **Emitters are read-only.** A new output format cannot change a parse.
- **Rules plus a place list, no model.** There is no statistical model, no
  training and no model file. The place list is what separates a city from street
  words on a line with no commas (`281 EVELYN DR DOTHAN`); a statistical tagger
  has no place list and would not find the city either. Fixing a misparse means
  adding a rule or a table entry, which shows up in review.
- **No global state.** A `Parser` is cheap and `Send + Sync`.

## What comes out

`ParsedAddress` holds the street number, pre- and postdirectional, street name,
suffix, `highway` (state, prefix and route), first and second unit (type and
number), `po_box`, `rural_route` (RR or HC, route, box), `general_delivery`,
`military` and `military_post_office`, `attention`, `building`, city, state, ZIP5,
ZIP+4, `place`, `diagnostics` and `source` (the original text and the spans).
`Diagnostics` holds the warnings, the unparsed remainder, the library version and the
version of the state's curated data (`state_data_version`, `None` without it).

Warnings have a stable snake_case `code()` meant for a database column. A warning is a finding about the
parse, not a statement that the address is wrong. The codes, what each means and how often rows that carry it
disagree with labeled data are in [`warnings.md`](warnings.md).

## Choices that shape the output

- **The place is reported beside the city, not in it.** `city` is what the input
  said (it has no span when it was found from the ZIP); `place` holds the
  standard place name and how it was found: exact, a listed variant, completed (a
  cut-off name), or from the ZIP. Filling in or correcting a city is a
  correction, which the library avoids, and the key leaves the city out.
- **City and ZIP disagreeing is a warning** (`zip_city_mismatch`), not an error.
  It says the pair does not match the place list. It fires only for states with a
  curated state data, because the national list gives one place per ZIP while the postal
  service accepts several city names for many ZIPs.
- **`default_state` is a lookup hint, never a fill.** When the input names no state
  and has no known ZIP, a city is looked up in the hinted state and the state's
  state data readings apply. `state` stays empty, `missing_state` still fires and the
  key keeps its `k4n` form; `default_state_applied` says when the hint decided
  something.
- **Dual addresses keep both.** A record with a street address and a PO Box fills
  the street fields and `po_box` and raises `dual_address`. The key, the slug and
  the RESO output use the street; the USPS output writes the PO Box alone, as Pub
  28 section 215 prefers for the mailpiece.
- **Shapes with no RESO field are folded in** (`StreetName` or `UnitNumber`; [`reso-mapping.md`](reso-mapping.md)).
- **Attention lines are a field** (`ATTN`, `C/O`, `% NAME`) and are not written by any
  emitter.
- **A trailing country is ignored.** `USA`, `US` or `UNITED STATES` after the
  address is dropped with `country_ignored`; other countries are not recognized.
- **A second line that is used or dropped without a component of its own is reported** (`second_line_skipped`,
  `second_line_in_street`, `second_line_building`), so a pipeline can audit those rows. None changes a component or a key.
- **A letter after the house number is reported.** `123 B MAIN ST` raises `ambiguous_number_letter`: the letters `A` to
  `D` are read as a unit, the others stay in the street name. `123B ELM ST` keeps the letter in the number and raises
  `glued_number_letter`; its key differs from the spaced form. Details: [`warnings.md`](warnings.md).
- **Intersections have no key.** `MAIN ST & 1ST AVE` raises
  `intersection_detected`: the first street is parsed, the second stays in
  `unparsed`, and `key()` and `slug()` are `None`, because the first street alone
  would match every address on it.
- **`tag()` and `address_type()`** give usaddress-shaped output. Tokens that share
  a label are joined; a repeated label is joined and reported (`repeated_label`)
  instead of raising an error (`docs/usaddress-compat.md`).
- **A penthouse after a designator is one unit** (`APT PH 5213` is `APT PH5213`).
- **A curated state data wins over the national list for its state.** National rows for
  that state only add places the state data lacks.

## The key

The canonical key is a deterministic string for deduplication and joins (`123 N. Main Street, Apt 4` and
`123 north main st #4` give the same key). It uses the street components, state and ZIP5 and leaves out the city.
Any change to what an input produces needs a new version prefix; store the version with your keys.
Format and history: [`key-format.md`](key-format.md). The slug is for display and is not unique or versioned.

## Lexicon layers

Data comes in layers, compiled in by `build.rs` into static sorted tables (a malformed or contradictory table fails the
build): the base Pub 28 and RESO lexicons (`crates/doorplate/data/*.toml`), the national place list (`data/places/`,
cargo feature `places-us`, on by default; [`places.md`](places.md)), curated state data (`data/states/<st>/`;
[`states/fl.md`](states/fl.md)) and, at run time, an optional custom layer (`custom-layer` feature). Layering is
add-only: a later layer adds names, variants and ZIPs and never replaces an earlier entry; a state's `overrides.toml`
is the one exception. What a custom layer can extend and what stays code: [`custom-layers.md`](custom-layers.md).

Cargo features: `rayon` (parallel `parse_many`), `corpus` (the golden-corpus runner; pulls in serde) and `places-us`
(on by default). The default build has no runtime dependencies.

## Where to look next

The repository layout and how it is tested are on [Repository layout and tests](repository.md). The reference pages
([the key](key-format.md), [warnings](warnings.md), [RESO mapping](reso-mapping.md), [Pub 28 notes](usps-pub28-notes.md),
[places](places.md), [state data](states/README.md)) are in the menu; the index of every page is [`README.md`](https://github.com/jeremeybingham/doorplate/blob/main/docs/README.md) on GitHub.
