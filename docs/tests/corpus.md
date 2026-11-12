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

- `id`: unique across all files, prefixed by the file's id prefix (table below). Ids are never a public contract; a case can be renamed or merged.
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

One row per `tests/corpus/*.jsonl`; a new file gets a row here and an id prefix no other file uses (grep `"id": "xx-` first; the corpus test reports duplicate ids).

| File | Id prefix | What it covers |
|---|---|---|
| `bare-po-box.jsonl` | `nb-` | `PO BOX` with no number at the end of a street line is left unparsed, not part of the street name |
| `bare-unit-word.jsonl` | `bw-` | A number before a designator word on line 2 (`4 REAR`, `408 SOUTH`) is the unit; a directional plus suffix is a street name |
| `bay.jsonl` | `by-` | `BAY` at the end of a street name is part of the name; after a suffix or on line 2 it is still a unit |
| `blvd-direction.jsonl` | `bd-` | A suffix-word street (`BOULEVARD`, `PARKWAY`) with a direction after it, so the USPS line reads back; `AVENUE N` stays a lettered street |
| `box-bare-name.jsonl` | `bx-` | `BOX` and a number after a street name with no suffix is a unit, as after a suffix |
| `box-first.jsonl` | `bf-` | A box first, then a street (`BOX 3310 FERNLEAF RD`); `PMB` before a PO Box |
| `box-road.jsonl` | `br-` | Street words after a box number are the road the box is on; the key stays the box's |
| `campus-box.jsonl` | `cb-` | A school code then `BOX`, `CPO` and a number: a campus box, the code is the attention line |
| `care-of-front.jsonl` | `cof-` | `C/O` and a name ahead of a box or a street line: the marker and name go to `attention` |
| `compass-street.jsonl` | `cn-` | A spelled-out compass word and a suffix (`44 WEST AVE 2B`) are the street's name and suffix; `KY` or `TR` and a number after a compass word are the road |
| `country.jsonl` | `co-` | A trailing `USA`, `US` or `UNITED STATES` on one line, on its own line, in line 2 or in the city or state field (`country_ignored`); `US` as a highway prefix is not a country |
| `county.jsonl` | `cy-` | `CR` after a name is `CIRCLE` in every state; `CTY RD` and `CTY HWY` before a route are `COUNTY ROAD` and `COUNTY HIGHWAY` outside Florida too |
| `county-data.jsonl` | `cty-street-`, `cty-full-`, `cty-placeholder-`, `cty-highway-` | Shapes seen in Florida county property listings, hand-labeled: house number letters, units with and without designators, highways, placeholders (`UNKNOWN`, `NO SITUS`) |
| `county-data-golden.jsonl` | `cty-golden-` | One case per distinct shape in raw lines from eight Florida county listings; inputs only were taken, the labels are by hand |
| `default-state.jsonl` | `ds-` | Cases with `default_state`: a comma-less city found in the hinted state, the state's data readings, and the input's own state or a known ZIP winning over the hint |
| `dept.jsonl` | `dp-` | A department name on line 2 or after a comma is the attention line; `DEPT 4` and streets named `FIRE DEPT RD` are unchanged |
| `digit-letter-unit.jsonl` | `dl-` | A digit-letter after a name with no suffix (`60 LARKMOOR 1A`) is the unit, with or without a postdirectional |
| `fields-state.jsonl` | `ff-` | A reading only a state's data has (Florida `SR 60`) applies to pre-split fields as to one line |
| `fl-state.jsonl` | `fl-` | Florida state data and the national place list on Florida input: a city with no comma, cut-off cities completed, the place from the ZIP, `zip_city_mismatch`, `CR` and `SR` |
| `glue.jsonl` | `gl-` | A word before a trailing `CT`, `WY`, `KY` or `MT` stays one word (`PINEBRIAR CT`), in pre-split fields and on one line |
| `glued-floor.jsonl` | `gf-` | A floor written as a plain number and the floor word |
| `glued-number-letter.jsonl` | `gnl-` | A letter stuck to the house number (`glued_number_letter`) |
| `hash-before-designator.jsonl` | `hu-` | A `#` right before a unit designator and its value marks that unit (`# APT-4`); `#4` and `APT #4` keep their reading |
| `hyphen.jsonl` | `hn-` | The Queens house number with one trailing letter (`12-34A`); no letter or two letters stay as they were |
| `hyphen-second-number.jsonl` | `hp-` | A spaced hyphen between the house number and a second number is dropped; New York, Massachusetts, Hawaii and Canada are left as before |
| `intersections.jsonl` | `is-` | Two streets joined by `&`, `AND`, `@` or `AT`: first street as components, second in `unparsed`, `intersection_detected`, no key; look-alikes (`AT&T WAY`) must not warn |
| `keys.jsonl` | `key-` | Pin the emitters: exact key and slug strings, written from `docs/key-format.md` |
| `last-line-in-line1.jsonl` | `ll-` | On pre-split fields, line 1 ending with the state field and a ZIP is read as written |
| `letter-before-hyphen.jsonl` | `lh-` | A letter before the hyphen (`53A-53 HOLLIS AVE`) is one house number, kept as written; a range with a letter is `multiple_addresses` |
| `level-words.jsonl` | `lv-` | `GROUND`, `MEZZANINE`, `GARAGE`, `LL`, `LOBBY LEVEL` as units; `CAMP GROUND RD` and `LL BEAN RD` keep their reading |
| `line2-attention.jsonl` | `an-` | Words only on line 2 under a street are the attention line when they look like a firm or a person; a name after a unit, a credential, `D/B/A`; the rest stay unparsed |
| `lonedir.jsonl` | `ld-` | A lone directional on line 2 after a line 1 that ends in its suffix is the unit, not the postdirectional |
| `loop.jsonl` | `lp-` | `LOOP` after a street name, then a number, is the suffix and a bare unit |
| `lost-fraction.jsonl` | `lf-` | A fraction written without its slash (`31 1 2 ELM PLACE`) after the house number or in a whole-number street name |
| `mail-names.jsonl` | `mn-` | Queens mail names (`BRIARWOOD`, `JAMAICA ESTATES`) found in the place list are the city, not part of the street |
| `name-after-box.jsonl` | `nm-` | Words only on line 2 under a PO Box line with no street are the attention line |
| `name-before-number.jsonl` | `nbn-` | Words ahead of the house number: an initial is part of the name, `C O` with a space is the care-of marker |
| `name-lines.jsonl` | `nl-` | Name lines with commas and two leading units |
| `national-data.jsonl` | `nat-` | Fixes found by comparing the parser with a national address database; the addresses are invented (the database is not redistributable) |
| `no-north.jsonl` | `nn-` | `NO` right after the house number and before a plain word is north; `NO NAME RD` and a bare number keep `NO` |
| `non-us-address.jsonl` | `fa-` | A foreign address whose line 2 or last segment ends in a country name gets `non_us_address` |
| `nostreet.jsonl` | `ns-` | Street lines with no street: a lone number, a PO Box word with no number, only a country |
| `null-words.jsonl` | `nw-` | A bracketed `<NULL>`, and `NaN` or `undefined` as a city, state or ZIP field |
| `number-before-unit.jsonl` | `nbu-` | A bare number before a designated unit on line 2 (`5 APT 12`) is the first unit with no designator |
| `number-letter.jsonl` | `nlt-` | A letter after the house number |
| `number-pair.jsonl` | `np-` | Two numbers before a street: the house number in New York and Hawaii, a building and a unit elsewhere |
| `number-word.jsonl` | `nu-` | `NO.9` and `NUM.12` read as the value; the number word after `PO BOX` is dropped |
| `paren-group.jsonl` | `pg-` | A parenthesized group at the end of a line: a unit, floor or box is read as that unit, any other group lands in `unparsed`; an unclosed `(` is dropped |
| `placeholder-city.jsonl` | `pcity-` | A placeholder in the city field (`Not stated`, `UNKNOWN`) is no city; a real city is kept |
| `placeholder-phrases.jsonl` | `ph-` | Registry stand-ins for a missing street (`NO STREET ADDRESS`): a placeholder, no key |
| `places-us.jsonl` | `pl-` | The place behaviors in states with no curated state data, a county written as the city, a municipality prefix (`VILLAGE OF ...`) |
| `po-no-box.jsonl` | `pn-` | `PO`, `P O` and `P.O.` with a number that ends the line are a PO Box; `PO RD 5` keeps its reading |
| `pobox.jsonl` | `pb-` | The eleven misspellings of PO BOX read as a box; streets named `POX`, `P`, `POP` are unchanged |
| `pobox-zip.jsonl` | `pz-` | A number after `PO BOX` or a designator is the box or unit number even when it equals the ZIP5 |
| `pub28.jsonl` | `p28-` | Examples from USPS Publication 28 (sections in `docs/usps-pub28-notes.md`): highways, PO Box, rural route, highway contract route, general delivery, military; inputs use the spellings Pub 28 says to change |
| `queens.jsonl` | `qk-` | In Queens, NY the key drops the hyphen of `37-12`, so a building written both ways keys the same; other places keep it |
| `recipient.jsonl` | `rc-` | Recipient text ahead of the address on line 1 goes to `attention`; `COUNTY ROAD 12` and `C/O` right before the address are unchanged |
| `regressions.jsonl` | `rg-`, `us-roundtrip-001` | Parsing bugs found over time, from Florida data and other tests; each note says what went wrong |
| `repeated.jsonl` | `rt-` | Repeated text and its warning |
| `repeated-tail.jsonl` | `rp-` | A street, a unit or both written twice, the copy ending line 1, is read once with `repeated_text` |
| `repeated-unit.jsonl` | `ru-` | The same unit on both lines, or twice on line 2, is kept once; two different units stay two |
| `reso.jsonl` | `reso-` | Pin the emitters: RESO field values, written from `docs/reso-mapping.md` |
| `road-letter.jsonl` | `rl-` | A letter after `ROAD` on one line |
| `road-number.jsonl` | `rn-`, `cd-` | A number after a road word is the road's in a closed list of states and words (`PRIVATE ROAD 1234` in TX), a unit elsewhere; both spellings share a key |
| `route-typos.jsonl` | `rty-` | Typos of rural route and highway contract prefixes (`RUR RTE 3 BOX 84`, `HRC 5 BOX 12M`) |
| `rrbox.jsonl` | `rb-` | A lone letter after a numeric rural route or contract route box number is part of the box (`45A`) |
| `second-line.jsonl` | `sl-` | A second address line used or dropped without a component of its own is reported (`second_line_skipped`, `second_line_in_street`, `second_line_building`); a unit, a street, a dual address and an attention line get no warning |
| `so-for-south.jsonl` | `so-` | `SO` as the last word of the street, after a suffix or a grid number, is the postdirectional south; `SO CAROLINA AVE` keeps it in the name |
| `spelled.jsonl` | `sp-` | Spelled-out numbers: a house number word (`ONE COMMERCE PLAZA`), a unit number word (`SUITE TWO`), a spelled ordinal floor; `ONE MILE RD` is unchanged |
| `spelled-number.jsonl` | `sn-` | A singular suffix word starts the name, so `ONE` is the house number (`ONE PARK AVE`) |
| `stray-designator.jsonl` | `sdb-` | A unit designator right after the house number, with a bare unit value on line 2, is that unit's type |
| `tag.jsonl` | `tg-` | Cases with `address_type`, `tag` and `tag_repeated`: one per address shape, a repeated label, a one-letter number prefix written apart from the number |
| `text-after-suffix.jsonl` | `ta-` | Plain words after the suffix are the attention line |
| `unit-before-street.jsonl` | `ubs-` | A unit between the house number and the street (`123 SUITE A OAK ST`) |
| `unit-road-word.jsonl` | `rw-` | A bare `#` followed by the street's own suffix or a direction is not a unit |
| `unit-separator.jsonl` | `sep-` | A dash or slash between a suffix and a unit, and a spaced hyphen then a bare value, are separators; a slash before a PO Box gives street and box |
| `unit-spaced-hyphen.jsonl` | `uh-` | A spaced hyphen between a designator and its value is dropped |
| `unit-then-box.jsonl` | `ub-` | A bare `BOX` and its number after a unit (`STE 105 BOX 121`) is the PO Box with `dual_address` |
| `units.jsonl` | `un-` | Units left in the street name: two numbers after a designator, `BOX`, `NO`, `NUM`, `LOC` after a street, a cut-off designator; a street named `FLOOR` or `UNIT` is unchanged |
| `unlisted-unit-words.jsonl` | `uw-` | `CND`, `COND` and `CONDO` on line 2 are a plain unit; on the street line they stay in the name |
| `us-highway-spelled.jsonl` | `ush-` | `UNITED STATES HIGHWAY 27` and `U S HIGHWAY 27` read as the US highway, like `US HWY 27` |
| `warnings.jsonl` | `wn-` | A letter after the number read into the street name warns that it may be the number's suffix or an initial |
| `zip-repair.jsonl` | `zr-` | A nearly right ZIP is repaired |

Notes on single files:

- `<st>-state.jsonl`: every folder under `crates/doorplate/data/states/` needs one, with cases from that state; a test fails when one is missing. `fl-013` and `fl-019` are Georgia and Colorado inputs that show a state with no curated data. The place cases need the default feature `places-us`.
- `pub28.jsonl` takes its inputs from the highway table (section 237), Appendix F, and the PO Box, rural route, contract route, general delivery and military sections; `docs/usps-pub28-notes.md` has the page for each. House numbers are present only where Pub 28's example has one.
