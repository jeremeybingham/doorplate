# Changelog

All notable changes are listed here, newest first. The project follows
[Semantic Versioning](https://semver.org/). The canonical key format has its own
version (currently `k2`), tracked separately in [`docs/key-format.md`](docs/key-format.md): a
change to what an input produces needs a new key version.

## [Unreleased]

### Changed

- **Recipient text ahead of the address is the attention line, not part of the street** (#127, **key-affecting, held for the
  `k3`**): `C/O ACME CORP 20 QUINCEWOOD CT` (the attention line took the whole line and the street was empty),
  `CO ACME INC 120 QUINCEWOOD AVE` and `CO 612 QUINCEWOOD ST` (`CO` for `C/O`, not the county highway),
  `ACME FOUNDATION 500 BAYVIEW RD` (no marker) and `ACME CO PO BOX 12345` (a name ahead of a box) now keep their house
  number or box and put the words in `attention`. Measured against the frozen checkpoint keys, 13,547 keys change
  in the seven large sources (5,494 IRS, 4,091 NC voter mailing, 1,870 amateur radio, 1,193 carrier census, 895 NY
  corporations, 3 Netsyms, 1 NAD), and `missing_street_number` is removed from about 12,000 rows. A county-highway prefix, a unit designator, a route or box word, a
  directional, any digit, a single letter or a word such as `BLOCK`, `NO` or `URB` among the leading words leaves the
  line as before (`[non_recipient]` in `data/special.toml`). The Netsyms sample changes in 3 rows.
- **A care-of line after a street no longer swallows the unit or leaves a warning** (#126, **key-affecting, held for the `k3`**): in
  `12 OAK AVE STE 4` / `% 5 STAR GROUP` the number after the marker started a second address, so the name was left over
  and the unit stayed in the street name. Now a marker line after a street is the attention line when it holds a
  digit-led name (`% 5 STAR GROUP`, `% 4-H CLUB`), and a copy of the street line (`% 68 QUINCEWOOD ST`) is dropped
  with `second_line_skipped`. A bare number (`% 9`) and a second address (`% 4 BAYVIEW WEST A`) stay unparsed.
  Measured against the frozen checkpoint keys: 299 of 1,975,975 IRS rows and 1 of 9,038,491 carrier-census rows change
  key (the unit now parsed out of the street name), none in NAD, Netsyms, the amateur-radio list or the NY
  corporations; 966 IRS rows lose `unparsed_remainder` (117 of them gain `second_line_skipped`); the Netsyms sample is
  identical.
- **Faster parsing** (#156): the lexicon's multi-word lookups join the tokens once and slice, instead of building a
  new string for every candidate length. About 30% fewer allocations per parse and about 6% more addresses per second
  on the benchmark suite's mix. No output or key changes (0 differences against 0.3.1 over 37.0M rows).
- **Place lookups allocate nothing** (#148): the place key is built in one buffer, kept per thread for `place` and
  `is_place`, instead of a string per word and per expansion. A further 25% fewer allocations per parse (138 to 103)
  and about 4% more addresses per second. No output change (a test compares the new key with the old
  implementation on every place name, every suffix and 30,000 generated strings).
- **Cheaper table lookups** (#147): the binary search over a lexicon table compares the first byte inline before it calls
  `memcmp`, and the key normalization checks a string in one pass. About 17% more addresses per second on the benchmark
  suite's mix (43,000 to 50,300), with no output change (tests compare both with the previous behavior).

### Changed (breaking)

- **`parse_tokens` and `to_usaddress_tags` cut the input like `usaddress.tokenize`** (#78): `#` and `&` are tokens of
  their own (`#7-C` is `#` and `7-C,`), trailing `. , ; )` stay on the token (`Ct,Mabank,TX` is `Ct,`, `Mabank,`, `TX`), a
  lone comma gives no token, leading punctuation is dropped, and `&amp;` and `&#38;` are read as `&`. Before, the
  tokens were whitespace-delimited. Checked token for token against usaddress on its 8,108 test strings and the 56,835
  inputs of the benchmark suite. `tag()` and the labels are unchanged (99.3% identical dicts, as before). The parse and
  the keys do not change: only this output view. The benchmark suite scores these tokens by character span, so its
  figures move only where a different cut had cost a token: the `hand` stratum goes from 92.3% to 94.3% and the whole
  suite from 92.2% to 92.3% (`docs/benchmarks.md`).
- **The `Lexicons` predicates the tagger uses are crate-private** (#137): `is_country`, `is_building_word`,
  `is_area_word`, `is_city_head`, `is_placeholder`, `is_no_data_line`, `is_number_marker` and `place_key`. The typed
  lookups (`suffix`, `directional`, `unit`, `state`, `special`, `highway`, `military`, the place functions and the
  table iterators) stay public. Three word lists that were hard-coded in the tagger (the unit filler words, the
  unit-value joiners and the intersection connectors) are now behind `Lexicons`. No output or key changes.
- **Result types and growable enums are `#[non_exhaustive]`** (#135), so a later field or variant is not a break.
  Structs: `ParsedAddress`, `Diagnostics`, `SourceInfo`, `PlaceMatch`, `Highway`, `RuralRoute`, `MilitaryBox`,
  `ComponentSpan`, `UspsAddress`, `DisplayAddress`, `ResoAddress`, `UsaddressTag`: read their public fields as
  before, but they cannot be built with a struct literal or matched without `..` outside the crate. Enums:
  `AddressType`, `ParseError`, `OptionsError`, `MatchKind`, `PlaceKind`, `PlaceSource`, `StateKind`, `Special`: a
  `match` needs a `_` arm. `ParseOptions` too, with `ParseOptions::new()` and `.default_state(..)` in place of the
  struct literal. No output or key changes.
- **The reserved `confidence` field is removed** (#136): `Diagnostics::confidence` in Rust, `ParsedAddress.confidence`
  in Python and the `confidence` key of `to_dict()`. It was always `None`; named warnings are the signal for how far to
  trust a parse (#102). No other value and no key changes.
- **State data is built in** (#101). The `state-fl` Cargo feature is gone: the Florida data is always compiled in, as
  every folder under `crates/doorplate/data/states/` is. `data/packs/` is now `data/states/`, `pack.toml` is
  `state.toml`, `docs/packs/` is `docs/states/`, the corpus file `fl-pack.jsonl` is `fl-state.jsonl`, and
  `Lexicons::has_pack` is `Lexicons::has_state_data`. A test checks that every state folder has a corpus file
  (`tests/corpus/<st>-state.jsonl`). The parser's output and the keys do not change.

### Added

- **A municipality prefix before the city is read off for the place** (#68): `VILLAGE OF PINECREST`, `TOWN OF LONGBOAT KEY`,
  `CITY OF SUNRISE`, `TOWNSHIP OF` and `TWP OF` now give `place` the rest (source `variant`; a cut-off rest such as
  `VILLAGE OF PALM SPRI` is completed from the ZIP), in every state, where only Florida's per-name spellings did. The city
  stays as written and no key moves. A place whose name starts with the prefix (`CITY OF INDUSTRY`, CA) is the place as
  written. `BOROUGH OF` is not read (one row in 40M). The list is `[place_prefix]` in `data/special.toml`.
  Measured: 0 keys and 0 warnings changed (17.6M rows of four sources against the frozen checkpoint keys, and
  against the build before this rule); the Netsyms sample is identical. On the record files of ten sources 3,247 rows
  (1 in 12,000 of the 40M) now get a place: `CITY OF` 2,683 (TX 2,277, CA 326), `TOWN OF` 292, `VILLAGE OF` 245,
  `TWP OF` 18 and `TOWNSHIP OF` 9.

- **A warning for a county written as the city** (#113): `city_is_county` for `123 MAIN ST, HENNEPIN, MN 55401` (and
  `MIAMI DADE`, `BROWARD`, `COOK`), where the city is no place of the state but the name of one of its counties (with
  or without `COUNTY`), from the county names of the national place list. `place` stays empty and the city is kept as
  written; the key reads the street, state and ZIP, so no key moves. A name that is both a place and a county
  (`COOK`, MN) is a place and is not flagged. Measured against the frozen checkpoint keys: 0 keys changed in 12.7M rows
  (the amateur-radio list, the tax-exempt list and the carrier census); the warning is on 0.013% of the amateur-radio
  rows, 0.017% of the tax-exempt list, 0.024% of the carrier census, and 1 of 1,138,982 Netsyms sample rows.

- **A warning for a letter after the house number that was read into the street name** (#102): `ambiguous_number_letter`
  for `123 A MAIN ST` (street `A MAIN`), where the letter may be the number's suffix (`123A`). The reading is not changed
  and no key moves. It is not raised when the letter is stuck to the number, is a directional, is the whole street name
  or is the `U` of `U S ROUTE`.
- **`docs/warnings.md`: what each warning tells you** (#102), in two groups (look at these rows; informational), with
  the measured rate at which rows that carry each code disagree with labeled data (a 1M-row NAD sample, and the NC voter
  pair for the unit), and `label_score.py --by-warning` to regenerate it.

- **Three warnings for a second address line that is used or dropped without a component of its own** (#45):
  `second_line_skipped` (a copy of the end of line 1 or of the city, or a line of no-data markers, dropped),
  `second_line_in_street` (line 2 joined the street that line 1 began: a route, a suffix or a directional) and
  `second_line_building` (kept as the building name, which no emitter prints). They report what the parser already
  did; no component and no key changes. A row that has such a line now carries a warning where it had none, so a
  pipeline that treats "no warnings" as clean sees about 0.015% more rows flagged (the 21,825 of 146.6M that
  the Netsyms review counted).

- **The state data version in the output** (#7): `provenance.state_data_version` in the command-line JSON and in
  `to_dict()`, `ParsedAddress.state_data_version` in Python and `Diagnostics::state_data_version` in Rust,
  beside the library version. It is the `version` in the `state.toml` of the address's state (Florida's is
  `2026.10.5`), or `None` when the state has no curated data. `Lexicons::state_data_version(state)` is the lookup.
  An added field only: no existing value or key changes.

## [0.3.1] - 2026-10-22

A patch release: `doorplate --version`, the care-of line with a percent sign, and a quieter warning for Queens
house numbers. The key format stays `k2`, but **one correction changes the keys of some inputs** (the
second entry below): inputs with a `%` care-of line or `IN CARE OF` that 0.3.0 keyed wrongly. If you stored keys for
addresses like those, re-parse them; no other input's key changed (measured against the released 0.3.0 over
about 19 million rows from five sources).

- Provenance (issue #85): `doorplate --version` (and `-V`) prints the library version, `--help` (and `-h`) prints
  the usage and exits 0, and the JSON from `doorplate parse` and Python's `to_dict()` carry
  `provenance.library_version`. A new field in the output, not a change to any existing value or match key. The state data
  version (#7) will join the same `provenance` group.

- Parsing: an in-care-of line written with a percent sign (`% JOHN SMITH`, `%JOHN SMITH`) and `IN CARE OF NAME`
  are read as the attention line, in line 2 and in one-line input alike. Before, the `% NAME` text stayed
  in `unparsed` with an `unparsed_remainder` warning (64% of the rows of the IRS exempt-organization
  extract), and `IN` was left over from `IN CARE OF`.

  **Keys changed for these inputs.** In 0.3.0 the leftover text pushed the tail of line 1 (a unit, a floor)
  into the street name, so the street part of the key was wrong (`MAIN ST 5TH FL` instead of `MAIN`, `ST`); now it
  is right, so the key differs from 0.3.0's. Compared with the released 0.3.0 row by row: 172,455 of the
  1,975,975 IRS rows (8.7%), 799 of 5,929,426 NY corporation rows, 59 of 9,038,491 FMCSA rows and 18 of
  1,676,974 FCC rows get a different key, and every one has a `%` care-of marker or `IN CARE OF`; no key changed in
  the Netsyms sample (1,138,982 rows) or the Texas file (211,009). This is a one-off correction under `k2`, not a new
  key version (`docs/key-format.md`, "Version history"). Issue #97. An earlier version of this entry said keys do
  not change; that was wrong.

- Warnings: a hyphenated house number with a larger second part (`21-77 31ST ST`) no longer raises
  `multiple_addresses` when the place resolves to Queens County, New York, where the part before the
  hyphen is the cross street. Ranges elsewhere (`1204-1206 MAIN ST`, and in Manhattan) still warn. Only the
  warning changes; the number and the key do not (issue #99; the twin `2177 31ST ST` keys apart: #109).

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
