# Golden corpus

Labeled addresses with their expected parse, one JSON record per line in
`*.jsonl`. The runner is the `doorplate::corpus` module (feature `corpus`),
run by `crates/doorplate/tests/corpus.rs` and by `doorplate corpus test`:

```sh
doorplate corpus test [--verbose] [--update-baseline]       # same runner, from the CLI
cargo test -p doorplate --test corpus -- --nocapture   # accuracy report
CORPUS_VERBOSE=1 cargo test -p doorplate --test corpus -- --nocapture   # plus field diffs
UPDATE_CORPUS_BASELINE=1 cargo test -p doorplate --test corpus   # record passing cases
```

The corpus may be ahead of the parser: a failing case does not fail the
test. `passing.txt` lists the cases that pass; the test fails if one of them
stops passing (a regression), or if the corpus is malformed. When a change
makes more cases pass, rerun with `UPDATE_CORPUS_BASELINE=1` and commit the
updated `passing.txt` with it.

Every parsing bug fixed gets a case here (`CONTRIBUTING.md`).

## Record format

```json
{"id": "cty-street-005", "input": "4158 INVERRARY DR #309",
 "expect": {"street_number": "4158", "street_name": "INVERRARY", "street_suffix": "DR", "unit_number": "309"},
 "warnings": ["missing_city", "missing_state", "missing_zip"],
 "note": "# designator: unit_type stays empty"}
```

- `id`: unique across all files. Prefixed with the source: `cty-`
  (shapes seen in Florida county address listings, `county-data.jsonl`),
  `cty-golden-` (the same, from raw listing lines, `county-data-golden.jsonl`), `p28-`
  (Pub 28 examples), `rg-` (regressions), `key-`, `reso-` (emitter cases),
  `fl-` (Florida state data, `fl-state.jsonl`), `pl-` (national place list outside
  Florida, `places-us.jsonl`), `ds-` (`default_state`, `default-state.jsonl`),
  `tg-` (`tag()` and `address_type()`, `tag.jsonl`),
  `co-` (trailing country, `country.jsonl`),
  `sl-` (a second line used or dropped, `second-line.jsonl`),
  `ns-` (street lines with no street, `nostreet.jsonl`),
  `pb-` (misspelled PO BOX words, `pobox.jsonl`),
  `dp-` (department names, `dept.jsonl`),
  `gl-` (a word glued to a state-like suffix, `glue.jsonl`),
  `by-` (BAY in a street name, `bay.jsonl`),
  `hn-` (hyphenated house number with a letter, `hyphen.jsonl`),
  `rb-` (a spaced letter after a rural route box number, `rrbox.jsonl`),
  `ff-` (state data on pre-split fields, `fields-state.jsonl`),
  `cy-` (CR as CIRCLE and the CTY highway spellings, `county.jsonl`),
  `qk-` (Queens house numbers in the key, `queens.jsonl`),
  `ld-` (a lone directional on line 2, `lonedir.jsonl`),
  `lp-` (LOOP and a number after a name, `loop.jsonl`),
  `rc-` (recipient text ahead of the address, `recipient.jsonl`),
  `un-` (units left in the street name, `units.jsonl`),
  `sp-` (spelled-out numbers, `spelled.jsonl`),
  `is-` (intersections, `intersections.jsonl`),
  `nl-` (name lines with commas and two leading units, `name-lines.jsonl`),
  `rt-` (repeated text and its warning, `repeated.jsonl`),
  `zr-` (a nearly right ZIP repaired, `zip-repair.jsonl`),
  `gf-` (a floor written as a plain number and the floor word, `glued-floor.jsonl`),
  `nlt-` (a letter after the house number, `number-letter.jsonl`),
  `cn-` (a compass word naming the street, `compass-street.jsonl`),
  `pz-` (a PO Box or unit number equal to the ZIP, `pobox-zip.jsonl`),
  `bx-` (BOX and a number after a name with no suffix, `box-bare-name.jsonl`),
  `ub-` (a bare BOX after a unit, `unit-then-box.jsonl`),
  `nb-` (PO BOX with no number at the end of a street, `bare-po-box.jsonl`),
  `nm-` (words only on line 2 under a PO Box, `name-after-box.jsonl`),
  `hu-` (a `#` before a unit designator, `hash-before-designator.jsonl`),
  `nat-` (shapes found in a national address database, `national-data.jsonl`);
  `us-roundtrip-001` in `regressions.jsonl` came from the USPS round trip.
