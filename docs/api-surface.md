# API surface audit

The audit of #135: every public name and shape of the Rust crate, the Python package and the command-line
tool, with one decision for each (keep, change in 0.4.0, hide, or later). It was made on `main` on 2026-10-23,
at the start of 0.4.0, while the project has no users: this is the last cheap moment to rename things.
The decisions were confirmed by the owner on 2026-10-23 and made in the same release; the rest follow from rules that already exist.

The public Rust items were listed from `cargo +nightly rustdoc -p doorplate --all-features -- -Z unstable-options
--output-format json` (59 public items in the crate root, `lexicon` and `corpus`); the Python names from
`__init__.pyi`; the command line from `doorplate --help` and a run of each form.

## How the surfaces line up

One name should mean one thing in every language. The mapping, as it stands and as it stays:

| Concept | Rust | Python | CLI JSON (`components`) | CSV (`addr_`) | RESO |
|---|---|---|---|---|---|
| House number | `street_number` | `street_number` | `street_number` | `street_number` | `StreetNumber` |
| Street directional | `street_dir_prefix`, `street_dir_suffix` | same | same | same | `StreetDirPrefix`, `StreetDirSuffix` |
| Street name and suffix | `street_name`, `street_suffix` | same | same | same | `StreetName`, `StreetSuffix` |
| Unit | `unit_type`, `unit_number` (and `second_unit_*`) | same | same | same | `UnitNumber` |
| City, state | `city`, `state` | same | same | same | `City`, `StateOrProvince` |
| ZIP | `zip5`, `zip4` | `zip5`, `zip4` | `zip5` | `zip5`, `zip4` | `PostalCode`, `PostalCodePlus4` |
| Output forms | `to_usps`, `to_display`, `to_long`, `to_reso`, `to_usaddress_tags`, `tag` | the same names | `usps`, `reso`, flags | `usps_line1`, `usps_last_line` | |
| Key, slug | `key(KeyOptions)`, `slug()` | `key(unit=False)`, `slug()` | `key`, `key_unit`, `slug` | `key`, `key_unit`, `slug` | |
| Diagnostics | `diagnostics.warnings`, `.unparsed` | `warnings`, `unparsed` | `warnings`, `unparsed` | `warnings`, `unparsed` | |
| Provenance | `diagnostics.library_version`, `.state_data_version` | `library_version`, `state_data_version` | `provenance.*` | none | |

The names agree; the differences are deliberate (RESO uses its own Data Dictionary names; Rust returns enums and
structs where Python returns strings and dicts). Decision: **keep all of these names**. No `zip` / `zip5` or
`unit` / `occupancy` renames: a rename costs every example and doc, and the existing names follow Pub 28's
words. The mapping above goes into the documentation as the reference.

## Rust (`doorplate`)

### Findings

1. **Only two types are `#[non_exhaustive]`** (`Component` and `Warning`). Every result struct has all fields
   public and no `#[non_exhaustive]`, so adding a field is a breaking change for anyone who builds one with a
   struct literal or matches it exhaustively. This already happened once: #7 added `Diagnostics::state_data_version`.
   The result types are built by the parser, never by callers, so they can be closed without cost.
2. **Enums that can grow are closed:** `AddressType`, `ParseError` and `OptionsError` (one variant each),
   `MatchKind`, `PlaceKind`, `PlaceSource`, `StateKind`, `Special`.
