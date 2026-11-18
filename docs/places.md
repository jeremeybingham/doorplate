# National place list (`crates/doorplate/data/places/`)

Layer 2 of the lexicon (`docs/how-it-works.md`): place names and ZIP places for every
state, DC and Puerto Rico, generated from public data. It lets the parser find a city on
a line with no commas, tell a street from a city before a ZIP, and complete a cut-off
city. Hand-curated rows (Florida's; [Curated rows](#curated-rows) below) sit above it and win for their state.

## Files

| File | Rows | Columns |
|---|---|---|
| `places.toml` | | list version, states, sources |
| `places.tsv` | 50,408 places: 19,491 municipalities, 20,021 places, 10,896 subdivisions; 16,291 variants | `state`, `name`, `county`, `kind`, `sources`, `variants` |
| `zips.tsv` | 41,154 ZIPs | `zip`, `state`, `place` |

The curated rows ([below](#curated-rows)) have the same shape, with an `evidence` column and, for ZIPs, a
`shared` column; the national table has no `shared` column, because GeoNames gives each ZIP one place.

- `name` is upper-case words of letters and digits: accents folded
  (`ANASCO`), apostrophes and periods dropped (`OFALLON`), other
  punctuation a space (`WINSTON SALEM`), `ST`, `FT`, `MT` written out
  (`SAINT LOUIS`), as in the Florida curated rows.
- `kind` is `municipality` (a city, town, village or borough with its own
  government), `place` (a Census designated place, a Puerto Rico comunidad,
  or a postal name GeoNames has and the Census does not) or `subdivision`
  (a township and the like; below).
- `sources` is `census`, `geonames` or both.
- `variants` are other spellings of a name that is the same place: a
  township's bare name and `TWP` form (`ROARING BROOK TOWNSHIP` has
  `ROARING BROOK` and `ROARING BROOK TWP`), and the long name of a
  consolidated city-county (`ATHENS` has `ATHENS CLARKE COUNTY`). There are
  no misspellings in this list; those are curated (the Florida curated rows).
- `county` is the county name without `County`, `Parish` or `Municipio`
  (`Baltimore city` stays `BALTIMORE CITY`). It is for telling places apart
  and is not used by the parser yet.

## Sources and licenses

What may be committed, and how data seen only in private sources (such as Netsyms) may
reach this list: [`data-policy.md`](data-policy.md).

| Data | Source | License |
|---|---|---|
| Places, county subdivisions (`census`) | US Census Bureau 2024 Gazetteer Files: places (32,333), county subdivisions (36,421), counties (3,222), https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/ | Public domain |
| County of a place or subdivision | Census 2020 reference lists `national_place_by_county2020.txt` and `national_cousub2020.txt`, https://www2.census.gov/geo/docs/reference/codes2020/ | Public domain |
| ZIP to place, postal-only places, county of a postal-only place (`geonames`) | GeoNames postal codes `US.zip` (41,489 rows) and `PR.zip` (177), https://download.geonames.org/export/zip/, downloaded 2026-10-16 | CC BY 4.0, attribution in `NOTICE` |

The source files are in `local-data/places/` (not committed; URLs, dates and
checksums in `local-data/README.md` and `SHA256SUMS` there).

## How it is built

```sh
python3 tools/places/build_us.py            # reads local-data/places/
```

The output is deterministic. The builder stops on a name that is not upper-case words, two
names the parser's place comparison rule (`lexicon/place_key.rs`, ported into the script)
would treat as one in a state, a ZIP whose place is not in `places.tsv` or lies outside
the place's state, and a state with no places or no ZIPs.

## What the builder settles

- **Places.** Every Gazetteer place in the 50 states, DC and Puerto Rico, without the type
  word (`Alachua city` is `ALACHUA`; `Milford city (balance)` is `MILFORD`; the part after
  a comma is dropped). A consolidated city-county is called by its city (`ATHENS`,
  `LOUISVILLE`), with the Census name as a variant; Massachusetts' `Amherst Town` is
  `AMHERST`, with `AMHERST TOWN` a variant.
- **Subdivisions.** Only active governments (Census `FUNCSTAT` A) whose type mail uses.
  Townships, plantations, gores, grants, purchases and locations keep the type word
  (`WASHINGTON TOWNSHIP`) and add the bare name and, for townships and plantations, `TWP`
  and `PLT` forms as variants. Towns, cities, villages and boroughs that are not Census
  places (New England, New York, Wisconsin) take the bare name. Left out: Census county
  divisions (`CCD`), unorganized territories, precincts, districts, wards, barrios and
  numbered townships (20,299 subdivisions kept). A bare name that a place already has, or
  that two subdivisions share, is not added as a variant (4,400 and 78 dropped).
- **One county for a place that spans several.** The 2020 list names every county a place
  touches, not how much lies in each. The 1,301 places that span several get the county
  whose center (Gazetteer `INTPTLAT`/`INTPTLONG`) is nearest the place's internal point; a
  Connecticut place takes the lowest county code (the 2022 counties are missing from the
  2024 Gazetteer). It is a tie-break for display, not a fact about the place.
- **A subdivision name used several times in a state** (`WASHINGTON TOWNSHIP` in 22
  Pennsylvania counties) is one row with no county. The 462 places newer than the 2020
  county list get a county only if GeoNames has a ZIP with the same name in the state
  (a guess from the nearest center would mislead). 1,503 rows have no county in all.
- **GeoNames names.** Each ZIP's place is GeoNames' name for it, folded to the same
  spelling. A name the Census does not have becomes a `place` row (6,508 rows, `sources` =
  `geonames`: `BROOKLYN`, `WASHINGTON CROSSING`). Where a Census row and a GeoNames name
  are the same place by the comparison rule, the row gets both sources. 206 pairs differ
  only in spacing (`LAKEVIEW`, `LAKE VIEW`); the parser cannot tell them apart, so there
  is one row, spelled as the better kind of source has it (municipality over place over
  subdivision).
- **Mail names added by hand (#486).** `tools/places/extra_places.tsv` lists 33 places and
  one variant that real address data writes as the city and that neither the Census nor
  the GeoNames ZIP places have: Queens, Bronx, Brooklyn and Manhattan mail names
  (`BRIARWOOD`, `THE BRONX`, `QUEENS`), Los Angeles ones (`ARLETA`), military installations
  (`FORT CAVAZOS`), and a few island and neighborhood names (`HILTON HEAD`). `NEW YORK CITY`
  is a variant of `NEW YORK`. Each is a populated place in the GeoNames dump (`US.txt`), so
  its `sources` is `geonames`, and it has 100 or more city-field rows in one of the real
  sources; the counts are selection evidence and stay out of the repository
  (`data-policy.md`). Left out: `LA` (a state code) and names that are a street name more
  often than a city (`SANTA FE`, `HARRISON`, `CRESTVIEW`). Misspellings and abbreviations
  (`BKLYN`, `NYC`) are not added: this list has none. `kind` is `place`. The New York City
  names carry their county (from the GeoNames county code), because the Queens house-number
  rule (`21-77` keys as `2177`) reads the place's county; the county is empty for the
  others. Before, `100 EXAMPLE BRIARWOOD NY 11435` read the city as part of the street
  (`missing_city`); now the city is `BRIARWOOD` (corpus `mn-001` to `mn-008`).
- **Puerto Rico is in this pass** (`PR.zip` is a separate GeoNames file whose
  county column is the municipio). The 513 GeoNames rows left out are the
  511 military ZIPs (`APO AE` and the like, no state) and 2 Marshall
  Islands ZIPs. Other territories have no Census places in these files.
  Puerto Rico urbanizations are not handled here.

## How it is compiled in

`build.rs` compiles `crates/doorplate/data/places/` when the `places-us` cargo feature is on
(it is by default), under the curated rows:

- A state with curated rows (`zip_city_check` in `places.toml`: Florida) keeps the curated places and ZIPs. A national
  row whose comparison key the curated rows already have, as a name or a variant, is the
  curated row's and is skipped; the national list adds the rest. For Florida that is 405
  Census places the curated rows lack (`TRINITY`, `CITRUS SPRINGS`, all CDPs): 727 curated
  places and 1,132 with the national rows. The builder
  renames the Census's `Everglades` to `EVERGLADES CITY` (`CENSUS_NAMES` in
  `build_us.py`), the curated name. The curated 1,473 main ZIPs are untouched
  (GeoNames is the source of both); the observed-ZIP pairs (rows of `curated_zips.tsv` with no `place`) are added
  once the national rows are in, and left out when `places-us` is off.
- For every other state a name, variant or ZIP that would lead to two places
  is a build error, as in the curated rows. Names, counties and kinds are checked the
  same way.
- The parser reads the national layer for every state:
  `Lexicons::place`, `zip_places`, `places` and `is_place` cover all 52. So
  the Florida behaviors work everywhere: a city on a line with no commas, a
  street versus a city before a ZIP, a city run into the street, a cut-off
  city completed from the ZIP, and the place from the ZIP. A `default_state`
  hint looks a city up in the hinted state's places.
  `zip_city_mismatch` stays limited to the states in `zip_city_check`
  (`Lexicons::checks_zip_city`), because the list names one place per
  ZIP, and its place equals the written city on only 75.8% of the
  benchmark's addresses.

The tables are packed records in `OUT_DIR`, read with `include_bytes!` (`emit_places` in
`build.rs` has the layout); a table of `&str` costs a pointer and a relocation per string
and added 13.4 MB. Packed, the national list adds **2.9 MB** to the stripped release binary
(1.57 MB without it, 4.49 MB with it, as measured when it was added; current sizes are on
`docs/speed-and-size.md`), and `build.rs` takes about 2 seconds more.

## Coverage

Measured on the blind [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark) (`local-data/geocode-benchmark/`,
26,745 addresses with a city and a state), by the place comparison rule:

| | Share |
|---|---|
| City is in the list for its state | 87.4% (Gazetteer places alone: 73.5%) |
| ZIP is in `zips.tsv` | 88.2% |
| ZIP's place equals the city | 75.8% |

The last row is why `zip_city_mismatch` stays limited to the states in `zip_city_check`:
GeoNames names one place per ZIP, and many ZIPs are used by several. The list contains
657 of the Florida curated rows' 665 original places (the curated rows win for Florida and add
`BAREFOOT BAY`, `BRUCE`, `ENTERPRISE`, `INLET BEACH`, `PENSACOLA BEACH`, `PERDIDO KEY`,
`WALNUT HILL`, `WEEKI WACHEE`). Corpus `rg-030` shows the gap: `BELLVIEW` is a Census place
in Escambia County, but GeoNames names its ZIP 32526 `PENSACOLA`, so `curated_zips.tsv`
lists `BELLVIEW` as a place of 32526.


## Curated rows

Florida's places, spellings and ZIPs were checked by hand against real data. They are two hand-edited files
next to the generated tables, compiled in every build (no feature), and they are not output of `build_us.py`:

| File | Rows | Columns |
|---|---|---|
| `curated_places.tsv` | 727 places (411 municipalities, 316 other places), 1,072 variants | `state`, `name`, `county`, `kind`, `variants`, `evidence` |
| `curated_zips.tsv` | 1,937 rows: 1,473 main ZIPs (107 with a second place), 464 observed (ZIP, place) pairs | `zip`, `state`, `place`, `shared`, `evidence` |

`places.toml` lists the states whose ZIP-to-place table is complete enough to warn on (`zip_city_check = ["FL"]`):
`zip_city_mismatch` is raised only there (`Lexicons::checks_zip_city`). Street spellings that mean something
else in a state are in `data/suffixes.toml` and `data/special.toml` (`[[highway.state]]`: `SR` is `STATE ROAD`
in Florida, below).

- `name` is the place in upper case with `SAINT` written out (`PORT SAINT LUCIE`) and no punctuation
  (`OPA LOCKA`). `county` is the county name; Miami-Dade is `DADE`. `kind` is `municipality` or `place`.
- `variants` are other spellings seen in county listings and public address lists, mostly typos (`ADVENTURA`
  for AVENTURA). Some are the names of real places in other states (`VENTURA`, `STANFORD`, `RENTON`), so the
  parser trusts a variant only in a city field or when the ZIP agrees.
- `evidence` is `sources:` the list of where a place came from (`original` is the authors' first hand-made list,
  `observed` a place first seen in county listings, `census`, `geonames`) or `addresses:N`, the distinct street
  addresses that show it. A `curated_zips.tsv` row with a `place` is a ZIP's main place (GeoNames' name, copied as
  is); a row with an empty `place` adds the place in `shared` to the ZIP, from real addresses; the `shared`
  column of a main row lists places that also use the ZIP (it straddles a boundary).
