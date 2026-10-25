# Changelog

All notable changes are listed here, newest first. The project follows
[Semantic Versioning](https://semver.org/). The canonical key format has its own
version (currently `k3`), tracked separately in [`docs/key-format.md`](docs/key-format.md): a
change to what an input produces needs a new key version.

## [Unreleased]

### Changed

- **Faster, and a little more accurate where the rules went** (0.3.1 to 0.4.0, measured back to back on one machine; the
  tables are in [`docs/benchmarks.md`](docs/benchmarks.md#031-to-040)). Ordinary input is unchanged: the suite's `natural`
  stratum is 98.3% on both builds (the whole suite 92.2% to 92.3%, the `hand` stratum 92.3% to 94.3% from #78). Geocode dev goes from 94.4% to 94.5%, fields input from
  98.9% to 99.1%, unit numbers from 96.8% to 97.8%, and the share of wrong parses that raise a warning from 43.9% to
  54.7%. Python `parse` on the geocode addresses goes from 34,149 to 38,463 per second (+13%), `parse_tokens` +19%, and
  `parse_many` on four threads from 113,873 to 137,876 (+21%); one address in Rust takes 12.4 µs instead of 17.3 µs
  (a full one-line address, -28%). The CLI binary grows from 5.0 to 5.5 MB; the wheel stays 1.8 MB.
- **The key is now `k3`** (**breaking**: every stored key re-keys; store the prefix, re-parse to re-key). The segment layout
  is the same as `k2`; the prefix is `k3:` (`k3n:` with no state or ZIP), and the value of some keys changes because 0.4.0
  reads some inputs differently, each marked "held for the `k3`" below. Measured against the frozen `k2` keys of the
  foundation checkpoint (the prefix left out of the comparison) over 36,920,703 rows in seven large sources: **482,869 keys
  change (1.31%)**: NY corporations 331,765, Netsyms 56,947, carrier census 47,439, NC voter 17,971, IRS 16,987, amateur
  radio 7,758, NAD 4,002. The Queens house number (#109) is most of it (383,510 of the 482,869 when measured on its own,
  79%). Every other key keeps its value and changes only the prefix. A full Netsyms run on `main` (146,622,381 US rows) finished with no errors.
- **A lone directional on line 2 is a unit** (#170, **held for the `k3`**: 712 keys change): `123 MAIN ST` / `N` had the
  postdirectional `N` (`second_line_in_street`); NAD's labels say a unit for 88.8% of such rows (584 of 658). Now a lone
  directional of at most two letters on line 2, after a line 1 that already ends in its street suffix, is the unit `N`.
  Line 1 with no suffix, a postdirectional already there, or two words on line 2 are unchanged. Measured: 712 keys change in the seven large sources (NAD 524, NC voter mailing 147, NY corporations 41, others 0), each a street that loses a postdirectional and gains a unit, with `second_line_in_street` removed.
- **In Queens the key drops the hyphen of the house number** (#109, **held for the `k3`**: 383,510 keys change): `37-12 82ND
  ST` and `3712 82ND ST` were one building with two keys (14.6% of the hyphenated Queens addresses in a New York registry
  also appear without the hyphen). When the resolved place is in Queens, NY, a number of one to three digits, a hyphen, two
  digits and an optional letter (`37-12`, `37-12A`) keys without the hyphen, so both forms give `k2:S|3712||82ND|ST||NY|11354`.
  Elsewhere the hyphen stays (`20-22 W 45TH ST` in Manhattan is two numbers). `street_number` and the slug keep what was
  written. Measured: 383,510 keys change in the seven large sources (NY corporations 306,725, Netsyms 56,391, carrier census 14,785, NAD 3,355, amateur radio 1,269, IRS 847, NC voter 138), every one a New York key that loses the hyphen of its house number and nothing else; no warning changes.
- **`CR` is CIRCLE and `CTY HWY`, `CTY RD`, `CTY ROAD` are county roads in every state** (#108, **held for the `k3`**: 8,080 keys
  change): three readings that only Florida had, because that is where the evidence was first collected. `CR` after a
  street name was `CREEK` outside Florida; it is now `CIRCLE` (`12 BAYVIEW CR` is `BAYVIEW CIR`), still with
  `non_standard_abbreviation`, and `CR` before a route number stays `COUNTY ROAD`. `CTY HWY`, `CTY RD` and `CTY ROAD` before
  a route number are `COUNTY HIGHWAY` and `COUNTY ROAD` (a Minnesota `3709 CTY RD 214` was a street `CTY`, suffix `RD`,
  unit `214`, and the route number was lost); `CTY` alone stays `CITY`. The two Florida overrides are gone; `SR` stays
  Florida's. Measured: 8,080 keys change in the seven large sources (carrier census 6,801, amateur radio 852, IRS 177, NY corporations 147, NC voter 80, NAD 19, Netsyms 4): `CR` to `CIR` 3,149, `CTY RD` and `CTY ROAD` to `COUNTY ROAD` 3,939, `CTY HWY` to `COUNTY HIGHWAY` 992; nothing else changes.
- **Pre-split fields get the state's data for highways** (#110, **held for the `k3`**: 1,086 keys change): in Florida
  `22200 SR 60` was `STATE ROAD 60` on one line (`parse("22200 SR 60, LAKE WALES, FL 33898")`) but a street named `SR 60`
  through `parse_fields`, so one address had two keys; `CTY HWY` had the same gap. The highway pass now gets the state
  (from the state field, or the ZIP) before it reads line 1, as it does on one line. The suffix override (`CR` as `CIR`)
  already worked on both. All 1,086 changes are Florida highway readings.
- **A spaced letter after a rural route box number is part of the box** (#95, **held for the `k3`**: 4,824 keys change): `RR 2 BOX 45 A` and
  `HC 63 BOX 4 B` had the box `45` and `4` with the letter left unparsed (`unparsed_remainder`). Now the box is `45A` and
  `4B`, as the joined form `RR 2 BOX 45A` already was. One lone letter after a numeric box, on the same line; a PO Box is
  unchanged. Measured against the build before this rule: 4,824 keys change in the seven large sources (carrier census 4,283, amateur radio 457, IRS 54, NC voter 14, NY corporations 16, NAD 0, Netsyms 0), every one a rural route or highway contract key that gains a box letter.
- **A letter after a hyphenated house number is part of the number** (#100, **held for the `k3`**: 4,998 keys change): `12-34A MAIN ST` had no
  street number (`missing_street_number`, the number left in the street name `12-34A MAIN`). Now `12-34A` is the number, as
  `12-34` and `1234A` already were. One letter only; `12-34AB` and `12A-34` are unchanged, and `1204-1206A` is a number, not
  a range. Measured against the build before this rule: 4,998 keys change in the seven large sources (NY corporations 4,286, carrier census 560, amateur radio 84, IRS 44, Netsyms 16, NC voter 8, NAD 0), and `missing_street_number` is removed from every one.
- **`LOOP` after a street name is the suffix, and a number after it a unit** (#145, **held for the `k3`**: 518 keys change): `1305 MAPLE COVE
  LOOP 412` had the street name `MAPLE COVE LOOP 412` with no suffix, because `LOOP` is a highway word (`LOOP 410`) and a
  number after a highway word is its route. Now `LOOP` with a name before it is a suffix like `CIR` or `DR`, so the number
  is a bare unit (`MAPLE COVE`, `LOOP`, unit `412`). `LOOP 410` at the start of the street is still a route. Measured against the build before this rule: 518 keys change in the seven large sources (carrier census 269, amateur radio 72, IRS 69, NY corporations 78, NAD 16, Netsyms 9, NC voter 5), all of the shape name, `LOOP`, number.
- **`BAY` at the end of a street name is part of the name** (#144, **held for the `k3`**: 97 keys change): `1305 HERON BAY #
  2B` and `1305 HERON BAY 2B` had the street `HERON` and a unit `UNIT 2B`, because `BAY` is an observed unit
  designator (an industrial bay). Now `BAY` is a unit designator only after a street suffix (`MAIN ST BAY 4`), on a later
  line, after a `#`, or after a word with a digit; after a plain name it is part of the street (`HERON BAY`, with a bare
  unit `2B`). Measured against the build before this rule: 97 keys change in the seven large sources, 95 of them a
  street name that now ends in `BAY`, and `non_standard_abbreviation` is removed from those 97. NAD's labels agree (433
  of 462 rows have a street name ending in `BAY`).
- **A word before a trailing `CT`, `KY`, `MT` or `WY` is no longer cut in two** (#143, **held for the `k3`**: 15,725 keys
  change): in pre-split fields `1305 PINEBRIAR CT` had the street name `PINE BRIAR` (and `TRELLIS CT` had `TR ELLIS`,
  `STORCH CT` had `ST ORCHARD`), because the tokenizer took `CT` for Connecticut ending a city glued to the street. A state
  code that is also a street suffix now ends a glued city only when a ZIP of that state follows. Measured against the
  build before this rule: 15,725 keys change in the seven large sources (about 0.04% of rows, no warning changes), 15,713
  of them the same name without the cut; the 6 NAD rows match NAD's labels. `STHARTFORD CT 06103` still splits.
- **A department name is an attention line, not a unit** (#166, **held for the `k3`**: 31 keys change): on a later line or
  comma segment, two or more words with no digit ending in `DEPT` or `DEPARTMENT` (`MATH DEPT`, `HUMAN RESOURCES
  DEPARTMENT`) were a unit `DEPT` with no number and their words in `unparsed`. `DEPT 4`, a street named `FIRE DEPT RD`,
  a line that starts with a designator (`SUITE B ...`) and a department alone on line 1 are unchanged. Measured against
  the build before this rule: about 220 rows change (216 NY corporations, 2 IRS, 2 NAD; the IRS department lines mostly
  start with `%` and were already attention lines); `missing_unit_number` is removed from 218 rows and
  `unparsed_remainder` from 217; the 31 key changes are streets that had a department joined to them by a dash.
- **Misspelled PO BOX words are read as PO Boxes** (#165, **held for the `k3`**): `P O BX 1234`, `P BOX`, `POX`, `PO BOX BOX`,
  `P OBOX`, `PO OX`, `PO POX`, `POX BOX`, `PO OBX`, `POP BOX` and `P O OX` are forms of PO BOX (they were streets with
  `missing_street_number`), with no warning (as `POB`). Measured against the build before this rule: 869 keys change
  in the seven large sources (807 `S` to `P`; 52 street keys that no longer hold box words, now with `dual_address`;
  6 route and military boxes); `missing_street_number` is removed from 827 rows. This also fixes two unreleased
  readings: a recipient is no longer taken ahead of a box that starts the line (`FIRM CALLER 4410`, from #127), and a
  country-only street field with an attention line (`USA` / `% NAME`) is dropped again (from #130).
- **Lines with no street are no longer read as a street name** (#130, **held for the `k3`**: the key becomes `None`): a lone
  number (`4871`) is a house number with `missing_street_name` (it was the street name `4871`), a bare `PO BOX` or `PO`
  stays in `unparsed` (it was the street name `PO BOX`), and a street field that is only a country (`UNITED STATES`,
  `USA`) next to a city, state or ZIP field is dropped with `country_ignored` and `missing_street_name`. A line that is only an organization name is
  unchanged. Measured against the build before this rule: 9,555 keys in the seven large sources change, all to
  `None` (carrier census 6,064, IRS 2,236, NY corporations 710, amateur radio 283, NC voter 182, NAD 54, Netsyms 26);
  `missing_street_name` is added to 8,637 rows, `unparsed_remainder` to 914 and `country_ignored` to 5, and
  `missing_street_number` is removed from 9,555.
- **A floor written as an ordinal and `FL` is a floor when the state is `FL`** (#114, **held for the `k3`**: it changes the
  unit and the unit-level key): `123 MAIN ST 5TH FL` and `123 MAIN ST THIRD FL` with state `FL` are floor 5 and floor
  3; the repeated-state rule had dropped the `FL` and left `5TH` as a bare unit. The ordinal must follow a street suffix
  (`123 5TH FL` is the street `5TH`), and a plain number (`5 FL`) is unchanged. 82 rows of the large sources have the
  shape and 67 change; one key changes (of 37M rows). `THIRD FLOOR` (the second problem of the issue) was fixed with
  #129. The harness (`tools/harness`, schema version 8) now compares an ordinal by its number in the `street` check
  (`5TH` equals `5`), so a correct floor is no longer a false mismatch.
- **Spelled-out numbers are read as numbers** (#129, **key-affecting, held for the `k3`**): `ONE COMMERCE PLAZA`, `TWO
  BAYVIEW LANE 15TH FLOOR` and `ONE NORTH MAIN ST` have the house number 1 or 2 (a number word `ONE` to `TWENTY` at the
  start of a street line, when a name and a street suffix follow), `SUITE TWO` is suite 2, and `THIRD FLOOR` is floor 3.
  `ONE MILE RD`, `THREE FORKS RD`, `TWO RIVERS DR` and `FOUR CORNERS RD` stay streets (`[numbered_street]` in
  `data/special.toml`). `FLR` is an observed spelling of FLOOR (`non_standard_abbreviation`). Pub 28 does not say how a
  spelled-out number is written, so the data is the source (section 235 only covers numeric street names). Measured
  against the build before this rule, 26,132 keys change (16,808 NY service-of-process addresses, 4,148 other NY
  corporation rows, 2,740 carrier census, 2,091 IRS, 288 amateur radio, 57 NC voter); `missing_street_number` is removed
  from 18,500 rows, `unparsed_remainder` from 10,611 and `missing_unit_number` from 6,239, and
  `non_standard_abbreviation` is added to 11,738 (the `FLR` spelling).
- **Recipient text ahead of the address is the attention line, not part of the street** (#127, **key-affecting, held for the
  `k3`**): `C/O ACME CORP 20 QUINCEWOOD CT` (the attention line took the whole line and the street was empty),
  `CO ACME INC 120 QUINCEWOOD AVE` and `CO 612 QUINCEWOOD ST` (`CO` for `C/O`, not the county highway),
  `ACME FOUNDATION 500 BAYVIEW RD` (no marker) and `ACME CO PO BOX 12345` (a name ahead of a box) now keep their house
  number or box and put the words in `attention`. Measured against the frozen checkpoint keys, 13,547 keys change
  in the seven large sources (5,494 IRS, 4,091 NC voter mailing, 1,870 amateur radio, 1,193 carrier census, 895 NY
  corporations, 3 Netsyms, 1 NAD), and `missing_street_number` is removed from about 12,000 rows. A county-highway prefix, a unit designator, a route or box word, a
  directional, any digit, a single letter or a word such as `BLOCK`, `NO` or `URB` among the leading words leaves the
  line as before (`[non_recipient]` in `data/special.toml`). The Netsyms sample changes in 3 rows.
- **Units written as two numbers, with `BOX`, `NO`, `NUM` or `LOC`, cut off or twice stay out of the street name** (#128, **key-affecting,
  held for the `k3`**): `1200 QUINCEWOOD RD NW STE 180 417020` (unit `180 417020`), `2100 E BAYVIEW BLVD 250 3440`,
  `1500 QUINCEWOOD BLVD BOX 3300`, `2400 BAYVIEW PKWY NO 65`, `9900 N BAYVIEW PKWY E NUM 230` and `... LOC 12` (a unit with
  no type; Pub 28 lists none of these words as a designator, so this is the data's reading), `1300 ZEPHYRMILL AVE NW
  SUIT` and `... 15TH FLOO` (a cut-off designator is read, with `non_standard_abbreviation`), and `STE STE C` (one
  designator). `FLO` and `FLOO` are observed spellings of FLOOR. Measured against the frozen checkpoint keys: 18,020 keys
  change in the seven large sources (8,073 carrier census, 5,882 IRS, 1,950 amateur radio, 1,847 NY corporations,
  235 NC voter, 26 NAD, 7 Netsyms); `possibly_truncated` is removed from 3,312 rows, `unparsed_remainder` from 1,807 and
  `missing_unit_number` from 340, and `non_standard_abbreviation` is added to 653. A street named for the word
  (`12 BOX ST`, `123 FLOOR ST`) is unchanged; so is a single-letter floor (`18TH F`).
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
