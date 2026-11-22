# Puerto Rico addressing: what Pub 28 says and what the parser does

Research for the Puerto Rico epic (#332, reading task #92). It reads the Puerto Rico and Spanish-language parts of USPS Publication 28, states each rule in our own words with its section, and sets it against what the parser does today. It changes no parser behavior. Rules that change a key are marked **key**; they wait for a key version (a minor release, 0.8 or later) as the standing decision says.

Read: section 29 (291 to 295), Appendix D5, Appendix H, Appendix I (I1 to I5). The examples in these sections are images; they were read, and the addresses below are invented analogs of the same shapes. Not read here: Appendix J (U.S. Virgin Islands), which is outside the epic. Pub 28 was last changed in October 2024 (see `tools/pub28/verify.py`); it has not changed these pages.

The parser results are from `main` at `52d6aa2` (0.6.2), `parse` on one-line input unless a field form is named. "Warnings" lists the codes the parse returned.

## What Pub 28 says

| # | Rule (our words) | Source |
|---|---|---|
| R1 | Puerto Rico uses several formats. Residential: the street line is `NUMBER PREFIX-WORD STREET` (`CALLE`, `AVE`, `CARR`, `PASEO`, `CAMINO`, `VIA` and similar come **before** the street name and stay part of it); the urbanization (`URB NAME`) is a second line. A three-line form omits the urbanization. | 291, I21, I51.1 |
| R2 | The urbanization is the only element that tells apart identical street names and number ranges inside one ZIP. It is a required part of the address, so Pub 28 treats the list of urbanization names as a ZIP check. `URB` goes before the name. The two layouts shown put the `URB` line either above the street line (§292) or after it (I51 components figure). | 292, I21.1, I51.4 |
| R3 | Where an area has no street names or repeating numbers, the urbanization name stands in for the street name and the house number goes ahead of it (`1234 URB LOS OLMOS`). Public housing (`RES`, residencial) with no streets: the apartment number is the primary number and the project name is the street name. | I21.3 |
| R4 | Some urbanization names stand alone without `URB` (`EXT`, `RES`, `REPTO`, `BO`, `BDA`, `JARD`, `ALT(S)`, `SECT`, `TERR`, `MANS`, `IND`, `EST`, `PARQ`, `VISTA(S)`, `VILLA(S)` and about 20 more, I51.4 list). `URB EXT VISTA BELLA` is the wrong form of `EXT VISTA BELLA`. | I51.4 |
| R5 | Apartment buildings and condominiums with a street address: `NUMBER STREET APT N`. A condominium on no named street, or with no building number: the condominium name takes the street position, and **the number 1 is used when there is no building number**. When several towers share a name, the building number is the primary number (`1 COND VERDE APT 1120`; `3 VISTA SUITES APT 104` for tower III). Another form puts the condominium name on its own line with `TORRE 2 APT 905` or `EDIF 1 APT 104` below it. | 291 (exceptions), I22 |
| R6 | The house number is always written **before** the street prefix: `A17 CALLE 1`, never `CALLE 1 A17`. A lettered number has no hyphen (`C19 CALLE 125`, not `C-19`). A block and house number are joined by a hyphen (`199-31 CALLE 19`); the words `BLOQUE`, `NUMERO`, `CASA`, `LOTE` and `#` are dropped. A numbered street always carries its prefix (`CALLE 191`) so the street number is not read as a house number. | I51.2, I51.3 |
| R7 | `CALLE` is not replaced by `ST`: "such substitutions render the address undeliverable." The AMS database has no prefix field, so the Spanish prefix lives in the street name. Appendix H lists compressed forms only for use when space is short (`CALLE` to `CLL`, `CAMINO` to `CAM`, `CAMINITO` to `CMT`, `CERRADA` to `CER`, `CIRCULO` to `CIR`, `ENTRADA` to `ENT`, `PASEO` to `PSO`, `PLACITA` to `PLA`, `RANCHO` to `RCH`, `VEREDA` to `VER`, `VISTA` to `VIS`; `AVENIDA` is `AVE`); the English translation is information only. | 291, H, I51.1 |
| R8 | Box and route words are English in the standard form: `APARTADO` becomes `PO BOX`; `RUTA RURAL n BUZON m` (also `RFD`, `BZN`) becomes `RR n BOX m`; `RUTA ESTRELLA n BUZON m` becomes `HC n BOX m`. No leading zero on the route. A letter in a box number loses its hyphen (`17-A` becomes `17A`). Sector or barrio names after a route and box are dropped: use one address style only. | 293, I51.5 to I51.7 |
| R9 | Spanish directionals (`NORTE`, `NORESTE`, `NOROESTE`, `SUR`, `SURESTE`, `SUROESTE`, `ESTE`, `OESTE`) are rare. The ZIP+4 file uses the English forms; `OESTE` is `W`, though 294 also shows `O`/`NO`/`SO` as the Spanish abbreviations. | 294, I4 |
| R10 | Abbreviations for the descriptive words: the lists in 293 and Appendix I3 differ in a few entries (see below). | 293, I3 |
| R11 | Last line: `SAN JUAN` is the only valid city for San Juan addresses; area names such as `RIO PIEDRAS`, `CONDADO`, `BARRIO OBRERO` are not valid last-line cities. | I51.8 |

Where 293 and I3 differ: `COOP` against `COO`; `SEC` against `SECT` (and I3 adds `SECC` for Sección); `ALT`, `ALTS`, `EST`, `INT` appear only in I3; `BLDG`, `BL`, `CAS`, `CORP`, `GEN DEL`, `HOSP`, `REPTO`, `VIL` appear only in 293. Neither list is a complete street word table.

What Pub 28 does **not** say: anything about `KM` (kilometer markers on `CARR` roads), lot codes beyond R6, or a street-first order. The street-first order (`CALLE LUNA 123`) is real input but Pub 28 names it as the incorrect form; the standardized output puts the number first.

## What the parser does today

| Shape (invented) | Parse | Pub 28 | Verdict |
|---|---|---|---|
| `1234 AVE ASHFORD APT 1A, SAN JUAN PR` | number 1234, street `AVE ASHFORD`, unit `APT 1A`, no warnings | R1, R5 | right |
| `150 CALLE A, SAN JUAN PR`, `125 CALLE MAIN` | number, street `CALLE ...` | R1, R7 | right; the prefix stays in the name |
| `12 CALLE LUNA ST` | suffix `ST` after `CALLE LUNA` | R7 | not changed to anything: the parser keeps what it sees |
| `A17 CALLE 1`, `199-31 CALLE 19` | number `A17` / `199-31` | R6 | right |
| `A-17 CALLE AMAPOLA` | no number, street `A-17 CALLE AMAPOLA`, `missing_street_number` | R6 (hyphen is the wrong form) | gap, **key** |
| `CALLE 19 BLQ 199 CASA 31` | no number, whole line is the street name, `missing_street_number` | R6 (`BLQ`, `CASA` words) | gap, **key** |
| `1234 URB LOS OLMOS, PONCE PR` | number 1234, street `URB LOS OLMOS` | R3 | right |
| `27 CALLE LUNA URB LAS PALMAS` | number 27, street `CALLE LUNA URB LAS PALMAS`, no warning | R2 (URB is not part of the street) | gap, **key** (#318) |
| `URB LAS FLORES, CALLE 3 B-12` (one line) | street `URB LAS FLORES`, `CALLE 3 B-12` unparsed, `missing_street_number`, `unparsed_remainder` | R2, R6 | gap, **key** (#318) |
| `URB LAS FLORES CALLE 3 B12` | no number, street `URB LAS FLORES CALLE 3 B12`, `missing_street_number` | R2, R6 | gap, **key** |
| `URB LAS FLORES 12 CALLE 3` | no number, street `URB LAS FLORES 12 CALLE 3`, `missing_street_number` | R2 | gap, **key** |
| `EXT VISTA BELLA 12 CALLE 4` | no number, street holds all of it, `missing_street_number` | R4 | gap, **key** |
| field form: line 1 `27 CALLE LUNA`, line 2 `URB LAS PALMAS` (either order of the two lines) | number 27, street `CALLE LUNA`; the urbanization lands in `attention` and is **absent from `to_usps()` and from the key** | R2 | the urbanization is lost; two urbanizations with the same street and number in one ZIP get the same key. **key** |
| `CALLE LUNA 123, SAN JUAN PR`, `CALLE DEL SOL 210 2B` | no number, number stays in the street name, `missing_street_number` | R6 (street-first is the incorrect form) | gap, **key** (#319); the number is read from the end |
| `AVE PONCE DE LEON 1500 APT 4` | no number, street `AVE PONCE DE LEON 1500`, unit `APT 4` | R6 | same shape, **key** (#319) |
| `COND LAS AMAPOLAS, SAN JUAN PR` | no number, street `COND LAS AMAPOLAS`, `missing_street_number` | R5 (number 1 when none) | decision needed (see below) |
| `COND DEL MAR APT 103` | street `COND DEL MAR`, unit `APT 103`, `missing_street_number` | R5 | same |
| `1 COND VERDE APT 1120`, `3 VISTA SUITES APT 104` | number 1 / 3, street, unit | R5 | right |
| `COND GARDEN HILLS PLAZA TORRE 2 APT 905` | street `COND ... TORRE 2`, unit, `missing_street_number`, `possibly_truncated` | R5 (`TORRE` is a building line) | gap |
| `RES LAS MARGARITAS EDIF 1 APT 104` | street `RES ... EDIF 1`, unit, `missing_street_number`, `possibly_truncated` | R3, R5 | gap |
| `EDIF 5 APT 12 RES LAS MARGARITAS` | street `EDIF 5`, the project name unparsed, three warnings | R3, R5 | gap |
| `APARTADO 825` | no number, street `APARTADO 825`, `missing_street_number` | R8 (it is a PO Box) | gap, **key** |
| `RUTA RURAL 3 BUZON 12000`, `RUTA ESTRELLA 1 BUZON 18` | street name holds all of it, `missing_street_number` | R8 | gap, **key** |
| `RR 3 BOX 12000`, `HC 03 BOX 1050`, `PO BOX 1195` | read as rural route / highway contract / box; `HC 03` keys as route `3` | R8 | right |
| `RR 2 BOX 1980 SECTOR EL BRINCO` | route and box right, `SECTOR EL BRINCO` unparsed with `unparsed_remainder` | R8 (sector dropped) | right (the text is reported, not kept) |
| `BO PUEBLO CARR 2 KM 14.5` | no number, all in the street name; the key reads `KM 145` (the decimal point is dropped) | none | the key merges `KM 14.5` with `KM 145`; no Pub 28 source |
| `12 CLL LUNA`, `12 AVENIDA LUNA` | street name kept as written | R7 | right (not rewritten) |
| `1 CALLE NORTE`, `12 CALLE OESTE` | `NORTE` and `OESTE` stay in the street name | R9 | right |
| `PR 123 KM 4, ARECIBO PR` | read as the highway `PR 123`, number empty, street `KM 4` | none | see the guard below |
| `PR 123, HOUSTON TX` | street `PR 123` (a Texas private road); in Puerto Rico still the highway `PR 123` | none | right (#314) |

The pattern: the forms that Pub 28 gives as the standard (number then prefix and street, `COND` or `URB` with a number ahead, `RR`, `HC`, `PO BOX`) parse right. The gaps are in the forms real data uses instead: street first, `URB` before or after the street on one line, Spanish box and route words, and block-lot and lettered numbers with a hyphen. The cost is `missing_street_number` and a street name that holds the number, so the key of every such row is a street name, not a number plus street.

## Findings

1. **The urbanization is dropped (R2).** In the field form it goes to `attention` and never reaches `to_usps()` or the key; in one-line input it is either glued to the street name or left unparsed. Pub 28 calls it the only element that tells two same-named streets apart in a ZIP. A rule that reads `URB` as its own part is not enough unless the key keeps it too; that is a key decision for the owner (below).
2. **The #318 rule has support (R2).** Both orders (`URB` before the street, `URB` after the street) are in Pub 28's own figures, so reading `URB NAME` after a street as the urbanization is a Pub 28 reading, not only a data habit. The case `NUMBER URB NAME` (R3) is different: the urbanization stands in for the street and the current parse is right. The rule must tell them apart by whether a street (`CALLE`, `AVE` and the R1 prefixes) is present.
3. **#319 is a data-cleaning reading, not a Pub 28 rule (R6).** Pub 28 gives only the number-first order and says to move a trailing number ahead of the prefix. Reading `CALLE DEL SOL 210` as number 210 is the same move; it can be written as "the standardized form is number first", but the street-first rows in real data (FMCSA, FCC) are what justify it, and the review queue is the way to measure it.
4. **Numbered streets are why the order matters (R6).** `CALLE 19 21` could be street 19, house 21 or the reverse; the prefix rule is Pub 28's reason for always writing `CALLE` before a street number. A rule must not read the last number of `CALLE NN` as a house number when the prefix is followed by only one number.
5. **Spanish box and route words are a separate, small rule (R8).** `APARTADO`, `BUZON`, `BZN`, `RUTA RURAL`, `RUTA ESTRELLA` map to the existing box, RR and HC kinds. They are unambiguous in PR and in states with a Spanish-speaking population, but a street named `RUTA` exists, so scope them to Puerto Rico first. Evidence for the size of this one is still to be measured.
6. **Condominium and residencial names with no number (R5).** Pub 28 asks for the number 1. We cannot invent a number in a parse (the parser reports what the text holds), so the open choice is whether `missing_street_number` stays on `COND LAS AMAPOLAS`. The 0.7.0 policy is that warnings are stable from 0.7.0; a change here would be a rule change that removes a warning, not a new code.
7. **`KM` has no source.** The decimal point lost in the key (`KM 14.5` equals `KM 145`) is a separate defect in the number normalization and applies outside Puerto Rico. It needs its own issue; not part of this epic.
8. **R9 and R11 need no rule.** Spanish directionals are rare and the parser keeps them in the street name, which is what a name such as `CALLE NORTE` needs. The last-line rule is about validity, which the library does not judge.

## Guard

A PR rule keys on the state `PR` or a Puerto Rico ZIP (006, 007, 009), as `is_puerto_rico` does in `tools/harness/probes.py`, with one more case: a one-line input with no state but a Spanish prefix (`CALLE`, `URB`) is a candidate, not a match. `PR` plus a number with no Puerto Rico state or ZIP (#314) stays a road. The parser keeps `PR 123, HOUSTON TX` a road (#314, a `k6` rule).

## What this gives the rule issues

| Issue | What the research settles | What is still open |
|---|---|---|
| #318 (`URB` after the street) | Source: R2 (both orders), I51.4. Rule: with a `CALLE`/`AVE` prefix street present, `URB NAME` is not part of the street. `NUMBER URB NAME` with no street prefix keeps `URB NAME` as the street (R3). | Where the urbanization goes in the output and the key (finding 1). `version:K`. |
| #319 (street-first forms) | Source: R6 and I51.3 (the standard is number first). Cases: `CALLE NAME NUMBER`, `CALLE NAME NUMBER UNIT`, `AVE NAME NUMBER UNIT`. | A rule scope: Puerto Rico only (state or ZIP), or any state. Whether the number is the house number or still `missing_street_number` with the number kept apart. `version:K`. |
| New: lettered and block-lot numbers | Source: R6 (`A-17` to `A17`, `BLQ`, `CASA`, `LOTE`, `NUM` dropped). | Corpus size from the seven sources (`K7`-style lot codes are on the left-as-is list in `usps-pub28-notes.md`, which this would revisit). |
| New: Spanish box and route words | Source: R8. | Size; the PR-only scope. |
| New: condominium and `RES` building lines | Source: R3, R5 (`TORRE`, `EDIF`, name on its own line). | The `missing_street_number` choice (finding 6). |

## Next steps (in the epic's order)

1. Open or reword the rule issues above (#318, #319 stay; the three new ones get a probe each in `PROBES`, or a `NO_PROBE` reason).
2. Build the Puerto Rico review queue from PR rows: `probe_queue.py` drops them today with no opt-out, so the queue needs an `--only-pr` mode or `rule_queue.py` with a PR sample. Roles to match the Pub 28 reading (`street-first`, `urb-after-street`, `condo-no-number`, `apartado`).
3. A benchmark of labeled PR rows, since the suites hold almost none (the epic's measurement table).
4. Corpus cases for each rule (invented addresses, ids with a new prefix), a ledger row in `usps-pub28-notes.md` per rule, and the flagged-share comparison on FMCSA, Netsyms and IRS PR rows.

Source reading cache: `local-data/pub28-cache/pr/` (not committed; USPS content).
