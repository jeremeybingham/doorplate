# The benchmark suite (specification)

A fixed, versioned set of labeled addresses that ships in the repository, and one runner
that scores doorplate and usaddress on it under a fixed, modest resource profile. This page
is the specification. How to run it: [`running-benchmarks.md`](running-benchmarks.md). The results:
[`benchmarks.md`](benchmarks.md).

No suite row is a real address point (see "Anonymization").

## What it is for, and what it is not

- **A benchmark anyone can rerun**, without the private data in `local-data/` (the Netsyms
  database, the [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark), the Florida exports) and on ordinary hardware.
- **A fair comparison with usaddress.** Neither library's rules, model or tests were made
  from it, its labels come from neither parser, and its mix is fixed before either parser runs
  on it.
- **Not a regression test.** It holds the known blind spots of both libraries at a stated
  rate, and neither is expected to reach 100%. The golden corpus (`tests/corpus/`) stays the
  regression set, and the rules under "Keeping it fair" say why a failure here is not a
  to-do item.

## Two tracks

The suite compares doorplate with usaddress first. A second track measures what only doorplate
does. The two are kept apart so that the second never blurs the first.

| | Comparison track | doorplate-only track |
|---|---|---|
| File | `benchmarks/suite/v1/compare.jsonl.gz` | `benchmarks/suite/v1/doorplate.jsonl.gz` |
| Command | `python benchmarks/suite.py compare` | `python benchmarks/suite.py doorplate` |
| Libraries | doorplate and usaddress, on the same input strings | doorplate alone |
| Measures | Token labels, in usaddress's label set | Fields input, standardized output, key stability, warnings |
| Reported | First, in its own section | Under its own heading, labeled as having no usaddress counterpart |

Both files are built from the same records and share record ids. The comparison file holds
nothing that only one library can do. No figure from the doorplate track appears in a
doorplate-versus-usaddress table, a headline row or a ratio.

## Layout

```
benchmarks/suite/
  v1/
    compare.jsonl.gz       # the comparison track
    doorplate.jsonl.gz     # the doorplate-only track
    MANIFEST.md            # composition counts, sources, the build commit, checksums
  v2/
    scoring.json           # the records of v1, with the letter convention (see "Versions")
    MANIFEST.md
  README.md                # how to run it
benchmarks/suite.py        # the runner (both tracks, the resource profile)
tools/benchsuite/build.py  # the generator (maintainers only: reads local-data/)
```

A version directory is never edited after it is published (see "Versions").

## Record format

`compare.jsonl.gz`, one JSON object per line:

```json
{"id": "v1-000123", "input": "1234 W Example Ave Apt 5, Springfield, IL 62704",
 "tokens": [["1234", "AddressNumber"], ["W", "StreetNamePreDirectional"], ["Example", "StreetName"],
            ["Ave", "StreetNamePostType"], ["Apt", "OccupancyType"], ["5", "OccupancyIdentifier"],
            ["Springfield", "PlaceName"], ["IL", "StateName"], ["62704", "ZipCode"]],
 "stratum": "natural", "style": "mixed-commas", "mods": [], "type": "street", "state": "IL",
 "source": "nad", "tags": []}
```

- `input`: one string, the only input both parsers get.
- `tokens`: the gold labels, in usaddress's label set, assigned by the generator. A token
  with no letter or digit is not scored, as in `tools/compare/compare_usaddress.py`.
- `stratum`: `natural`, `hard` or `hand` (see "Composition").
- `style`: how the record was written (see "Styles"); `mods` lists the modifiers applied to it
  (`hash-unit`, `zip4`, `no-zip`, `no-state`, `noise`, `extra-text`).
- `type`: `street`, `po_box`, `rural`, `highway`, `military` or `general_delivery`.
- `source`: `nad`, `tiger`, `synthetic` (a shape NAD has no rows for, such as a PO box) or
  `hand`.
- `tags`: the blind-spot classes the record belongs to (see "The hard stratum"). Empty for
  most `natural` records.

`doorplate.jsonl.gz` has the same `id`, `stratum`, `type`, `state`, `source` and `tags`, and:

- `fields`: `{line1, line2, city, state, zip}`, the same record as `parse_fields` would get it.
- `inputs`: the record written in two to four styles, for the key-stability measure.
- `expect`: the components, named as in the golden corpus (`docs/tests/corpus.md`), in
  Pub 28 standard form.
- `usps`: the expected `to_usps()` delivery line and last line.

## Sources

