# RESO field mapping (Data Dictionary 2.0)

Implemented by `crates/doorplate/src/emit/reso.rs` (`ParsedAddress::to_reso`). In
Python it is `parse(s).to_reso()` (a dict of the non-empty fields), and the
`reso` object in the JSON of `doorplate parse`.

This maps a parse to RESO field names and shapes. It does not validate
deliverability, and it does not check values against any server's lookups.

## Source and version

- **RESO Data Dictionary 2.0**, Property resource, group *Location / Address*:
  `https://dd.reso.org/DD2.0/Property/<FieldName>/`. The pages were first read on
  2026-10-15 (the site footer read "Generated October 12, 2026") and the field table
  below was checked against them again on 2026-10-20 (footer "Generated October 19,
  2026"): every type, maximum length, lookup status and field status is unchanged.
- Lookups: `https://dd.reso.org/DD2.0/lookups/StreetDirection/`,
  `.../StreetSuffix/`, `.../StateOrProvince/`, `.../Country/`.
- Release overview: `https://dd.reso.org/DD2.0/about/release-guide/`.
- The Data Dictionary calls its maximum lengths "Suggested". The emitter never
  cuts a value; `ResoAddress::length_overruns()` reports the ones that exceed.

The emitter targets the fixed set in the table below. A newer Data Dictionary
(2.1 is still listed on `dd.reso.org` as a draft, "in development", on 2026-10-20) needs this file rechecked, and a change of target is a
change to this document and to `reso.rs` together.

## Field table

Types, lengths and lookup status are as the Data Dictionary pages give them.

| DD field | DD type | Max len | Lookup | Emitted from | Notes |
|---|---|---|---|---|---|
| `StreetNumber` | String | 25 | | `street_number` | DD: may hold non-numeric characters and modifiers such as `1/2` or `B`; must not hold prefixes, direction or suffix. Same cleaning as the USPS line (uppercase; punctuation dropped except `-`, `/`, and `.` between digits). |
| `StreetNumberNumeric` | Number | 10 | | leading digits of `street_number` | DD: "the integer portion of the street number". `123-125`, `12A` and `123 1/2` give 123, 12, 123. Empty when the number starts with no digit or has more than 10 digits. A derived value. |
| `StreetDirPrefix` | String List, Single | 15 | `StreetDirection`, open with enumerations | `street_dir_prefix` | Lookup values are `E N NE NW S SE SW W`, the Pub 28 abbreviations. |
| `StreetName` | String | 50 | | `street_name`, or a folded form (below) | |
| `StreetSuffix` | String List, Single | 25 | `StreetSuffix`, open, **no standard values** | `street_suffix` abbreviation | See choice 1. |
| `StreetDirSuffix` | String List, Single | 15 | `StreetDirection` | `street_dir_suffix` | As the prefix. |
| `UnitNumber` | String | 25 | | `unit_type` + `unit_number`, then the second unit | DD definition: the unit "that should appear following the street suffix or, if it exists, the street suffix direction (e.g., Apt G, #55)". The field holds the designator with the number. See choice 3. |
| `City` | String List, Single | 50 | `City`, open | `city`, or the military post office | |
| `StateOrProvince` | String List, Single | 2 | `StateOrProvince`, open with enumerations | `state` code | See choice 4. |
| `PostalCode` | String | 10 | | `zip5` | |
| `PostalCodePlus4` | String | 4 | | `zip4` | DD: "the last four digits of a nine-digit U.S. ZIP Code". |
| `UnparsedAddress` | String | 255 | | the USPS line 1, city, state and ZIP | DD: the full civic location as one entity, optionally with City, StateOrProvince, PostalCode and Country. See choice 5. |

## Shapes with no field of their own

The Data Dictionary has no field for these, so they are folded into
`StreetName`, with `StreetNumber` empty (except highways):

| Shape | `StreetName` | Other fields |
|---|---|---|
| Highway street (`100 KENTUCKY STATE HIGHWAY 625`) | state code, standard prefix, route: `KY STATE HIGHWAY 625` | `StreetNumber` kept; suffix and directionals as parsed |
| PO Box | `PO BOX 12` | |
| Rural route / highway contract | `RR 2 BOX 152`, `HC 68 BOX 23A` | |
| Military or State Dept. box | `PSC 1650 BOX 10` | |
| General delivery | `GENERAL DELIVERY` | |
| APO / FPO / DPO | not applicable | `City` = `APO`, `FPO` or `DPO`; `StateOrProvince` = `AA`, `AE` or `AP` |
| Second unit designator | not applicable | appended to `UnitNumber`: `APT 4 LOT 18` |
| Dual address: street and PO Box (Pub 28 section 215) | the street's name; the box is not emitted | street fields and units from the street; `UnparsedAddress` uses the street line (choice 8) |
| Attention or care-of line (`ATTN ...`, `C/O ...`, section 214) | not applicable | not emitted |
| Building name (`EAST TOWER`) | not applicable | not emitted |

The text is the same as the USPS emitter's delivery line (Pub 28 sections
237, 238.1, 239, 241 to 261), so the two outputs agree. The PO Box and route
box numbers could instead go in `StreetAdditionalInfo` (choice 2).

## Fields not emitted

| DD field | Why |
|---|---|
| `Country` | The parser reads no country, so emitting `US` would be an assumption of the library's scope, not a parse result. Choice 6. |
| `PostalCity` | DD: the official USPS city. That needs USPS data; this library does not validate or look up. |
| `StreetSuffixModifier` | DD: a suffix not in the pick list, or one that extends or prefixes the suffix. The parser either maps a suffix to Pub 28 (with `non_standard_abbreviation`) or leaves it unparsed. |
| `StreetAdditionalInfo` | DD: "information other than a prefix or suffix for the street portion of a postal address". Nothing in the parse maps to it unambiguously. Choice 2. |
| `CityRegion`, `StateRegion`, `CountryRegion` | Area fields (group Location / Area), not address parts. |

## Choices

The Data Dictionary pages give definitions, types and lookups but not
conventions, so these are choices, not facts from the Data Dictionary.

1. **`StreetSuffix` form.** The Pub 28 abbreviation (`ST`), as `to_usps()`. The lookup is open and defines no values.
2. **PO Box, route and box numbers** stay in `StreetName`; `StreetAdditionalInfo` is not used.
3. **`#` units** keep the designator (`#55`), as the Data Dictionary's example does. The USPS line writes `# 55`, by design.
4. **State codes outside the lookup** (`PR`, `GU`, `AA`, …) pass through with no warning: the lookup is open with enumerations, but a server that enforces them would reject these.
5. **`UnparsedAddress`** is `LINE1, CITY, ST ZIP` (USPS line 1, ZIP+4 with a hyphen). No country is added.
6. **`Country`** is left empty. No option sets it.
7. **Text not placed** (`Diagnostics::unparsed`) is not emitted; it stays in the diagnostics.
8. **Dual addresses** give the street in every field, because RESO address fields describe the property. The PO Box is left out, so the USPS output and the RESO output differ for these records (the key uses the street too).

## Verification status

Checked against the Data Dictionary pages on 2026-10-20: field names, types, lengths, lookup and field statuses. Not checked: the lookup value lists, a particular RESO server, or the Lookup Resource's `LookupKey` form. Tests: `emit/reso.rs` and `tests/corpus/reso.jsonl` (written from this table, not copied from emitter output).
