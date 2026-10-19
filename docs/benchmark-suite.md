# The benchmark suite (specification)

A fixed, versioned set of labeled addresses that ships in the repository, and one runner
that scores doorplate and usaddress on it under a fixed, modest resource profile. This page
is the specification. The suite is built in the steps under "Status" below; the plan and
the decisions behind it are in issue #75.

This library formats and parses; it does not validate deliverability. Nothing in the suite
says an address exists or can receive mail, and its rows are made so that they are not real
address points (see "Anonymization").

## What it is for, and what it is not

- **A benchmark anyone can rerun**, without the private data in `local-data/` (the Netsyms
  database, the geocode benchmark, the Florida exports) and on ordinary hardware.
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
 "stratum": "natural", "style": "mixed-commas", "type": "street", "state": "IL",
 "source": "nad", "tags": []}
```

- `input`: one string, the only input both parsers get.
- `tokens`: the gold labels, in usaddress's label set, assigned by the generator. A token
  with no letter or digit is not scored, as in `tools/compare/compare_usaddress.py`.
- `stratum`: `natural`, `hard` or `hand` (see "Composition").
- `style`: how the record was written (see "Styles").
- `type`: `street`, `po_box`, `rural`, `highway`, `military` or `general_delivery`.
- `source`: `nad`, `tiger`, `synthetic` (a shape NAD has no rows for, such as a PO box) or
  `hand`.
- `tags`: the blind-spot classes the record belongs to (see "The hard stratum"). Empty for
  most `natural` records.

`doorplate.jsonl.gz` has the same `id`, `stratum`, `type`, `state`, `source` and `tags`, and:

- `fields`: `{line1, line2, city, state, zip}`, the same record as `parse_fields` would get it.
- `inputs`: the record written in two to four styles, for the key-stability measure.
- `expect`: the components, named as in the golden corpus (`tests/corpus/README.md`), in
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
- **Building names are replaced** with invented ones of the same shape (`BLDG 4`, `NORTH TOWER`),
  since a provider's building value can hold a business or family name.
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
| `Building` | `BuildingName` (invented, above) |
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

The `natural` mix by address type and style is filled in from the local counts in step 2:

| Address type | Share of `natural` |
|---|---|
| Street, no unit | _to be measured_ |
| Street with a unit | _to be measured_ |
| PO box | _to be measured_ |
| Rural or highway-contract route | _to be measured_ |
| Military | _to be measured_ (floor 100) |
| General delivery | _to be measured_ (floor 50) |

### The hard stratum

One inventory, made the same way for both libraries (step 2): strings rendered from the
local sources in each style, both parsers run on them, and their errors sorted into classes by
one classifier. **Every class above 1 in 10,000 records in the local data gets its proportional
share of the 3,000, with a floor of 50.** Classes are not added or dropped by hand.

Classes already known, to be counted with the rest:

| Class | Library it is known for | Issue |
|---|---|---|
| A neighborhood or unincorporated place missing from the place list | doorplate | #29 |
| A named building with no building word | doorplate | #37 (E) |
| A trailing number in the street read as a unit | doorplate | #37 (F) |
| A highway modifier before the city on one line | doorplate | #10 |
| `VILLAGE OF` / `TOWN OF` / `CITY OF` before the city | doorplate | #68 |
| A label doorplate does not model (number prefix, premodifier, subaddress, intersection) | doorplate | #35 |
| _usaddress's classes_ | usaddress | measured in step 2 (its 88% on the geocode `dev` split shows they exist) |

The final table, with counts, goes in `MANIFEST.md`.

### Exclusions

The generator drops any record whose input string (whitespace collapsed, lowercased) appears in:

- usaddress's training files at the pinned commit (the fetcher in `tools/compare/training_overlap.py`)
- usaddress's test files (`tests/external/usaddress/`)
- the golden corpus (`tests/corpus/`) or the Pub 28 examples
- the geocode benchmark's splits

It also drops duplicates within the suite.

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
- usaddress is pinned (0.5.16 at the time of writing). The runner prints its version and
  scores `usaddress.parse`, so `RepeatedLabelError` cannot drop a record.

### doorplate-only track

- **Fields input**: `parse_fields` on `fields`, scored on the components in `expect`.
- **Standardized output**: the components in Pub 28 form, and the `to_usps()` lines.
- **Key stability**: the share of records whose `inputs` (the same record in several styles)
  all give the same `k2` key, and the share of keys shared by two different records.
- **Warnings**: of the records parsed wrong, the share that raised a warning; of those parsed
  right, the share that raised one.

## The resource profile

The reference profile is **4 logical CPUs and 8 GB of memory, on Linux**. It is what a
GitHub-hosted `ubuntu-latest` runner on a public repository has, and what an ordinary laptop has.
The runner applies it itself:

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

- `v1` is built once, audited, scored and published. It is never edited after that.
- Label errors found later are collected in an issue and fixed in `v2`. Both versions' scores
  are kept in `docs/benchmarks.md`, each with the version it came from.
- A new version is also needed when the usaddress pin moves or a source is replaced; the old
  version stays runnable.

## Status

Built in these steps (issue #75), each a small pull request or a local step:

1. **This specification**, with the data-policy change that lets anonymized NAD rows ship.
2. **The blind-spot inventory** (local, counts only): fills in the composition tables. No rule
   changes come from it.
3. **The generator**, `tools/benchsuite/build.py`, and the private twin.
4. **The label audit**: a random 500 records, plus every record the generator flags.
5. **The runner**, `benchmarks/suite.py`, with the profile and the CI job.
6. **`v1` frozen and scored**: figures in `docs/benchmarks.md` and the READMEs.