| Source | What it gives | Ships? |
|---|---|---|
| National Address Database (NAD) r24 | Street, city, state and ZIP for street records, with the parts already split into labeled columns by the data providers | Yes, anonymized (below) |
| Census TIGER/Line feature names | Street names for the states NAD lacks (HI, MI, MS, NH, NV, PR), with invented numbers | Yes (public domain). A download: needs a go-ahead |
| Generator templates | PO boxes, rural and highway-contract routes, military and general delivery, which NAD (address points) does not hold. Real city, state and ZIP from NAD; invented box and route numbers | Yes |
| Hand-labeled shapes | The `hand` stratum: invented addresses copying the shapes of messy real rows (MLS fields, forms, mailing lists) | Yes |
| Netsyms, the Florida exports and DBPR files, the geocode benchmark | **Counts only**: how often each shape and style occurs, and the blind-spot rates | No. Only aggregate counts reach the suite, as `docs/data-policy.md` allows |

### Anonymization

A suite row is never a real address point:

- **House numbers are invented.** Each is a random number of the same shape as the source's
  (digit count, a letter or fraction suffix, a hyphenated form), and never equal to it.
- **Unit values are invented** in the same way. The designator (`APT`, `STE`) is kept.
- **Only common streets.** A street is used only if NAD has at least 20 address points on it
  in that ZIP code, so an invented number does not point to one of a handful of houses.
- **Building names are not used.** A provider's building value can hold a business or family name, and
  `v1` leaves building names out altogether (see "How the mix was chosen").
- **Nothing else is carried over**: no coordinates, no NAD source names, no ids.
- Street, city, state and ZIP are kept. They are public facts, and the shapes under test
  depend on them.

## Labels

The gold labels come from the field each token was written from, never from a parser. For NAD
records:

| NAD column | usaddress label |
|---|---|
| `AddNum_Pre` | `AddressNumberPrefix` |
| `Add_Number` | `AddressNumber` |
| `AddNum_Suf` | `AddressNumberSuffix` |
| `St_PreMod` | `StreetNamePreModifier` |
| `St_PreDir` | `StreetNamePreDirectional` |
| `St_PreTyp` | `StreetNamePreType` |
| `St_PreSep` (`OF THE`) | Fixed in the label audit, following usaddress's training data; the coarse score folds it into the street either way |
| `St_Name` | `StreetName` |
| `St_PosTyp` | `StreetNamePostType` |
| `St_PosDir` | `StreetNamePostDirectional` |
| `St_PosMod` | `StreetName` (usaddress has no post-modifier label) |
| `Building` | Not used in `v1` |
| `Floor`, `Unit`, `Room`: designator, value | `OccupancyType`, `OccupancyIdentifier` |
| `Post_City` | `PlaceName` |
| `State` | `StateName` |
| `Zip_Code`, `Plus_4` | `ZipCode` |

A unit value is split into designator and value with the Pub 28 Appendix C2 list (USPS data,
not a doorplate rule). PO box, route, military and general-delivery records use the `USPSBox*`
and `USPSBoxGroup*` labels as `docs/usaddress-compat.md` lists them. Recipient, `C/O` and
country text added by a style get `Recipient` and `CountryName`.

**Provider splits that are wrong** (a suffix left inside `St_Name`, a directional in the
name) are found in the label audit and fixed in the generator, never in single rows and never
by copying either parser's output.

## Styles

A style is a way of writing a record as one string. The generator picks one per record with the
frequencies measured in the local data (counts only), so the mix matches what people have:

| Style | Example (invented) |
|---|---|
| `mixed-commas` | `1234 W Example Ave Apt 5, Springfield, IL 62704` |
| `upper-commas` | `1234 W EXAMPLE AVE APT 5, SPRINGFIELD, IL 62704` |
| `upper-nocommas` (the geocode style) | `1234 W EXAMPLE AVE APT 5 SPRINGFIELD IL 62704` |
| `spelled-out` | `1234 West Example Avenue Apartment 5, Springfield, IL 62704` |
| `hash-unit` / `bare-unit` | `... AVE # 5, ...` / `... AVE 5B, ...` |
| `zip4`, `no-zip`, `no-state` | `... IL 62704-1234` / `... SPRINGFIELD IL` / `... SPRINGFIELD 62704` |
| `noise` | doubled spaces, stray periods, a cut-off city, at measured rates |
| `extra-text` | a leading recipient or `C/O` line, a trailing `USA` |

The final list and the frequencies go in `MANIFEST.md`.

## Composition

The mix is fixed here **before either parser runs on the suite**. About 20,000 records:

