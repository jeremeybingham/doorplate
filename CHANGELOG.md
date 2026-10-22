# Changelog

All notable changes are listed here, newest first. The project follows
[Semantic Versioning](https://semver.org/). The canonical key format has its own
version (currently `k2`), tracked separately in [`docs/key-format.md`](docs/key-format.md): a
change to what an input produces needs a new key version.

## [Unreleased]

- Provenance (issue #85): `doorplate --version` (and `-V`) prints the library version, `--help` (and `-h`) prints
  the usage and exits 0, and the JSON from `doorplate parse` and Python's `to_dict()` carry
  `provenance.library_version`. A new key in the output, not a change to any value or key. The state data
  version (#7) will join the same `provenance` group.

- Parsing: an in-care-of line written with a percent sign (`% JOHN SMITH`, `%JOHN SMITH`) and `IN CARE OF NAME`
  are read as the attention line, in line 2 and in one-line input alike. Before, the `% NAME` text stayed
  in `unparsed` with an `unparsed_remainder` warning (64% of the rows of the IRS exempt-organization
  extract), and `IN` was left over from `IN CARE OF`. Keys do not change (issue #97).

- Warnings: a hyphenated house number with a larger second part (`21-77 31ST ST`) no longer raises
  `multiple_addresses` when the place resolves to Queens County, New York, where the part before the
  hyphen is the cross street. Ranges elsewhere (`1204-1206 MAIN ST`, and in Manhattan) still warn. The
  number and the key do not change (issue #99; the twin `2177 31ST ST` keys apart: #109).

- Documentation: a Disclaimer section in the four READMEs (provided as is, no warranty, use at your own
  risk, not a validator, not affiliated with the US Postal Service, RESO or DataMade).

- Planned for 0.4.0: the reserved `confidence` field, always `None`, is removed (issue #102). The
  roadmap now lists a table of how reliable each warning is and named warnings for known
  ambiguities in its place.

- For maintainers: `tools/review/` (issue #122) is a local page that shows the hard rows of a harness run to a person, records a verdict and a corrected string for each, and writes a shape-only export that may be shared. The wasm crate gained `parse_fields`, and `export.py --full` writes the answers in full text for the sources the owner clears in `local-data/review/full-ok.txt`, with name-bearing fields masked.

- For maintainers: the harness moved from `tools/netsyms/` to `tools/harness/` and reads any address source (`run.py --input`), with an ingest tool (`tools/ingest/`) that turns a source into one record format, `label_score.py` (scores the parse against labeled parts, or against another file's labels) and `shapes_report.py` (a ranked list of failure shapes). The run artifacts are schema version 4.

## [0.3.0] - 2026-10-19

Still an alpha. The match key moves to `k2`, and a batch of parsing
rules found by running the parser over about 146 million split US address rows, a second
national address source, nearly two million Florida licensee addresses and the geocode benchmark. On the
benchmark's `dev` split the whole-address score goes from 92.6% to 94.4% (usaddress: 88.1%);
speed and size are unchanged. A benchmark suite now ships in the repository.

### Changed: the match key is now `k2`

The prefix is `k2:` (and `k2n:` for a partial key). `k1` is retired: the library no longer
produces it and there is no migration tool. The segment layout is the same. The key is a function
of the parse, so keys of different versions never compare equal, and several inputs now parse
differently, which is why this is a new version. To re-key stored data, store the prefix with your
keys and parse the original addresses again. `docs/key-format.md` is the `k2` spec. The inputs
whose key (or other output) changes, each with its row in `docs/usps-pub28-notes.md`:

- **Units.** A pre-split second line of one to three short bare tokens (`2 5`, `4 G`, `B B5`) is a
  unit with no designator, and so are up to three such tokens after a `#`. A designator that always
  takes a value followed by two letters (`APT TD`) is a unit. Two units in one value
  (`UNIT 101/102`, `SUITE 3 & 4`) are one unit value, kept as written, and a business name after a
  whole unit (`UNIT 12 BLU SPA`) stays in `unparsed` instead of hiding the unit. A directional after
  a designator that does not always take a value is the street's postdirectional
  (`123 OCEAN FRONT W` is the name `OCEAN FRONT`, not unit `FRNT W`).
- **House numbers from split sources.** A fraction alone in line 2 (or opening it) joins the number
  (`123 MAIN ST` / `1/2` is `123 1/2`). A lone `N`, `S`, `E` or `W` and a number of three digits or
  more that open the line are one grid number (`N 10129` is `N10129`); a grid number takes one
  trailing letter (`E7608B`); a hyphen before a fraction is a space (`1174-1/2`). A comma right after
  a lone directional that follows the number is dropped (`3324 N, ANDREWS AVE`).
- **Placeholders.** A line 2 of no-data markers (`NONE`, `PA NONE`, `NULL`, `999999999 999999999`) is
  dropped instead of becoming a unit or leftover text, and `NULL` or a run of nines where the house
  number goes is dropped. A marker dropped from an otherwise usable address raises no `placeholder`
  warning (that warning removes the key).
- **Route numbers.** The key drops leading zeros from rural and highway route numbers (`RR 02` and
  `RR 2` share a key; `COUNTY ROAD 023` is `COUNTY ROAD 23`) and keeps them in box numbers. The USPS
  output writes the route as given.
- **The end of the street and the start of the city, one line with no commas.**
  Area words (`DOWNTOWN`, `UPTOWN`, `OLD`, `OLDE`, `CENTRAL`) before a known city belong to the
  city. Words that open a city name and are also suffixes (`LAKE`, `PARK`, `FOREST`, `FORT`, `PORT`,
  `MOUNT`, `VILLAGE`, and others) start the city after the street's own suffix
  (`123 MAIN ST LAKE QUINCEBROOK`). A spelled-out compass word before a known city is the street's
  postdirectional, and before an unknown town it opens the city. A lone directional that equals the
  first word of the city stays the postdirectional (`123 MAIN ST WEST` with city `WEST POINT`). A
  trailing suffix or directional equal to the state field is kept (`123 DEBBIE CT` with state `CT`).
- **Florida pack 2026.10.5** (`state-fl`): 26 more communities, 37 more spellings (abbreviations,
  misspellings, `VILLAGE OF` forms and the Miami-Dade district code) and 123 more observed
  (ZIP, place) pairs, from the Florida licensee files, by the pack's existing rules. `zip_city_mismatch`
  and "no place found" fire less often on Florida data.

Some inputs were looked at in this work and deliberately not changed, because the data does not say
which reading is right (a unit stuffed into the number field, `1120 -202`; a lone directional as the whole
of line 2) or a rule would break more than it fixes. Each is listed with its reason and its evidence in
`docs/usps-pub28-notes.md`, under "Left as it is on purpose", so it is not reopened without new evidence.

### Added

- A benchmark suite (`benchmarks/suite/v1/`, `python benchmarks/suite.py all`, issue #75): 19,586 labeled addresses
  (anonymized National Address Database rows, Census TIGER street names for the states NAD lacks, templates for PO
  boxes, routes, military and general delivery, and 1,000 hand-labeled shapes) scored for doorplate and usaddress
  under a fixed 4-CPU, 8 GB profile, with a doorplate-only track and a private twin that checks the public set was
  not tuned to. On its `natural` stratum doorplate gets 98.3% of whole addresses right and usaddress 96.1%; on the
  `hard` stratum, which holds both libraries' blind spots on purpose, 54.3% and 18.3%.
- `doorplate.duckdb` (extra: `pip install "doorplate[duckdb]"`): `register(con)` adds
  `doorplate_parse(text)` and `doorplate_parse_fields(line1, line2, city, state, zip)` to a
  DuckDB connection, returning a STRUCT of the chosen columns (Arrow UDFs, GIL released), and
  `parse_column(relation, column)` returns a lazy relation with the parsed columns added.
- For maintainers: a batch harness over the Netsyms address database (`tools/netsyms/`: `run.py`,
  `analyze.py`, `compare.py`, `nad_score.py`) and the National Address Database scorecard;
  `tools/compare/oneline_fl.py` and `city_diff.py`; `benchmarks/split_geocode_train.py`.

### Documentation

- The headline geocode-benchmark figure is the `dev` split (94.4% of whole addresses; the rules were
  first tuned against `test`, 96.7%), with 20% of `train` held out unread. All figures in
  `docs/benchmarks.md` and the READMEs are rerun.
- `docs/data-policy.md` (what data may be used and committed, and how Netsyms, the National Address
  Database and the Florida licensee files were used), `AGENTS.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`; `CONTRIBUTING.md` has a "Releasing" section.

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