- Exactly one input form:
  - `input`: a single-line string, passed to `Parser::parse`.
  - `lines`: an array of address lines as the source gave them (for example
    a street line and a `CITY, ST ZIP` line). Two lines are passed to
    `Parser::parse_fields` as `line1` and `line2`, which reads them like one
    line when city, state and ZIP are empty; one line goes to `parse`, and
    more are joined with `", "`.
  - `fields`: `{line1, line2, city, state, zip}`, passed to
    `Parser::parse_fields`.
- `expect`: expected `ParsedAddress` components, named as the struct fields
  are, plus `unparsed` (`Diagnostics::unparsed`). **An absent key means that
  component must be empty**, so a parser that fills in extra parts fails.
  Structured values:
  - `rural_route`: `{"kind": "RR" | "HC", "route": "2", "box": "152"}`
  - `highway`: `{"prefix": "COUNTY ROAD", "route": "23"}`, with the
    standard prefix from `crates/doorplate/data/special.toml` `[[highway]]`, plus `"state": "KY"`
    when the name holds a state (`KY STATE HIGHWAY 1`, Appendix F)
  - `military`: `{"kind": "PSC", "number": "1650", "box": "10"}`
  - `military_post_office`: `"APO"`, `"FPO"` or `"DPO"`
  - `general_delivery`: `true` (absent means false)
  - `building`: the building name as tokens joined (`"EAST TOWER"`)
  - `attention`: the attention or care-of line as tokens joined
    (`"ATTN LAW DEPT"`, `"C/O YMF"`)
  - a dual address (street and PO Box) fills both the street fields and
    `po_box`, with the `dual_address` warning
  - `second_unit_type`, `second_unit_number`: a second unit after the
    first, in input order
- `warnings`: `Warning::code()` strings. Compared as a set, exactly: missing
  or extra warnings both fail.
- `note`: optional, why the case is there or why it is labeled this way.

Emitter expectations are optional record keys, checked only when present
(unlike `expect`, absent means not checked):

- `key`: the property-level key string (`KeyOptions::property()`), or
  `"none"` when the address has no key.
- `key_unit`: the same for `KeyOptions::unit()`.

- `slug`: the expected `slug()` string, or `"none"`.

- `usps`: `{"line1": ..., "line2": ..., "last_line": ...}` from
  `to_usps()`; an omitted part must be empty.

- `address_type`: the expected `ParsedAddress::address_type().code()`:
  `street`, `po_box`, `rural_route`, `military`, `general_delivery`, `dual`
  or `unknown`. Absent means not checked.

- `tag`: the expected `ParsedAddress::tag()`, an object from usaddress label
  to joined value (`{"AddressNumber": "123", "StreetName": "Main"}`); a label
  not listed must be absent. `tag_repeated` lists the labels `tag()` joined
  from separate runs (two units give `OccupancyType` and
  `OccupancyIdentifier`). Absent `tag` means not checked.

- `default_state`: a state (code or name) passed as
  `ParseOptions::default_state` for this case, so the hint cases (`ds-*`) can
  run in the one corpus. Absent means no hint.

- `place`: `ParsedAddress::place` as `"NAME (source)"`, with the state data's
  standard name and the `PlaceSource::code()` (`"WEST PALM BEACH (name)"`,
  `"FERNANDINA BEACH (completed)"`, `"PENSACOLA (zip)"`), or `"none"`.
  These cases need the state data, which is always built in.

- `reso`: an object of Data Dictionary 2.0 field names to the expected
  `to_reso()` values (`{"StreetName": "MAIN", "City": "MIAMI"}`). A field not
  listed must be empty. Names are checked against the Data Dictionary address
  fields; `StreetNumberNumeric` is written as its decimal text. Write expected
  values from `docs/reso-mapping.md`, not by copying the emitter's output.