| Stratum | Share | Records | How it is drawn |
|---|---|---|---|
| `natural` | 80% | about 16,000 | Random, weighted by state population and by the measured shape and style frequencies. Not selected on how either parser does: its score is the headline estimate |
| `hard` | 15% | about 3,000 | A count for each blind-spot class of either library (below) |
| `hand` | 5% | about 1,000 | Hand-labeled real shapes, checked twice |

Each reported group has at least 500 records, so a group's figure has a 95% interval of about
±2 points.

The `natural` mix by address type, from counts in the local data:

| Address type | Share of `natural` | Records of 16,000 | Basis |
|---|---|---|---|
| Street, no unit | 83.6% | about 13,380 | The rest after the rows below |
| Street with a unit | 12.2% | about 1,950 | 12.7% of NAD rows have a unit; 9.7% of Florida DBPR line 1s show one |
| PO box | 2.7% | about 430 | 2.75% of the 470,000 DBPR mailing addresses of a known type |
| Rural or highway-contract route | 0.6% | 100 (floor) | Measured 0.03%: too rare to sample without a floor |
| Military | 0.6% | 100 (floor) | Measured 0.004% |
| General delivery | 0.3% | 50 (floor) | Measured: 1 row in 500,000 |

### The hard stratum

One inventory, made the same way for both libraries (see "How the mix was chosen"): strings rendered from the
local sources in each style, both parsers run on them, and their errors sorted into classes by
one classifier. **Every class above 1 in 10,000 records in the local data gets its proportional
share of the 3,000, with a floor of 50.** Classes are not added or dropped by hand.

The classes, with their quotas, are in `MANIFEST.md`. A named building is not one of them.

### The hand stratum

90 shapes written by hand in `tools/benchsuite/hand/shapes.txt`, each with its gold labels, copying the forms messy real
rows take: case and comma variants, a dozen unit forms, directionals in several spellings, state routes and county roads,
fractions and hyphenated numbers, cities with `St.` or `Mt.`, a recipient or `C/O` line, a trailing `USA`, PO boxes,
rural, highway and military routes, general delivery, a few intersections. `tools/benchsuite/hand.py` fills the slots with
invented street names and numbers and real city, state and ZIP combinations, and writes `tools/benchsuite/hand/hand.jsonl`
(1,000 records, at most 38 per shape; shipped, since nothing in it is real but the place names). Labels come from the
templates, never from a parser. A program checks that the labeled tokens are the tokens `usaddress.tokenize` finds, and
that no string repeats or is excluded; the shapes were also read a second time. The stratum includes forms doorplate
does not model (intersections, a recipient, `USA`) at the rates the shapes give them. The runner scores by character span,
as `tools/compare/compare_usaddress.py` does, so a score does not depend on how a parser cuts the text.

### Exclusions

The generator drops any record whose input string (whitespace collapsed, lowercased) appears in:

- usaddress's training files at the pinned commit (the fetcher in `tools/compare/training_overlap.py`)
- usaddress's test files (`tests/external/usaddress/`)
- the golden corpus (`tests/corpus/`) or the Pub 28 examples
- the geocode benchmark's splits

It also drops duplicates within the suite, and the NAD rows the label rules do not cover: a building,
floor or room value, a unit in a form the designator list does not read (a lone word, a glued
designator, a fraction), and the provider splits found while building the generator: a street type or
direction left inside the name, a route name with a number and no type column, a house number of
zeros, and a city that is a placeholder (`NOT STATED`), holds a comma or a street type. Each is a rule of
`provider_split` in `tools/benchsuite/build.py`, never a single row.

## Scoring

### Comparison track

The scoring is `tools/compare/compare_usaddress.py`'s, imported by the runner rather than
rewritten:

- Tokens are compared one by one, and a whole address is right only when every token is.
  Scores are coarse (street parts folded into `StreetName`) and fine.
- `AddressNumberSuffix` counts as `AddressNumber` on both sides, as now.
- **Two headline figures for each library:**
  - *Shared labels*: the records whose gold labels both libraries model. This is the
    out-of-scope rule of `compare_usaddress.py`.
  - *All records*: no record is left out. A label only one library models counts as wrong for
    the other, so the blind spots stay in the figure.
- **Broken down** by stratum, style, address type and blind-spot tag, each with a 95% Wilson
  interval.
- **A paired table**: both right, only doorplate, only usaddress, both wrong.
- usaddress is pinned (a build records its version in `MANIFEST.md`). The runner prints its version and
  scores `usaddress.parse`, so `RepeatedLabelError` cannot drop a record.

### doorplate-only track