3. **Inputs are different from results.** `Fields` (five fixed parts of an address) is built by callers and
   stays open. `ParseOptions` (one field, `default_state`) will grow (the custom layer, #3). `KeyOptions` will not
   in practice: a new key option changes the key, which is a `k3`.
4. **`Lexicons` had 28 public methods**, including helpers that exist for the tagger (`is_number_marker`,
   `is_no_data_line`, `is_city_head`, `is_area_word`, `is_building_word`, `is_placeholder`, `is_country`,
   `place_key`). They were public by accident; #137 made them crate-private.
5. **`corpus` is public behind a feature** (`Corpus`, `Report`, `Comparison`, `Case`, `load`, `baseline_path`,
   `read_baseline`, `write_baseline`): test infrastructure for this repository and `doorplate corpus test`.
6. `lexicon::{normalize_key, MAX_FORM_WORDS, MAX_PLACE_WORDS}` are public for the build script and the layer.
7. The Cargo features after #101: `places-us` (default), `rayon`, `corpus`. No feature per state.

### Decisions

| Surface | Decision |
|---|---|
| Result types: `ParsedAddress`, `Diagnostics`, `SourceInfo`, `DisplayAddress`, `UspsAddress`, `ResoAddress`, `PlaceMatch`, `Highway`, `RuralRoute`, `MilitaryBox`, `ComponentSpan`, `UsaddressTag` | **Done: `#[non_exhaustive]`** (0.4.0, breaking). Fields stay public: reading them is the API |
| Open enums: `AddressType`, `ParseError`, `OptionsError`, `MatchKind`, `PlaceKind`, `PlaceSource`, `StateKind`, `RouteKind`, `Special` | **Done: `#[non_exhaustive]`** (0.4.0, breaking): a `match` needs a `_` arm |
| Closed enums: `Directional` (8 compass points), `MilitaryKind`, `MilitaryPostOffice`, `RouteKind` (fixed by USPS), `FieldName` (the five `Fields`), `InputKind` | **Keep closed** |
| `Fields`, `Span` | **Keep open** (callers build `Fields`; `Span` is two offsets and a field name) |
| `ParseOptions` | **Done: `#[non_exhaustive]` with builder methods** (`ParseOptions::new().default_state("FL")`); it will grow with #3 |
| `KeyOptions` | **Keep open**: its constructors `property()` and `unit()` are how it is built, and a new option would change the key |
| `Lexicons` helpers | **Done (#137): the tagger's predicates (`is_*`, `place_key`) are crate-private**; the typed lookups, the place functions and the iterators stay public as the layer interface ([`how-it-works.md`](how-it-works.md), "What a layer can extend") |
| `corpus` module | **Keep behind its feature, documented as unstable** (no semver promise) |
| `lexicon::{normalize_key, MAX_*}` | **Keep** (needed by `build.rs`, which includes the same file) |
| `VERSION` | **Keep** |
| Features | **Keep** as listed |
| Error messages | **Keep** (`EmptyInput` and `UnknownDefaultState` are the only errors; parsing never fails on odd input) |

## Python (`doorplate`)

### Findings

1. `__all__` lists exactly the names of `_core` that are public: `ParsedAddress`, `ParseError`, `Parser`, `parse`,
   `parse_fields`, `parse_many`, `parse_fields_many`, `parse_tokens`, `tag`, `address_type`, `__version__`. The
   helper modules `doorplate.pandas`, `.polars` and `.duckdb` each export `AVAILABLE_COLUMNS`, `DEFAULT_COLUMNS`
   and `parse_column` (DuckDB also `register`).
2. `ParsedAddress.confidence` is gone in #136; `library_version` and `state_data_version` are properties, also in
   `to_dict()["provenance"]`.
3. `repeated_labels()` is a method of `ParsedAddress` in Python and of `TaggedAddress` in Rust. It describes the
   usaddress-shaped `tag()` output, so it belongs with it.
4. `parse_many` and `parse_fields_many` return `None` for an empty input, where Rust returns `Err(EmptyInput)`.
   `parse` raises `ParseError`.
5. `parse_tokens` cut tokens differently from `usaddress.parse` (`#value`, commas): #78. The difference was in the
   emitter, not the tokenizer, so no key can change; it is made right in 0.4.0.
6. `key(unit=False)` in Python is `key(KeyOptions)` in Rust.
7. `to_usps()` returns `line1`, `line2`, `last_line`; the helper columns are `usps_line1`, `usps_line2`,
   `usps_last_line`.

### Decisions

| Surface | Decision |
|---|---|
| Module names, `__all__`, `Parser(default_state)` | **Keep** |
| `ParsedAddress` attributes and methods | **Keep** |
| `repeated_labels()` | **Keep** (a convenience beside `tag()`; moving it would break Python for no gain) |
| `None` for an empty input in the batch calls | **Keep, document** (the batch must not stop at one empty cell) |
| `parse_tokens` | **Done (#78): cuts the input into the tokens of `usaddress.tokenize`** (0.4.0, breaking for code that relied on the old cuts; no key or parse change) |
| Helper columns and the `addr_` prefix | **Keep** (names match the attributes; the prefix keeps columns apart) |
| Type stubs | **Keep in step**: any change above updates `__init__.pyi` in the same change |

## Command line (`doorplate`)

### Findings

1. Subcommands: `parse` (one address, `--line1`.. fields, or stdin), `parse-file`, `corpus test`, `--version`,
   `--help`. Exit codes: 0 success, 1 a usage error (unknown command or flag), 2 an empty address.
2. The JSON record: `input`, `components`, `warnings`, `unparsed`, `key`, `key_unit`, `slug`, `usps`, `reso`,
   `place`, `provenance` (`library_version`, `state_data_version`). `components` carries only the parts present.
3. The CSV adds `addr_`-prefixed columns after the input columns. It has `addr_usps_line1` and
   `addr_usps_last_line` but no `addr_usps_line2`. That loses nothing today: `to_usps()` fills `line2` only when
   it is asked to wrap long lines (`max_line`), which the command line never does, so `line2` is always empty
   there (the unit stays on `line1`).
4. `--usps`, `--display`, `--long`, `--usaddress` and `--tag` choose one output form instead of the JSON record.

### Decisions

| Surface | Decision |
|---|---|
| Subcommands, flags, JSON keys | **Keep** |
| Exit codes | **Keep, document**: 0, 1, 2 as above |
| CSV: no `addr_usps_line2` | **Keep**: the column would always be empty. Revisit if the command line ever gets a line-length option |
| CLI JSON key order | **Keep**; it is not a promise beyond "`input` first" |

## Warning codes

The 26 codes are stable snake_case strings from `Warning::code`, and `Warning` is `#[non_exhaustive]`: new codes
may be added in a minor release, and consumers must not treat the set as closed. How reliable each
code is, measured: [`warnings.md`](warnings.md). New codes come with the parser rules of 0.4.0's second phase. **Keep** the names.

## The key and the slug

The key is `k2:` plus pipe-separated parts (the format and when it changes are in
[`key-format.md`](key-format.md)); `KeyOptions` has one switch, `include_unit` (`KeyOptions::property()` is the
property-level key, `KeyOptions::unit()` the unit-level key, which carries the unit numbers). The slug is for display, not for
matching. **Keep** both; the `ParseOptions` builder above is the only change.

## Output shapes

`place` (name, state, county, kind, source), `usps`, `reso`, the usaddress-shaped tags, and the highway and
rural-route dicts are documented in [`reso-mapping.md`](reso-mapping.md), [`usaddress-compat.md`](usaddress-compat.md)
and the READMEs. **Keep.** The result structs become `#[non_exhaustive]`, so a field added later is not a break.

## What a deprecation looks like after 0.4.0

With users, a rename or removal is announced one release ahead: the old name stays and works, the CHANGELOG says
what replaces it and when it goes, and Python raises a `DeprecationWarning` where the language allows (Rust uses
`#[deprecated]`). A change that alters a key is never a deprecation: it is a new key version (`k3`). Before 0.4.0
none of this applies, which is why the breaking changes above are made now and without shims.

## What changes in 0.4.0 and what waits

- **In 0.4.0 (done):** the `#[non_exhaustive]` additions and the `ParseOptions` builder (Rust, breaking, no output
  change). The key comparison with 0.3.1 must show zero
  differences after them.
- **Decided elsewhere:** `confidence` (#136, done); the state data version (#7, done).
- **0.4.0, phase 2 (the parser rules):** anything that alters a key.

## Is it stable enough for a beta?

The answer (updated 2026-10-23, when the `k3` was folded into 0.4.0): **not after the foundation phase, yes at 0.4.0
once the `k3` is in.** After the foundation phase the Rust, Python and CLI surfaces above are
settled except for two things that are still moving: the custom layer (#3, whose interface #137 settled) and
the key itself (the `k3`, still to come in phase 2). The beta notice should
wait for the `k3`: a beta that changes its key afterwards is not a beta. The alpha notice in the four READMEs
stays until then.
