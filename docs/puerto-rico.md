# Puerto Rico addresses

What USPS Publication 28 says about Puerto Rico and Spanish-language addresses, and what the parser does with them in
0.7.0. Seven rules shipped in 0.7.0 with the `k6` key (#314, #318, #319, #747, #748, #749, #750); the rest is on
#818. Every address below is invented.

Read: Pub 28 section 29 (291 to 295), Appendices D5, H and I (I1 to I5); not Appendix J (U.S. Virgin Islands). The
examples there are images; the addresses below copy their shapes. Pub 28 was last changed in October 2024
(`tools/pub28/verify.py`) and has not changed these pages.

Figures: 0.7.0 release candidate (`41c95be`), 2026-11-22, `doorplate parse` on one-line input unless a field form is named.

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

Pub 28 says nothing about `KM` (kilometer markers on `CARR` roads) or lot codes beyond R6, and names the street-first order (`CALLE LUNA 123`) only as the wrong form, though real data uses it.

## What the parser does

Each rule below applies only in Puerto Rico: state `PR`, or a ZIP starting 006, 007 or 009 (`[puerto_rico]` in
`crates/doorplate/data/special.toml`). Outside it every reading is as before, and a row with no state or ZIP is out of
scope. The "Rule" column names the issue of a 0.7.0 rule; those rows changed keys.

| Shape | Parse | Pub 28 | Rule |
|---|---|---|---|
| `1234 AVE ASHFORD APT 1A`, `150 CALLE A` | number, street `AVE ASHFORD` / `CALLE A` (the prefix stays in the name), unit | R1, R5, R7 | |
| `12 CALLE LUNA ST` | street `CALLE LUNA`, suffix `ST`: kept as written | R7 | |
| `A17 CALLE 1`, `199-31 CALLE 19` | number `A17` / `199-31` | R6 | |
| `A-17 CALLE AMAPOLA`, `A 12 CALLE LUNA` | number `A17` / `A12` | R6 | #747 |
| `CALLE 19 BLQ 199 CASA 31` | number `199-31`, street `CALLE 19` (`BLOQUE`, `BLQ`, `BQ`, `CASA`, `LOTE`, `NUM`, `NUMERO`, `#` dropped) | R6 | #747 |
| `CALLE LUNA 123`, `AVE PONCE DE LEON 1500 APT 4`, `CALLE DEL SOL 210 2B` | number 123 / 1500 / 210, street `CALLE LUNA` and so on, unit `APT 4` / `2B` | R6 (street first is the wrong form, read anyway) | #319 |
| `CALLE 19` | street `CALLE 19`, `missing_street_number`: a lone number after a street word is the street's own | R6 | #319 |
| `1234 URB LOS OLMOS` | number 1234, street `URB LOS OLMOS` (no Spanish street word, so the urbanization is the street) | R3 | |
| `27 CALLE LUNA URB LAS PALMAS`, `URB LAS FLORES, CALLE 3 B-12`, `URB LAS FLORES 12 CALLE 3` | urbanization `LAS PALMAS` / `LAS FLORES`, street `CALLE ...`, number | R2, R6 | #318 |
| field form: `27 CALLE LUNA` with `URB LAS PALMAS` on the line above or below | urbanization `LAS PALMAS`; `to_usps()` writes `URB LAS PALMAS` above the street line; the key ends in `URB LAS PALMAS` | R2 | #318 |
| `EXT VISTA BELLA 12 CALLE 4` | all in the street name, `missing_street_number` | R4 | not yet: #818 |
| `1 COND VERDE APT 1120`, `3 VISTA SUITES APT 104` | number 1 / 3, street, unit | R5 | |
| `COND LAS AMAPOLAS`, `COND DEL MAR APT 103` | street `COND ...`, `missing_street_number` (the parser does not supply Pub 28's number 1) | R5 | decided on #724 |
| `COND VISTA REAL TORRE 2 APT 905`, also with the name on its own line; `RES LAS MARGARITAS EDIF 1 APT 104`, `EDIF 5 APT 12 RES LAS MARGARITAS` | street `COND VISTA REAL` / `RES LAS MARGARITAS`, unit `BLDG 2`, second unit `APT 905`, `missing_street_number` | R3, R5 | #749 |
| `12 CALLE LUNA EDIF 3` | the ordinary unit rules | R5 | not yet: #818 |
| `APARTADO 825` | PO Box 825 | R8 | #748 |
| `RUTA RURAL 3 BUZON 12000`, `RUTA ESTRELLA 1 BUZON 18`, `RR 3 BZN 7` | `RR 3 BOX 12000`, `HC 1 BOX 18`, `RR 3 BOX 7`; a leading zero on the route and a hyphen in `17-A` are kept as given | R8 | #748 |
| `RR 2 BOX 1980 SECTOR EL BRINCO` | route and box, `SECTOR EL BRINCO` in `unparsed` with `unparsed_remainder` | R8 (the sector is dropped) | |
| `BO PUEBLO CARR 2 KM 14.5` | all in the street name, `missing_street_number`; the key keeps `KM 14.5` apart from `KM 145` | none | #750 (any state) |
| `1 CALLE NORTE`, `12 CALLE OESTE` | the Spanish directional stays in the street name | R9 | |
| `PR 123 KM 4, ARECIBO PR` | highway `PR HIGHWAY 123`, street `KM 4`, `missing_street_number` | none | |
| `123 PR 462, HOUSTON TX` | street `PR 462` (a Texas private road); in Puerto Rico, or with no state, the highway | none | #314 (outside Puerto Rico) |

How the rules decide:

- **Street words.** `CALLE`, `AVE`, `CARR`, `PASEO`, `CAMINO`, `VIA` and the rest of the list in `special.toml`. `CIR`,
  `VIS` and `ENT` are left out because they are also English suffixes.
- **Street first (#319).** After a street word, a number at the end of the street, before a unit or a new segment, is
  the house number, with no warning. The street must keep a word of its own after the street word, and a number right
  after `KM` is never taken (`CARR 2 KM 14` is unchanged). One value after the number is a bare unit.
- **Urbanization (#318).** `URB NAME` or `URBANIZACION NAME`, before or after a street that has a street word, on the
  same line or its own, goes to the `urbanization` field without `URB`. RESO has no field for it, so the RESO output
  leaves it out ([`reso-mapping.md`](reso-mapping.md)); the key format is in [`key-format.md`](key-format.md).
- **Building lines (#749).** After a project name opening with `COND`, `CONDOMINIO`, `RES` or `RESIDENCIAL`, `TORRE`,
  `EDIF` or `EDIFICIO` and a value are the unit `BLDG`, and the apartment after it the second unit.
- **Box and route words (#748).** `APARTADO`, `RUTA RURAL`, `RUTA ESTRELLA`, `BUZON`, `BZN`. Scoped to Puerto Rico
  because a street named `RUTA` exists elsewhere.

Not needed: R9 (Spanish directionals are rare, and a name such as `CALLE NORTE` must keep them) and R11 (city validity,
which the library does not judge). Left for later (#818): the standalone urbanization names of R4, a building line
after a numbered street, and the flagged-share comparison on the Puerto Rico rows of FMCSA, Netsyms and IRS.

The ledger rows with their sources are in [`usps-pub28-notes.md`](usps-pub28-notes.md). Source reading cache:
`local-data/pub28-cache/pr/` (not committed; USPS content).