- **Fields input**: `parse_fields` on `fields`, scored on the components in `expect`.
- **Standardized output**: the components in Pub 28 form, and the `to_usps()` lines.
- **Key stability**: the share of records whose `inputs` (the same record in several styles)
  all give the same `k5` key, and the share of keys shared by two different records.
- **Warnings**: of the records parsed wrong, the share that raised a warning; of those parsed
  right, the share that raised one.

## The resource profile

The reference profile is **4 logical CPUs and 8 GB of memory, on Linux**. It is what a
GitHub-hosted `ubuntu-latest` runner on a public repository has, and what an ordinary laptop has.
The profile applies to benchmark runs only (builds, tests and the other tools are not limited). The runner applies it
itself:

- `os.sched_setaffinity` to 4 CPUs, and `RAYON_NUM_THREADS=4` for doorplate's batch calls
- an 8 GB `RLIMIT_AS` on the processes it starts (an address-space limit, so an approximation;
  peak resident memory is reported as well)
- a header that prints the CPU model, the CPUs and limits it got, the operating system, and
  the versions of doorplate, usaddress, Rust and Python

Speed is reported on 1 thread and on the profile's 4 threads, never on all cores. Accuracy does
not depend on the profile; speed and memory do, so the speed figures lead with ratios. A
`workflow_dispatch` job in CI runs the suite on a real runner. On macOS and Windows, run it in
Docker with `--cpus=4 --memory=8g`. The whole suite, both tracks and both libraries, should
finish in a few minutes under the profile.

## Keeping it fair

- **The suite is not a work list.** A rule change must have a reason from another source (a
  corpus case, Netsyms, NAD, a report), with its own invented corpus case. "Improves the suite
  score" is never a pull request's reason, and suite records are never copied into the corpus.
- **A private twin.** The same recipe with a seed that is not published builds a holdout in
  `local-data/`. At each release, both are scored. If the public suite's score pulls away from
  the twin's, the public set is being tuned to.
- **Blind label audit.** Doubtful gold labels are reviewed with both parsers' outputs hidden,
  and a gold label is never copied from either parser.
- **The mix is fixed first.** The composition above is completed and signed off before the
  first scored run, and is not changed after it in that version.

## Versions

- A version directory is never edited after it is published. Label errors found later go into a new version, and
  a new version is also needed when the usaddress pin moves or a source is replaced; the old one stays runnable.
- `v2` holds the same 19,586 records as `v1` (`records_from` points at `v1`; nothing is copied) and changes only
  the comparison track's scoring: a gold token that is a single letter A to D, labelled `AddressNumberSuffix`
  and directly after an `AddressNumber`, is right when the library labels it `AddressNumber`,
  `AddressNumberSuffix` or `OccupancyIdentifier`. A letter read as street name is still wrong.
- It moves 241 records (207 `hard`, 33 `natural`, 1 `hand`), and nothing in the doorplate-only track.
  usaddress's figures are the same in both. Rule and counts: `benchmarks/suite/v2/MANIFEST.md`.

## How the mix was chosen

The style weights of `v1` are **chosen, not measured**: 30% `upper-commas`, 20% `mixed-commas`, 25%
`upper-nocommas`, 15% `spelled-out` and 10% `mixed-nocommas`, with the modifiers `hash-unit` (10% of
designator units), `no-zip` (3%), `no-state` (2%), `noise` (5%) and `extra-text` (3%). The local sources
are 99% uppercase, so how often people write mixed case cannot be measured there. What was measured, as
counts only: 93% of the Florida auction listings have two commas (the geocode benchmark has none), 7.2% of
DBPR line 1s have a unit designator word and 2.5% a `#`, 32% spell the street type out, and 13.2% of NAD
rows have a unit.

The size (about 20,000 records, 80% `natural`, 15% `hard`, 5% `hand`) and the weights were fixed before
either parser was scored. The `hard` quotas come from an inventory of 200,000 records drawn from NAD, written
in these styles, labeled from the NAD columns and run through both parsers; one classifier sorted the wrong
ones by the first token whose coarse label differs from the gold. Both libraries come out within a point of
each other, and each classes' count is in `benchmarks/suite/v1/MANIFEST.md`. Building names are not in the
suite: every record with one was wrong for both libraries, because a bare NAD `Building` after the street
is not how people write one, so its gold labels are doubtful. Labels doorplate does not model (a recipient
line, a house-number prefix) make "all records" and "shared labels" differ by about 1 point for doorplate;
that is why both figures are reported. A trailing `USA` is not an error for doorplate: it drops the word on
purpose and raises `country_ignored`.