Most cases in `county-data.jsonl`, `county-data-golden.jsonl`,
`pub28.jsonl` and `regressions.jsonl` carry `key`, `key_unit`, `slug` and
`usps` expectations, and the ones with a state and ZIP also `reso`. They were
generated from each case's hand-labeled `expect` by
`tools/corpus/emit_expect.py`, a second implementation of the rules in
`docs/key-format.md`, `docs/reso-mapping.md` and Pub 28 that never reads the
emitters, so a disagreement shows up as a failing case. Cases are left out
when the label itself is a judgment call: `unparsed` text, or the warnings
`possibly_truncated`, `ambiguous_street_number`, `multiple_addresses`,
`invalid_zip` and `ambiguous_token`. Placeholders get `none` for key and slug
and an empty `usps`. When you add a case, run the script on the file (it adds
only the fields that are missing) and review the diff. `--check` compares
every stored expectation with what the script computes and exits 1 on a
difference; CI runs it, so a rule change in the emitters or the specs has to
reach the script too.

The runner rejects unknown keys, duplicate ids, unknown warning codes, and
suffix, unit, state, directional, highway-prefix or military values that are
not standard forms from the lexicon tables.

## Labeling conventions

- Values are written as the parser should store them: uppercase, periods
  dropped, suffixes, directionals, unit designators and states as their
  standard abbreviations (`CIRCLE` -> `CIR`, `EAST` -> `E`, `UN` -> `UNIT`).
  Names keep their own words (`6th` -> `6TH`, `St. Petersburg` ->
  `ST PETERSBURG`; expanding `ST` to `SAINT` in a place name is a state-data
  job).
- A unit with no designator (`DR 706`) or with `#` has an empty `unit_type`
  and only a `unit_number`. Pub 28 C2 uses `#` when the designator is
  unknown, so the USPS emitter writes both as `# 706`.
- The parser does not guess. A token it cannot place confidently goes to
  `unparsed` (`409742ND SQ`, `5210/5212`).
- Warnings follow these rules, so labels stay consistent:
  - `unparsed_remainder` exactly when `unparsed` is set.
  - `missing_city`, `missing_state`, `missing_zip` whenever that component is
    empty, including for street-only lines and placeholders. An APO, FPO or
    DPO in the city position counts as the city.
  - `missing_street_number` when there is a street name or highway but no
    number; `zero_street_number` replaces it for house number 0. Neither is
    raised when nothing street-like was found, or for PO Box, rural route,
    general delivery and military lines.
- A highway address keeps the prefix and route in `highway` and leaves
  `street_name` empty. Words after the route are labeled as on any street:
  `HWY 11 BYPASS` has suffix BYP, `US 41 SW` has postdirectional SW.
  - `invalid_zip` replaces `missing_zip` when there is a ZIP-like token that
    is not a valid ZIP (a cut-off `3`); the token goes to `unparsed`.
  - A placeholder line is consumed whole: `placeholder`, nothing in
    `unparsed`.

The tagger follows these conventions; its rules and their sources are in
`docs/usps-pub28-notes.md` ("Parser rules").

## Files

Ids are never a public contract; a case can be renamed or merged.

### `county-data.jsonl`

Ids `cty-street-`, `cty-full-`, `cty-placeholder-` and `cty-highway-`.
Address shapes seen in Florida county property listings, hand-labeled in this
library's schema: house number letters, units with and without designators,
highways, placeholders such as `UNKNOWN` and `NO SITUS`. Cases that need a
place list are in `fl-state.jsonl` instead.

### `county-data-golden.jsonl`

Ids `cty-golden-001` and up. One case per distinct shape in raw address lines
from eight Florida county listings. Only the inputs were taken; the expected
values were labeled by hand, not copied from any parser's output.

### `pub28.jsonl`