- `build.rs` fails on a malformed or contradictory row: a name or variant that leads to two places, a ZIP that is
  the main ZIP of two places, a shared place that is unknown or already used, a name that is not upper-case
  words, or a row with no evidence. Additions are add-only: a name or spelling whose key is already present is an
  error.

### Sources

| Data | Source | License |
|---|---|---|
| Place list, county, kind, variants, shared ZIPs | Curated by the authors from the sources below and from Florida county listings | MIT OR Apache-2.0 |
| Place names (`census`) | US Census Bureau, 2024 Gazetteer Files, places, Florida | Public domain |
| ZIP to main place (`geonames`) | GeoNames postal code export, `US.zip`, Florida rows, https://download.geonames.org/export/zip/ | CC BY 4.0, attribution in `NOTICE` |
| Observed ZIP places, added communities and spellings, the `SR` rule and the evidence for `CR` and `CTY HWY` (moved to the base tables, #108) | A Florida public-record address export (2025-10-10, 445,252 Florida addresses) and four further public-record address files (961,275 distinct Florida addresses together); and the Florida DBPR licensee files (downloaded 2026-10-18; 1,794,538 distinct Florida street addresses with a city, from licensees' mailing and location addresses). Only city, ZIP and the parsed street key were used; no names are kept | Florida public record (Chapter 119, Florida Statutes) |

### Rules for additions

- **A community** is added when at least 10 distinct street addresses use it as the city and it has one main ZIP
  (the ZIP with most of its addresses has at least half of them). The county is GeoNames' county for that ZIP,
  in the curated spelling (`DADE`, `ST. LUCIE`). It must be a real place: left out are split ones
  (`PLANTATION KEY`), resorts (`HIGH POINT RESORT`), non-places (`CIUDAD DE MIAMI`, `HIALEAH LAKES`) and strings
  with mis-encoded accents.
- **A spelling** of a known place is added when at least 10 distinct addresses use it. `LA BELLE` needs an entry
  because the place comparison rule reads `LA` as the suffix LANE; changing that rule would merge `LADUE` and
  `LA DUE` in Missouri. Two spellings the place key folds together (`GREEN ACRES CITY`, `GREENACRES CITY`) need
  one row or none.
- **An observed ZIP pair** (a place written with a ZIP the main row does not give it) is kept when the city is a
  curated name or listed variant and either at least 10 distinct street addresses use it and they are at least
  1% of the ZIP's addresses, or at least 3 that are at least 5% (small and PO Box ZIPs). Fewer stay out: they
  are mostly a nearby big city written for a suburb (`ORLANDO` in Saint Cloud's 34771), which
  `zip_city_mismatch` should still flag.
- **A variant that is the name of a different Census place is dropped:** `BELLVIEW` is a Census place in
  Escambia County (ZIP 32526), not a spelling of BELLEVIEW (Marion County).
- **Placeholders written as the city are not curated** (see Known gaps).

The `addresses` count of a row added from the DBPR files counts distinct street addresses in those files only
(not summed with the earlier export).

### How the parser uses them

- **Finding the city on one line.** With the state (or, with none, the ZIP's state) known, the longest run of
  words before the state or ZIP that is a place becomes the city, preferring a place the ZIP belongs to
  (`123 MAIN ST WEST PALM BEACH FL 33401`). A variant counts there only when the ZIP agrees. Otherwise the
  suffix rule decides. This is the same for every state.
- **`zip_city_mismatch`**: the city is a known place, but the ZIP table does not list the ZIP for it. GeoNames
  gives one place per ZIP, while USPS accepts several city names for many ZIPs, so this flags a disagreement
  with the table, not a wrong address (`FORT MCCOY` with 32182). On 440,000 distinct Florida addresses it fires
  on about 0.4%, mostly a nearby big city written for a suburb.
- **`CR` is CIRCLE, `CTY HWY` is COUNTY HIGHWAY** (the base tables since #108; the evidence was first collected
  in Florida). The base table read `CR` after a street name as CREEK (an older Appendix C1 transcription). In
  the Florida address data 333 street lines end a name in `CR`; for 277 the same street in the same ZIP is also
  written CIRCLE or CIR, for none CREEK or CRK; the all-state sources agree (817 of 1,742 street and ZIP
  combinations Circle, 6 Creek). So `CR` is CIR in every state, with `non_standard_abbreviation`; `CR` before a
  route number stays COUNTY ROAD. `CTY HWY` (5 rows here, 235 in all-state sources, mostly Minnesota) is COUNTY
  HIGHWAY, and `CTY RD` and `CTY ROAD` are COUNTY ROAD, before a route number, raising
  `non_standard_abbreviation`.
- **`SR` is STATE ROAD in Florida** (`special.toml` `[[highway.state]]`; the rule and its evidence are in
  [`usps-pub28-notes.md`](usps-pub28-notes.md)).

### Known gaps

- Cities that match no place: 0.36% of Florida rows in the DBPR files (0.51% before they were added), against
  0.41% in the earlier export. The largest are not communities but placeholders and counties written as the city
  (`NO CITY CODE`, `FLORIDA`, `MIAMI DADE`, `BROWARD`, `UNINCORPORATED`, `UNKNOWN`, `SOUTH FLORIDA`, the bare
  counties `ORANGE` and `PINELLAS`; about 600 distinct addresses), and communities and spellings under the
  10-address line. Whether to read these as placeholders is open (#11). `MD MIAMI` and `MD HOMESTEAD` (a
  Miami-Dade district code before the city) are listed spellings.
- `zip_city_mismatch` fires on 0.68% of Florida rows in the DBPR files (0.78% before), a long tail of about
  7,000 (city, ZIP) pairs, mostly a nearby big city written for a suburb. The
  [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark)'s scores did not move.
- A city that is no known place, with a ZIP the table knows: `place` stays `None`.
