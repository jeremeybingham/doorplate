# Changelog

All notable changes are listed here, newest first. The project follows
[Semantic Versioning](https://semver.org/). The canonical key format has its own
version (currently `k2`), tracked separately in [`docs/key-format.md`](docs/key-format.md): a
change to what an input produces needs a new key version.

## [Unreleased]

### Changed

- **The match key is now `k2`** (`k2:` and `k2n:` for a partial key; 0.3.0). `k1` is retired: the
  library no longer produces it. The segment layout is the same, and the changes that make it a
  new version are listed here as they land (issue #44). The key is a function of the parse, so
  keys of different versions never compare equal: to re-key stored data, parse the original
  addresses again. `docs/key-format.md` is the `k2` spec.

### Documentation

- Benchmarks: the headline geocode-benchmark figure is now the `dev` split, 92.6% of whole
  addresses right (usaddress: 88.1%), not the `test` split's 96.4%, which the rules were
  tuned against. `benchmarks/accuracy.py` and `convert_geocode_benchmark.py` score the
  `dev`, `train` and `test` splits.

## [Unreleased]

### Added

- `doorplate.duckdb` (extra: `pip install "doorplate[duckdb]"`): `register(con)` adds
  `doorplate_parse(text)` and `doorplate_parse_fields(line1, line2, city, state, zip)` to a
  DuckDB connection, returning a STRUCT of the chosen columns (Arrow UDFs, GIL released), and
  `parse_column(relation, column)` returns a lazy relation with the parsed columns added.

## [0.2.0] - 2026-10-18

Still an alpha. New API and docs; no change to the `k1` key or to what any input
parses to.

### Added

- Display and long forms: `ParsedAddress::to_display()` (`123 N Main St Apt 4`) and
  `to_long()` (`123 North Main Street Apartment 4`), returning `DisplayAddress`; in
  Python `to_display()` and `to_long()`; in the CLI `--display` and `--long`. Neither
  is a Pub 28 form (use `to_usps()` for mail).
- `Parser::parse_fields_many` (parallel with the `rayon` feature) and, in Python,
  `parse_fields_many(line1=, line2=, city=, state=, zip=, default_state=None)` and
  `Parser.parse_fields_many`: a batch call for pre-split columns, GIL released.

### Changed

- Faster lexicon lookups (no allocation for tokens that are already keys): about 15%
  less time on the 30,622-address geocode benchmark. Output is unchanged.

### Documentation

- Each crates.io package now has its own README (`crates/doorplate/README.md`,
  `crates/doorplate-cli/README.md`) instead of the repository README.
- Fuzzing: `tools/fuzz/long_run.sh` runs both fuzz targets unattended for a set time.
  A 5-hour run of `parse` and `parse_fields` (about 194 and 177 million inputs) found
  no crashes, timeouts or out-of-memory kills.

## [0.1.0] - 2026-10-18

The first release. It is an alpha: keys are likely to get new versions as the parser
improves (store the `k1:` prefix with your keys and plan to re-key), and accuracy and
speed are measurements on a few datasets, not guarantees. If it parses your data badly,
please open an issue; see `CONTRIBUTING.md` for sharing messy data, anonymized if needed.

### Parsing

- Parses a US address written as one line, or as separate fields (`line1`, `line2`,
  city, state, ZIP), into components with their positions in the original text:
  street number, pre- and postdirectional, street name, suffix, up to two units, city,
  state, ZIP and ZIP+4.
- Reads the less common shapes: PO boxes, rural and highway contract routes, highway
  street names (`COUNTY ROAD 23`, `KY STATE HIGHWAY 625`), military and Department of
  State lines (`APO AE`), general delivery, dual addresses (street and PO box),
  attention lines and building names.
- Handles messy input: glued tokens (`101BRADDOCK LN`, `APT.1285`, `178ST`), cities run
  into the street, cut-off cities, placeholder text (`NO SITUS`), lines cut at about
  30 characters, copies of the address or city, a trailing `USA`, and intersections
  (reported, not keyed).
- Never panics on input. Every parse returns a `ParsedAddress` with diagnostics; only
  input with no address text is an error.
- `default_state` hint: looks a city up in the hinted state when the input names no
  state; never fills `state`.

### Output

- **USPS Publication 28** lines (`to_usps`, `to_usps_wrapped`, `lines`), checked
  against the published tables and the Appendix F examples.
- **RESO Data Dictionary 2.0** address fields (`to_reso`).
- A versioned **canonical match key** (`k1:`), at property or unit level, and a
  URL-safe **slug**.
- usaddress-compatible output: `to_usaddress_tags`, `tag` (joined by label) and
  `address_type`, with the label mapping documented.
- **Diagnostics**: 22 warning codes with stable names, the unparsed remainder, byte
  spans, and the library version. `confidence` is reserved and always `None`.

### Place data

- A national place list for the 50 states, DC and Puerto Rico (50,375 places, 41,154
  ZIPs; Census Gazetteer and GeoNames) finds the city on a line with no commas, tells
  a street from a city before a ZIP, and completes a cut-off city.
- A curated Florida pack adds Florida's place names, spellings, ZIP places and state
  readings (`CR` is CIRCLE, `SR` is STATE ROAD), with the `zip_city_mismatch` warning.
- `place` reports the place a city stands for beside the city, which keeps what the
  input said.

### Interfaces

- **Rust:** the `doorplate` library with no runtime dependencies (features `rayon`,
  `corpus`, `places-us`, `state-fl`) and `Parser::parse`, `parse_fields`, `parse_many`.
- **Python:** the `doorplate` package (abi3 wheels for Python 3.10 and later on Linux,
  macOS and Windows): `parse`, `parse_fields`, `parse_many` (parallel, GIL released),
  `tag`, `parse_tokens`, `address_type`, a typed read-only `ParsedAddress`, and
  `doorplate.pandas.parse_column` and `doorplate.polars.parse_column` helpers.
- **Command line:** `doorplate parse`, `parse-file` (CSV in, CSV out) and
  `corpus test`.
- `examples/`: a notebook tour, Polars and pandas pipelines and sample files.

### Quality

- A golden corpus of 437 cases, with key, slug, USPS and RESO expectations written
  from the specifications by an independent script; property tests; fuzz targets;
  a score floor on usaddress's labeled test files.
- `tools/pub28/verify.py` compares the tables with the live Pub 28 pages.
- `benchmarks/` and `docs/benchmarks.md`: 96.4% of whole addresses right on a public
  30,622-address geocoding benchmark (usaddress: 88.2%); about 21 µs per address from
  Python; a 1.7 MB wheel.

### Not in this release

- Address validation or deliverability, geocoding, address correction and international
  addresses (not planned).
- A confidence score (`confidence` is always `None`) and a user-extensible layer of
  aliases and places: planned, and both depend on more real, messy data. See
  `docs/roadmap.md`.