Built from the examples in USPS Publication 28 (`docs/usps-pub28-notes.md`
has the page for each section): the highway table in section 237 and the
"Examples in Use" column of Appendix F, the PO Box (281, 283), rural route
(241, 244), highway contract route (251, 253) and general delivery (261)
formats, and the military and Department of State examples in sections
225.1, 238.1 and 239. Inputs use the spellings Pub 28 says to change, and
the expected values are the standard forms it gives. House numbers are only
present where Pub 28's example has one.

### `regressions.jsonl`

Cases for parsing bugs found over time, from Florida address data and from
other tests (`CONTRIBUTING.md`: every parsing bug fixed gets a case). Ids start with
`rg-`; each note says what went wrong.

### `keys.jsonl`, `reso.jsonl`

Cases that pin the emitters: exact `k3` key and slug strings (`key-`) and RESO
field values (`reso-`), written from `docs/key-format.md` and
`docs/reso-mapping.md`.

### `fl-state.jsonl`

Every folder under `crates/doorplate/data/states/` needs a file like this one, `<st>-state.jsonl`, with cases
from that state; a test fails when one is missing.

Ids `fl-001` to `fl-047`. The Florida state data and the national place list on
Florida input: a city on one line with no commas, a city run into the street,
cut-off cities completed, the place from the ZIP, `zip_city_mismatch`, the
observed ZIP places, `CR` as CIRCLE, `SR` as STATE ROAD, and communities and
spellings added to the Florida data (`docs/states/fl.md`). `fl-013` and `fl-019` are
Georgia and Colorado inputs that show a state with no curated state data. They need
the default feature `places-us`.

### `places-us.jsonl`

Ids `pl-001` to `pl-021`. The same place behaviors in states with no curated
state data (`ST LOUIS`, `NORTH LITTLE ROCK`, `LA GRANGE PARK`, `ROARING BROOK TWP`, a
cut-off city, the place from the ZIP), and `zip_city_mismatch` not raised
there; and a county written as the city (`city_is_county`, `pl-009` to `pl-013`); and a municipality prefix before the city (`VILLAGE OF PINECREST`, `pl-014` to `pl-021`).

### `default-state.jsonl`

Ids `ds-001` to `ds-007`. Cases with a `default_state` field: a comma-less
city found in the hinted state, the state's data readings, a city not in the
hinted state, and the input's own state or a known ZIP winning over the hint.

### `second-line.jsonl`

