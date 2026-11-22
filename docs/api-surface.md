# API surface

The public names of the Rust crate, the Python package and the command line, how they line up, and what is promised about them. The audit
behind them is #135 and its pull requests.

## How the surfaces line up

One name means one thing in every language. The names follow Pub 28's words (no `zip` / `zip5` or `unit` / `occupancy` renames).

| Concept | Rust | Python | CLI JSON (`components`) | CSV (`addr_`) | RESO |
|---|---|---|---|---|---|
| House number | `street_number` | `street_number` | `street_number` | `street_number` | `StreetNumber` |
| Street directional | `street_dir_prefix`, `street_dir_suffix` | same | same | same | `StreetDirPrefix`, `StreetDirSuffix` |
| Street name and suffix | `street_name`, `street_suffix` | same | same | same | `StreetName`, `StreetSuffix` |
| Unit | `unit_type`, `unit_number` (and `second_unit_*`) | same | same | same | `UnitNumber` |
| City, state | `city`, `state` | same | same | same | `City`, `StateOrProvince` |
| Puerto Rico urbanization | `urbanization` | same | same | same | none |
| ZIP | `zip5`, `zip4` | `zip5`, `zip4` | `zip5` | `zip5`, `zip4` | `PostalCode`, `PostalCodePlus4` |
| Output forms | `to_usps`, `to_display`, `to_long`, `to_reso`, `to_usaddress_tags`, `tag` | the same names | `usps`, `reso`, flags | `usps_line1`, `usps_last_line` | |
| Key, slug | `key(KeyOptions)`, `slug()` | `key(unit=False)`, `slug()` | `key`, `key_unit`, `slug` | `key`, `key_unit`, `slug` | |
| Diagnostics | `diagnostics.warnings`, `.unparsed` | `warnings`, `unparsed` | `warnings`, `unparsed` | `warnings`, `unparsed` | |
| Provenance | `diagnostics.library_version` | `library_version` | `provenance.*` | none | |

The differences are deliberate: RESO uses its own Data Dictionary names, and Rust returns enums and structs where Python returns strings and dicts.

## What each surface promises

- **Rust.** Result structs and the enums that can grow are `#[non_exhaustive]` (a `match` needs a `_` arm); `Fields` is built by callers and stays open;
  `ParseOptions` has builder methods; the tagger's predicates are crate-private. `corpus` is behind a feature and has no semver promise.
  Errors: only `EmptyInput` and `UnknownDefaultState`; parsing never fails on odd input.
- **Python.** `__all__` lists the public names; the helper modules `doorplate.pandas`, `.polars`, `.duckdb` and `doorplate.compat` are not re-exported at
  the top level. `parse` raises `ParseError`; the batch calls return `None` for an empty cell so one empty cell does not stop a batch. The type stubs
  (`__init__.pyi`) change in the same change as the API.
- **Command line.** Subcommands, flags and JSON keys are stable; exit codes are 0 success, 1 a usage error, 2 an empty address. The CSV has no
  `addr_usps_line2` (it would always be empty). JSON key order is not a promise beyond "`input` first".
- **Warning codes** are stable snake_case strings and `Warning` is `#[non_exhaustive]`: new codes may be added in a minor release, so consumers must not treat
  the set as closed ([`warnings.md`](warnings.md)).
- **The key** is versioned ([`key-format.md`](key-format.md)); the slug is for display, not for matching.
- **Output shapes** (`place`, `usps`, `reso`, the usaddress tags, the highway and rural-route dicts): [`reso-mapping.md`](reso-mapping.md) and
  [`usaddress-compat.md`](usaddress-compat.md).

## Deprecation

A rename or removal is announced one release ahead: the old name stays and works, the changelog says what replaces it and when it goes, Python raises
a `DeprecationWarning` where the language allows and Rust uses `#[deprecated]`. A change that alters a key is never a deprecation: it is a new key version.
From 0.7.0, the first beta, this is the only way a name changes (before it, the alpha releases renamed with a changelog note).

## Is it stable enough for a beta?

Yes, from 0.7.0. The three surfaces are settled; the last planned break, the removal of the state data structure (#700: `state_data_version` left the diagnostics), landed in 0.7.0 itself, and `k6` is the key of the beta.

A beta may still get a new key version, because accuracy fixes change what an input produces and a changed input is a changed key
([`key-format.md`](key-format.md)). What the beta promises is when: a new key version comes only in a minor release (0.8 and later), never in
a patch, with the re-key advice in the changelog, and the API and warning codes do not change under it.
