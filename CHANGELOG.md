# Changelog

All notable changes are listed here, newest first. The project follows
[Semantic Versioning](https://semver.org/). The canonical key format has its own
version (currently `k3`), tracked separately in [`docs/key-format.md`](docs/key-format.md): a
change to what an input produces needs a new key version.

## [Unreleased]

### Added

- **`repeated_text` warning** (#236, `version:O`, **no key change**): raised when text that appears twice in the input is read once and the copy dropped: a line written twice (`812 ASHGROVE ST 812 ASHGROVE ST`, `PO BOX 7 PO BOX 7`), a cut-off copy of the address ahead of it, or the city, state or ZIP written again at the end of line 1. Not raised with `second_line_skipped`. Added to 38,422 of 36,920,703 rows of seven large sources (0.10%), no key changes. A repeat that is not dropped (the street name keeps the city, ZIP+4 in the ZIP field) has no warning yet and is the held `k4` rule.

### Changed

- **Words only on line 2 under a PO Box are the attention line** (#303, **no key change**): `PO BOX 1234` / `JANE ROE` and `PO BOX 12` / `ACME CORP` give `attention`; before they were `unparsed_remainder`. A street suffix word (`ELDER RD`) or a digit keeps the old result. 343 rows lose `unparsed_remainder` in 36,920,000 rows of seven sources (NC voter 168, NY corporations 120, IRS 55); no key changes.

### Changed (key-affecting, held for the `k4`)

- **`NO.9` and `NUM.9` read as the value, the number word counts with a second unit, and `PO BOX NO 12` is box 12** (#293, decided 2026-10-30: `NO.` before a unit value is a unit designator, which it already was after a suffix; no unit type is emitted, Pub 28 uses `#` for an unknown one): `1234 OAK AVE NO.9` is unit `9` (was `NO9`, while `APT.9` always worked); `1234 OAK AVE NO. 9` / `REAR` and `... NO 9 APT 4` read both units (the street name kept `AVE NO 9`); `PO BOX NO 12` and `PO BOX NO.12` are box `12` (was a street name, and box `NO12`). With no street suffix `NO` stays in the street name (north, numbered roads, a house-number prefix, the Spanish *número*). The marker branch is shared with `BOX` and `LOC`, which also now count with a second unit. 302 rows change in 36,920,703 rows of seven sources (NY corporations 163, carrier census 54, IRS 34, NC voter 31, amateur radio 19, NAD 1; Netsyms 0): 197 property-level keys and 298 unit-level keys.

- **A `#` right before a unit designator marks that unit** (#340): `410 ELM ST # APT-4`, `#APT-18` and `# APT 4` give the unit `APT` and its value; before, the `#` was read as a first unit with no number (`missing_unit_number`) and the real unit became the second unit. Only a `#` directly before a designator that has its value; `#4`, `APT #4`, `#APT4`, `PO BOX #12` and `APT 4 # B` are unchanged. 7,192 rows change in 36,920,703 rows of seven sources (NC voter 6,984, carrier census 123, NY corporations 82, amateur radio 3; IRS, Netsyms and NAD 0): 7,185 unit-level keys, and **52 property-level keys** (a street that had swallowed its suffix and unit into the name: NC voter 44, NY corporations 4, carrier census 3, amateur radio 1); 7,189 rows lose `missing_unit_number`.

- **`PO BOX` with no number at the end of a street line is left unparsed** (#301): `90 NE 5 AVE PO BOX` is the street `5 AVE` with `PO BOX` unparsed (`unparsed_remainder`); before, the street name was `5 AVE PO BOX` with no warning. 266 keys change in 36,920,000 rows of seven sources (carrier census 204, IRS 36, NY corporations 12, amateur radio 9, NC voter 5; NAD and Netsyms 0).

- **A bare `BOX` after a unit is the PO Box** (#300): `4920 W RIDGE ROAD STE 105 BOX 121` is street, unit `STE 105` and PO Box `121` with `dual_address`; before, the street name was `RIDGE ROAD STE 105 BOX 121` (`possibly_truncated`), or the box was lost. 356 keys change in 36,920,000 rows of seven sources (carrier census 250, IRS 46, amateur radio 33, NY corporations 22, NC voter 5; NAD and Netsyms 0).

- **`BOX` and a number after a street name with no suffix is a unit** (#299): `640 PINEWOOD BOX 18` and `6 ELMGROVE BOX 12` are the street and unit `18`/`12`; before, the street was `PINEWOOD BOX 18` with no warning (with a suffix it already worked, #128). Only with a house number and a digit value; `DUKE BOX 90123`, `RR1 BOX 5` and `100 BOX CANYON RD` are unchanged. 2,755 keys change in 36,920,000 rows of seven sources (carrier census 1,429, IRS 521, amateur radio 478, NY corporations 215, NC voter 112; NAD and Netsyms 0).

- **A PO Box or unit number equal to the ZIP is kept** (#260): `12 QUINCEWOOD AVE` / `PO BOX 12345` with ZIP `12345` is street plus box `12345` with `dual_address`; before, the number was dropped as a copy of the ZIP and `PO BOX` was left unplaced (`unparsed_remainder`), or in the street name. `APT 12345` likewise. Filed as warnings only; the measurement found keys change: 491 in 36,920,000 rows of seven sources (amateur radio 367, carrier census 100, NY corporations 16, NC voter 8; Netsyms, NAD, IRS 0), 106 of them rows that had no key.

- **A compass word and a street suffix is the street's name** (#325): `44 WEST AVE 2B`, `44 EAST ST 2` and `44 SOUTH ST 1R` are the street `WEST`, `EAST`, `SOUTH` with the suffix and the unit; before, the direction was the prefix and the suffix and unit made the name (`AVE 2B`). With the unit on line 2 (`44 WEST AVE` / `2B`) the unit is placed instead of left in `unparsed_remainder`. Only the spelled-out words and a value with a digit; `44 W MAPLE AVE 2B`, `100 N ST NW` and `147 SE AVENUE A` are unchanged. 1,066 keys change in 36,920,000 rows of seven sources (carrier census 609, amateur radio 190, NY corporations 104, IRS 86, NAD 77, NC voter and Netsyms 0).

- **A letter `A` to `D` after the house number is the number's suffix** (#270, decided 2026-10-29 from the NAD and NC voter labels): `46 A LINDEN AVE` is `46A LINDEN AVE` (the warning `ambiguous_number_letter` stays). Not before a single letter (an initial), a street suffix, a direction or a unit word; `E` to `Z` keep the street name. The number and its letter are one token, so `428 B SOUTH MAIN ST` is now `428B` in the output and the key too. 38,775 keys change in seven large sources (30,778 the new reading, 7,997 the glued spelling only) and 595 in the Texas file. Known cost: a street named for a person with an initial (`820 A PHILIP RANDOLPH BLVD`) reads `820A`.

- **A floor written as a number and the floor word is a unit** (#241, one part of it): `15 CEDAR STREET 3FL`, `18 ELM ST, 2FL`, `34 ELM ST 2FLOOR`, `61 OAK AVE 1FLR`, `18 ELM ST 2 FL` read the unit `FL` with its number; before, the number stayed in the street name or the floor had none (`missing_unit_number`). 8,717 keys change in seven large sources and 3 in the Texas file, almost all of them rows that had `missing_unit_number`. The other unit forms in #241 are not part of this change.

- **A nearly right ZIP is repaired** (#275, new warning `zip_repaired`): `NEWARK NJ 7102 -1234`, `NJ 7102` (the leading zero is restored in CT, MA, ME, NH, NJ, PR, RI, VT and VI) and `DALLAS TX 75001-5` (an extension under four digits is dropped) now place the city, state and ZIP; before, the whole last line stayed unplaced and the key had no state or ZIP. 633 of 211,009 Texas licensing rows and 308 of 36,920,703 rows of seven large sources change key, all from the `k3n:` form to a full key.

- **A name with commas ahead of the street is the attention line** (#268): `ACME HOLDINGS, INC.` / `318 EAST 41ST ST.` and `DANA QUILL, PRES.` / `318 EAST 41ST ST.` read the street from line 2 (the key was the organization name, with `missing_street_number`), and a name over a PO Box (`ACME, INC.` / `P.O. BOX 12`) reads the box. Up to three plain comma segments before the street or box.
- **Two units ahead of the street on line 1 are both units** (#276): `STE 410 RM 7`, `STE 330 AND STE 350`, `STE 95 #22` over `40 ELM ST`.
  `main` reports `0.5.0-dev` from here (the first held `k4` rule), so key dumps made between releases name their build (`key_diff.py` records the commit as well).
  Measured against the build before the change, row by row, on 36,920,000 rows of seven sources: 12,515 keys change, all of them rows that had `missing_street_number`; Netsyms and NAD 0. Stored `k3:` keys stay valid until the `k4` is cut.

## [0.4.1] - 2026-10-28

Tooling, documentation and extensibility, with **no key change** (the key format stays `k3`) and no parse-rule change: a custom
layer changes parsing only when one is loaded. Checked row by row against the frozen 0.4.0 keys on 36,920,000 rows of seven
sources: 0 keys and 0 warnings differ. Stored `k3:` keys stay valid.

### Added

- **Review tool: a stale parser is flagged** (#246, tooling only): `tools/review/server.py` warns at start-up and shows a banner when the WebAssembly parser build is older than the source it is built from (`--strict` refuses to start), and the page header shows the parser's library version and key prefix. The second review had used a build five days behind without a sign.

- **The custom layer, first part** (#3, additive, **no key change without a layer**): `CustomLayer::from_sources` (cargo feature
  `custom-layer`; the core takes the text of the files) loads your own spellings and word lists on top of the shipped tables:
  extra spellings of suffixes, unit designators, directionals, states, special words and highway prefixes; additions to the
  tagger's word lists (building, area, city head, non-recipient, numbered street, placeholder, country and place-prefix words); and
  state-scoped readings of a spelling. It is add-only: a spelling the shipped tables already have is a load error that names the file and
  entry, and every problem is listed. `ParseOptions::custom_layer` puts a layer on a `Parser`, and every parse reports it in
  `Diagnostics::custom_layer` (name, version, content fingerprint). A layer can change a key, so stored keys need a fixed layer
  ([`docs/key-format.md`](docs/key-format.md)). Parsing without a layer is unchanged: identical keys, USPS lines and warnings on
  100,000 sampled rows, and the same speed (about 108,000 parses per second on both). The layer also takes places (with their misspellings and county) and ZIPs (`places.tsv`, `zips.tsv`; a ZIP names its main and shared
  places, so the zip-city check and the state-from-ZIP rule use it). Parsing without a layer is unchanged on 100,000 sampled rows (same keys,
  USPS lines, last lines and warnings; the same speed). The command line (`--custom-layer DIR` on `parse`, `parse-file` and `corpus test`, `doorplate layer check DIR`, and `provenance.custom_layer` in the JSON) and Python (`load_layer`, `CustomLayer`, `custom_layer=` on `Parser` and every call and helper, `ParsedAddress.custom_layer`, `LayerError`) read a layer from a folder. Size: the `toml` parser and the loader add about 0.55 MB to the CLI binary (5.83 to 6.38 MB, unstripped) and about 0.24 MB to the Linux wheel (1.89 to 2.13 MB); the default Rust library build is unchanged (the feature is off by default).

- **A documentation site** (#107, phase 1, docs only): `mkdocs.yml`, `.readthedocs.yaml` and pinned `docs/requirements.txt` build the pages of `docs/` with MkDocs and the Material theme for Read the Docs; links from a page to a repository file are rewritten to GitHub in the site only (`tools/docs/links.py`), and a CI job builds the site with `--strict`.

- **Review tool: smaller helpers** (#222, tooling only): `]` and `[` move words of line 1 to the care-of line with a live re-parse; a correction left unchanged asks whether the parse was right (and the server refuses it unless confirmed); `l` opens span labeling, a `labeled` verdict that marks the parts of the one-line string; the page's helper functions are `tools/review/helpers.js`, tested under Node.

- **The Python and command-line reference** (#107, phase 2, docs only): `docs/python-api.md` is generated with `mkdocstrings` from the type stubs (`__init__.pyi` now has a docstring on every public function, class, method and property, taken from the Rust doc comments; the `Military` kinds were corrected to CPR, OPC, PSC, UPR and UNIT), so it describes `main` and needs no build of the extension; `docs/cli.md` lists the commands, options and exit codes. `pytest tools/docs` fails when a public name or a CLI option is missing from the pages. docs.rs builds the Rust API with all features.

- **Review tool v2: a comparison mode** (#132, tooling only): `tools/review/compare_sample.py` samples a real source, parses each row
  with doorplate and usaddress, and queues the disagreements (silent ones first, then give-ups, then a control) for a person to judge
  as doorplate right, usaddress right, both right or both wrong; the page shows both parses side by side, and `export.py --table`
  counts who was right by label pair. The v1 queue skips repeated inputs and has `--group coarse`.

- **Quieter harness scorers** (#112, tooling only): `label_score.py` treats a label's `EXT` post-modifier as the suffix, accepts a
  suffix inside the label's name when the type is empty, and counts a labeled unit that is not in the parsed text apart (NC pair
  score: suffix differences 3,000 to 1,292, name 2.33% to 2.05%, unit 0.58% to 0.39%); `--examples FILE` writes the
  disagreements (ids and values) to a local file under `local-data/`; `shapes_report.py` lists the input shapes behind `street`
  mismatches and counts `missing_street_number` rows that start with a number word (`ONE PENN PLAZA`).

- **`doorplate.compat`, a usaddress-shaped module** (#36, Python only, additive, no key or parse change): `import doorplate.compat as usaddress` gives `parse(s)`, `tag(s, tag_mapping=None)` and `RepeatedLabelError`, so a script that calls only those runs with one import changed. A token the parser did not place has the label `None`; a label in two runs is joined, and `tag(s, strict=True)` raises `RepeatedLabelError` (usaddress's attributes) the way usaddress does; blank input gives `[]` and `({}, "Ambiguous")`. Label compatibility, not identical output: [`docs/usaddress-compat.md`](docs/usaddress-compat.md) lists the differences and the decisions. Example: `examples/usaddress_migration.py`.

- **Faster `parse_column` and DuckDB columns** (#24, no key or parse change): `doorplate.pandas.parse_column`, `doorplate.polars.parse_column` and the one-line DuckDB functions build their columns in Rust (one list of strings per column, a thread per column, no Python object per row) instead of reading attributes off `parse_many`'s results. Values are identical (a test compares every column on the whole golden corpus). 100,000 addresses, 15 default columns: pandas 1.03 s to 0.83 s and Polars 0.86 s to 0.70 s on 4 CPUs (1.25x and 1.23x), DuckDB 0.79 s to 0.70 s; about 1.4x on 14 CPUs. No new dependency; a public Arrow result was not built ([`docs/benchmarks.md`](docs/benchmarks.md)). `parse_fields_many` is unchanged.

- **The custom layer, last part: the demo layer, the guide and the notebook section** (#3, documentation and examples only, no code change):
  `examples/layers/riverbend-demo` is a working layer for an invented county (two suffix spellings, a unit word, a directional, a
  trailing word, two places with misspellings and a shared ZIP), `examples/layers/template` is one to copy (one entry per table,
  options explained in comments), and [`docs/custom-layers.md`](docs/custom-layers.md) is now the customization guide: how to
  find the spellings worth adding, which file each symptom belongs in, and a ready prompt for an LLM that drafts a layer from a
  list of misparsed lines. The quickstart notebook has a "Your own spellings and places" section. Tests load both layers and keep
  the prompt in step with the loader.

- **`doorplate anonymize`, `doorplate::Anonymizer` and `doorplate.Anonymizer`** (#105, additive, no key change): rewrites
  address-like text so it can be shared, even text that does not parse. Digit runs become other digits of the same length,
  other words become invented words of the same length and case, and suffixes, directionals, unit designators, states, the
  city and the first three ZIP digits stay. The CLI takes stdin lines or named CSV columns (`--column`, `-o`, `--seed`),
  Python has `Anonymizer(seed)`, `anonymize_many` and `anonymize`, and each value is checked by parsing before and after
  (`faithful`). **Obfuscation that keeps the shape, not anonymity**: lexicon words and the city stay, so read the output
  before you share it. On 100,000 sampled street lines from each of nine local sources the parser reads 96.7% to 99.9%
  the same after the change (on line 2 of the eight sources that have one, 94.2% to 100%), and no digit run stays as it was except the single-digit fractions (`1/2`), which stay by design.

## [0.4.0] - 2026-10-25

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
  digits and an optional letter (`37-12`, `37-12A`) keys without the hyphen, so both forms give `k3:S|3712||82ND|ST||NY|11354`.
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