Ids `sl-001` to `sl-024` (#45, #126; `sl-016` to `sl-024` are the care-of line after a street: a copy, a digit-led name, a unit that is now parsed, and the bare number and second address that stay unparsed). A second address line that is used or dropped without a component of its own is
reported: a copy of line 1 or a no-data line (`second_line_skipped`), a route, suffix or directional that joins
the street of line 1 (`second_line_in_street`) and a building name (`second_line_building`); and the near misses
that get no warning: a unit, a street on line 2 alone, a dual address, an attention line, no line 2, the last line
on line 2.

### `recipient.jsonl`

Ids `rc-001` to `rc-015` (#127). Recipient text ahead of the address on line 1: after `C/O` or `ATTN`, after `CO`
(for `C/O`), with no marker, and ahead of a PO Box; with the number kept and the words in `attention`. The near
misses that must not change: a county road (`COUNTY ROAD 12`, `CO RD 12`), `C/O` directly before the address, and a
unit designator ahead of the address.
### `units.jsonl`

Ids `un-001` to `un-018` (#128). Units that stayed in the street name: two numbers after a designator or the suffix,
`BOX`, `NO`, `NUM` and `LOC` after a street, a designator cut off (`SUIT`, `FLOO`, `FLO`) and a designator written
twice; and the near misses that must not change (a street named `FLOOR`, `UNIT`, `NUM`, `BOX` or `NO`, a PO Box with a
unit, a plain unit).

### `spelled.jsonl`

Ids `sp-001` to `sp-016` (#129). Spelled-out numbers: a house number word ahead of a name and a suffix (`ONE COMMERCE
PLAZA`, `TWO BAYVIEW LANE 15TH FLOOR`), a unit number word (`SUITE TWO`, `UNIT ELEVEN`), a spelled ordinal before a
floor (`THIRD FLOOR`), `FLR`; and the near misses that must not change (`ONE MILE RD`, `THREE FORKS RD`, `TWO RIVERS
DR`, `FOUR CORNERS RD`, a street named `THIRD FLOOR`).

### `nostreet.jsonl`

Ids `ns-001` to `ns-012` (#130). Street lines with no street: a lone number (`missing_street_name`, no key), a PO Box
word with no number (`unparsed_remainder`), a line that is only a country (`country_ignored`); and the near misses
that must not change (`5TH ST`, `1 A ST`, `PO BOX 12`, a lone number with its street on line 2, a country ahead of a
street on line 2).

### `pobox.jsonl`

Ids `pb-001` to `pb-018` (#165). The eleven misspellings of PO BOX read as a box, a misspelled box with a unit, after a
street (`dual_address`), a misspelled word with no number (unparsed); and the near misses that must not change (streets
named `POX`, `P`, `POP`, the standard spelling).

### `dept.jsonl`

Ids `dp-001` to `dp-010` (#166). A department name on line 2 or after a comma (`MATH DEPT`, `HUMAN RESOURCES DEPARTMENT`)
as the attention line; and the near misses that must not change (`DEPT 4`, `DEPT. 4`, `DEPT #4`, streets named `FIRE
DEPT RD` and `FIRE DEPARTMENT RD`, an `ATTN` line).

### `glue.jsonl`

Ids `gl-001` to `gl-011` (#143). A word before a trailing `CT`, `WY`, `KY` or `MT` stays one word (`PINEBRIAR CT`, `TRELLIS
CT`), in pre-split fields and on one line; and the near misses that must not change (`CIR`, `LN`, a unit after `CT`, a
city glued to the street with a Connecticut ZIP).

### `bay.jsonl`

Ids `by-001` to `by-011` (#144). `BAY` at the end of a street name (`HERON BAY # 2B`, `HERON BAY 2B`, `HERON BAY W 45`)
is part of the name; and the near misses that must not change (`BAY` after a suffix or on line 2 is still a unit, a
street named `BAY` or `OYSTER BAY BLVD`).

### `loop.jsonl`

Ids `lp-001` to `lp-007` (#145). `LOOP` after a street name, then a number (`MAPLE COVE LOOP 412`) is the suffix and a
bare unit; and the near misses that must not change (no number, a designator, `LOOP 410` at the start of the street).

### `hyphen.jsonl`

Ids `hn-001` to `hn-009` (#100). The Queens house number with one trailing letter (`12-34A`, `123-45A`), alone, with an
ordinal street and with a unit; and the near misses that must not change (no letter, a letter on a plain number) or stay
unparsed (two letters, a letter on the first part).

### `rrbox.jsonl`

Ids `rb-001` to `rb-008` (#95). A lone letter after a numeric rural route or highway contract box number (`RR 2 BOX 45 A`)
is part of the box (`45A`); and the near misses that must not change (the joined form, no letter, a PO Box, two letters,
a letter on the next line).

### `fields-state.jsonl`

Ids `ff-001` to `ff-005` (#110). A reading only a state's data has (Florida `SR 60` is `STATE ROAD 60`, `CTY HWY` is
`COUNTY HIGHWAY`) applies to pre-split fields as it does to one-line input, with a state, with a ZIP alone; and the near
misses that must not change (another state, no state or ZIP).

### `county.jsonl`

Ids `cy-001` to `cy-009` (#108). `CR` after a name is `CIRCLE` in every state; `CTY RD`, `CTY ROAD` and `CTY HWY` before a
route number are `COUNTY ROAD` and `COUNTY HIGHWAY` outside Florida too; and the near misses that must not change (`CR`
before a route number, `CO RD`, `CTY` as `CITY`, a street named `CTY`).

### `queens.jsonl`

Ids `qk-001` to `qk-009` (#109). In Queens, NY the key drops the hyphen of `37-12` and `37-12A`, so a building written both
ways keys the same (`qk-001`/`qk-002`, `qk-003`/`qk-004`); and the near misses that keep the hyphen (Manhattan, the Bronx,
New Jersey, one digit after the hyphen).

### `compass-street.jsonl`

Ids `cn-001` to `cn-010` (#325). A spelled-out compass word and a street suffix (`44 WEST AVE 2B`) are the street's name and suffix, and the digit value after them is a unit, on one line and on line 2; and the near misses that must not change (an abbreviated direction before a name, a postdirectional, a letter after the suffix, no unit).

### `pobox-zip.jsonl`

Ids `pz-001` to `pz-005` (#260). A number after `PO BOX` (or `P.O. BOX`, or a unit designator such as `APT`) is the box or unit number even when it equals the ZIP5, and not a copy of the ZIP; and the near misses (a different number, a box alone on line 1).

### `box-bare-name.jsonl`

Ids `bx-001` to `bx-006` (#299). `BOX` and a number after a street name with no suffix is a unit (`640 PINEWOOD BOX 18`), as after a suffix; and the near misses (a suffix, a street named `BOX`, no name before `BOX`, a letter value).

### `unit-then-box.jsonl`

Ids `ub-001` to `ub-006` (#300). A bare `BOX` and its number after a unit (`STE 105 BOX 121`) is the PO Box with `dual_address`, as with a comma or `PO BOX`; and the cases that stay as they were (BOX after a suffix or a bare name).

### `bare-po-box.jsonl`

Ids `nb-001` to `nb-005` (#301). `PO BOX` with no number at the end of a street line is left unparsed, not part of the street name (`90 NE 5 AVE PO BOX`), a unit before it is still read; and the cases that stay (a box with a number, line 2).

### `name-after-box.jsonl`

Ids `nm-001` to `nm-006` (#303). Words only on line 2 under a PO Box line with no street are the attention line (`PO BOX 1234` / `JANE ROE`); and the cases that stay unparsed (a street suffix word, a digit) or already worked (the `%` marker, a street on line 1).

### `lonedir.jsonl`

Ids `ld-001` to `ld-008` (#170). A lone directional on line 2 (`N`, `NW`) after a line 1 that already ends in its suffix
is the unit, not the postdirectional; and the near misses that must not change (no suffix on line 1, a postdirectional
already there, a letter that is not a directional, two words on line 2).

### `country.jsonl`

Ids `co-001` to `co-015`: a trailing `USA`, `US`, `UNITED STATES` or
`UNITED STATES OF AMERICA` on one line, on its own line, in line 2, in the
city field and in the state field, each with `country_ignored`; and `US` as a
highway prefix, which is not a country.

### `national-data.jsonl`

Ids `nat-001` to `nat-023`: parser fixes found by comparing the parser with a
national address database. The addresses are invented (the database is not
redistributable and is not in the repository): words that merely begin with a
suffix spelling and end in a place name (`CREEKWOOD`, `PICO RIVERA`,
`AVENIDA DE LA LUNA`, `STRAND`), a word after `#`, values after a designator
(`APT I4`, `# 2WD`), a letter range (`APT A-D`), `U S ROUTE`, a postdirectional
`NE` before a city that starts with NE, a state code that is also a suffix
spelling (`CT`, `LA`, `WY`) settled by its ZIP, and `WASHINGTON DC`.

### `intersections.jsonl`

Ids `is-001` to `is-013`: two streets joined by `&`, `AND`, `@` or `AT`, with
the first street as components, the second in `unparsed`,
`intersection_detected`, and `none` for key and slug; plus the look-alikes that
are one street (`LAND AND SEA RD`, `BEACH AT SEA DR`, `STATE AND MAIN ST`,
`AT&T WAY`), which must not warn.

### `tag.jsonl`

Ids `tg-001` to `tg-008`. Cases with `address_type`, `tag` and `tag_repeated`:
one per address shape (street, PO Box, rural route, military, general delivery,
dual, unknown) and a repeated label (two units).

### `hash-before-designator.jsonl`

Ids `hu-001` to `hu-009` (#340). A `#` right before a unit designator and its value marks that unit (`# APT-4`, `#APT-18`, `# APT 4`, on line 1, line 2 and in one-line input; two units with the second written `# APT 4`); and the cases that keep their reading (`#4`, `APT #4`, `APT 4 # B`).
