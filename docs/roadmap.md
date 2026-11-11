# Roadmap

What is planned, what depends on what, and what is deliberately not planned.
`doorplate` 0.5.1 is an alpha. Priorities follow the data people bring: the more real,
messy addresses it sees, the sooner the items below that need them can happen. To send
some, see [Sharing messy data](../CONTRIBUTING.md#sharing-messy-data).

**Last reviewed 2026-11-11, against the issues up to #617 (the major review of the away run, #586, step B8).** The rules for the labels, the milestones and the order are in
[`backlog.md`](backlog.md); the open trackers are #402 (0.5.x, in order), #416 (0.6.0, the `k5`) and #417 (decided against).

## Stability while it is an alpha

- **Keys.** The match key is versioned (`k4:`) and each version is a contract
  ([`key-format.md`](key-format.md)), but expect new versions. A parser fix that changes
  what an input produces changes its key, and that needs a new version, so `k4:` and later
  are likely as the parser improves. Store the version prefix with the keys.
- **API and warning codes.** Names may change before 1.0, with a note in the changelog.
- **Accuracy and speed** are measured on a few datasets ([`benchmarks.md`](benchmarks.md))
  and are not guaranteed for yours. How the figures moved from 0.3.1 to `main`, and the release tolerance, are on
  [`version-comparison.md`](version-comparison.md).

## Released

**0.5.0 (2026-10-31)**, the `k4` (tracker #201): the parser rules that change keys, cut together and measured row by row. Keys changed: store the `k4:`
prefix and re-parse to re-key. The rules came from four reviews of real rows (the IRS extract, the FMCSA carriers, the FCC amateur licensees, the NY
corporations and the Boston, NC voter and campus-box queues): a name or recipient text around the street, boxes and routes written oddly or glued,
units left in the street name, a letter after the house number, a half written without its slash, a repeated line, care-of text in front, spelled-out
house numbers, a nearly right ZIP, and the warnings `repeated_text`, `zip_repaired` and `non_us_address`. What changed and the measured counts per rule
are in [`CHANGELOG.md`](../CHANGELOG.md); the `k4` against the frozen `k3` keys of 0.4.0 changes 127,869 of 36,920,703 keys (0.35%).

The release was proved with probes and a full run: one probe per open issue (35 of 35 open rule issues have a probe or a written reason), counted on 0.4.1 and
on the cut over 146.6 million Netsyms rows and the seven large sources; the suite's whole-address score rises from 92.3% to 93.4%, the Florida one-line
check and the geocode `city_diff` do not move, and `parse` was 8 to 12% slower ([`benchmarks.md`](benchmarks.md), "0.4.1 to 0.5.0"); the 0.5.1 round below won that back.

**0.4.1 (2026-10-28)**, decided 2026-10-27: everything done in 0.4.x, with **no key change and no parse-rule change** (a custom layer changes parsing only when one is loaded): tooling, documentation and extensibility (tracker #200).

- **Extensibility:** the custom layer (#3: your own spellings, words, places, ZIPs and state-scoped readings, from the command line, Python and
  Rust; [`custom-layers.md`](custom-layers.md)), `doorplate.compat`, a usaddress-shaped module (#36), and faster `parse_column` and DuckDB
  columns (#24, built in Rust).
- **Sharing messy data:** `doorplate anonymize`, `Anonymizer` in Python and Rust (#105, [`anonymizing.md`](anonymizing.md)).
- **Tooling:** the quieter harness scorers (#112, with the figures regenerated in #220), per-state street-pattern counts (#53), review tool v2: the
  comparison mode against usaddress (#132) and its helpers (#222, items 1 to 3), and a flag when the review page's parser is stale (#246).
- **Documentation:** the site at <https://doorplate.readthedocs.io/> with a Python and a command-line reference (#107, #229); the READMEs are
  short and link to the guides; the Python reference describes `main` until this release is out.
- **Coverage:** tests of the reachable branches, and a written account of what stays uncovered (#211, [`repository.md`](repository.md)).

Checked against the frozen 0.4.0 keys row by row (36,920,000 rows, seven sources): no key and no warning differs (#255). What follows the tag:
versions on Read the Docs and the Python reference's note (#252). #233 (the MkDocs and Material end of life on 2027-05-05) does not gate anything.

**0.4.0 (2026-10-25)**, one release in two phases (decided 2026-10-23, issue #138): the foundation, then the `k3`. The state data
is folded into the core, the lexicon is extension-ready (#137), the API was cleaned up and audited (#135, [`api-surface.md`](api-surface.md)),
the allocation work made parsing faster (#147, #148, #156), and the `k3` key and the parser rules behind it were cut together
(warnings that say how far to trust a parse, #102; line-2 diagnostics, #45; a county written as the city, #113; and the misparses of
the first review of real rows, #125 and its issues #126 to #130, #114, #143 to #145, #165, #166). What changed, and when keys
changed, is in [`CHANGELOG.md`](../CHANGELOG.md) and [`key-format.md`](key-format.md). It stays an alpha: the `k3` is new and has only
been checked on the project's own data, so a `k4` is likely.

## Next: 0.5.x, tooling, docs and performance

0.5.x has no key changes (`key_diff.py` against `local-data/keycompare/k4-cut` must show 0 differences) and is ordered by tracker #402.

- **Performance (done, released in 0.5.1):** the engine takes about half the time per parse of 0.4.1 (31.1 to 15.6 µs on one pinned CPU;
  85,900 instructions per parse against 157,500), with every key, warning and unit field unchanged. The figures, what was done and the leads
  for a later round are on [`speed-and-size.md`](speed-and-size.md); #418 holds the leads in Later.
- **Docs (done):** the edit pass (#399: current figures, no build history in the user pages) and the wheel-size correction (#277).
- **Release:** the 0.5.1 checklist is #453 (released with the references PR).
- **Tooling:** MessyStreets findings (#323) are in the Tooling milestone. The Try page work (#434: a guided path, a sample CSV, an anonymize mode) is in review and ships with the site, not a crate release.
- **Parse rules** found since the list closed are in **Later** unless they are measured at P2 or above: those are in 0.6.0 below.

## Next: 0.6.0, the `k5`

The next key-changing release (tracker #416). It opens with the rerank of every probed issue by rows affected (new cut-offs, recorded on #416), then the
rules below, each measured row by row against the frozen `k4` keys with `key_diff.py`. The list comes from the probe precision queues (about half
of 41 are analyzed; the rest and the final rescore may move issues in or out) and the re-probes of 2026-11-03. Planned order, with the measured rows:

1. A compass word with `KY` or `TR` and a number (#388): 28 of 30 wrong, about 5,650 rows. Merged.
   A half written without its slash before a direction letter (#387): 29 of 30 wrong, about 4,330 rows. Merged.
2. A campus box with two plain words, a route word with no route number and a misspelled post office, one rule (#384, widening the earlier campus-box rule): about 5,560 rows. Merged.
3. Missing-value strings in the city, state or ZIP (#419), with a small city-only placeholder list (the words that only ever stand in for a city). Merged.
4. A care-of line that ends mid-street gets a warning, and `C O` without a slash (#473, narrowed; about 1,000 rows). Merged.
5. A letter A to D after the house number is usually a unit (#487, reverses an earlier rule). Follow-up from the queues: a letter before a suffix word that is not the street's last suffix is a unit, and a letter before AND stays in the street (#466). Merged.
6. Unit forms: unit text with no designator on line 2 (#320, first part: a number before a designator word and a directional street name), words Pub 28 does not list as designators (the first part, condo and site words on line 2, merged; the rest is in Later), a unit between the house number and the street (#296, merged). Position words and `ADU` on line 2 are a unit type (#545, merged). A road number written before the road type (`331 5659 PRIVATE ROAD`, `2210 3315 FM RD`) stays in the street name (#542, merged; the issue stays open to close with the milestone, and the FM form is in Later). Merged.
   A second number after the house number (#313, #501, #502): a Queens or Hawaii pair is the number, a five-digit number written in two is joined, a number before an ordinal street is a unit. Merged. The same for any street (#544): a second number of three to five digits after the house number is the unit, a repeated number is dropped, and `PRIMARY`, `SECONDARY`, `DUPL` and `DUPLEX` are not units after a number on line 2. Merged.
7. The short curated place list of neighborhood mail names (#486): about a dozen names, about 0.01% of rows. Merged.
8. Found in the major review of the away run (the major review tracker, 2026-11-10; counts are over the 289M-row scan unless named, rows are matches times the review precision, an estimate; the denominator of each is on its issue):
   - P1: a line-2 digit run is a placeholder (#592, about 29,600; built), a `<NAME> ROAD n` road number is a unit in a closed list of states (#593, about 765,000, rough; built), a ZIP field of `0` (#605, 105,710 full NAD rows; `version:O`), a bare number before a unit on line 2 (#607, 319,542 full NAD rows), line 1 that ends in the row's own state and ZIP (#614, 72,119 full Netsyms rows).
   - P2: words after a street suffix (#589, about 6,500), a range-like second number (#590, about 7,650), a five-digit join outside NYC, Hawaii and Massachusetts (#591, about 7,300), `ROAD` plus a letter before the city (#600, about 24,200; built), a ZIP+4 cut to seven digits (#606, 15,136 full NAD rows), `UNITED STATES HIGHWAY` after a word or with a route pair (#608, 10,595 full NAD rows), a hyphen beside the second number (#612, 2,900 rows whose reading changes). Not a rule: the `missing_city` docs (#610).

Also in the milestone, not rules: the decisions-at-risk work: row counts for the deliberate decisions, a re-grade of the reviewed cards and five new queues (#524, done). Also in the milestone: the full docs review and readability pass before the release (#528) and the residual unit before the street (#529).
Puerto Rico street-first forms wait for the Puerto Rico research issue. Nothing here changes a key before the release is cut.

## Waiting, on data or demand

- **Later** (the milestone): wanted or known, none at the P2 line, none scheduled. By kind:
  - *From the major review (#586), all P3 by the full scan:* a lettered street before its suffix (#594), `OLD 25A` (#595), a lettered PO drawer (#598), a ZIP+4 written with `*` (#599), a spelled-number line with commas (#601), `# APT` after the street (#602); the one-line cuts (#596, #597) are not sized on field-form data; two numbers before the street name drop `multiple_addresses` (#617, P3 provisional: card counts only, remeasure on the full sources).
  - *Units:* two suffix words then a unit (#243), a unit value that is a suffix code (#272), `SUT` and `STU` (#289), two units joined by `&` (#290), a floor in parentheses (#291), a
    unit of more than one part (#294), a building word after a route (#295), a `PIER` as a last word (#327), a bare number or letter after a street with no suffix (#345), a name and a floor on line 1 (#351),
    a word and a number after a suffix (#375), NAD unit misses (#238), a unit marker after the street (#471), a building name after the street (#495, done), a designator with no value before
    the street name (#498), a unit repeated as `# N` on line 2 (#499).
  - *Boxes and routes:* glued box and route words (#304), a route after a street (#307), `PO BOX` with a placeholder on line 2 (#358), a box followed by street words (#366).
  - *House numbers and street names:* `SO` for `SOUTH` (#269), two house numbers joined by `&` (#274), a spaced hyphen between a building and a street (#310) or after a suffix (#341), grid numbers (#311),
    a letter before the house number (#312), a letter then a direction then a name (#360),
    `NO` for north (#470).
  - *State and road forms:* Texas `PR` roads (#314), `AND` between two highways (#317); Puerto Rico (#318, #319, the epic #332, #92).
  - *City field and line 2:* a unit or a box in the city field (#244), the city field holds the state (#357), a `CO` prefix with a fuller name on line 2 (#367),
    a person or business on line 2 after a real street (#472), a care-of or attention line with a name and no street (#509, done), a non-Latin city or country (#469), a city that starts with a state name (#480), a region phrase written as the state (#482),
    boilerplate before the street (#483).
  - *Review data and tooling:* the review tool's deferred sharing helpers (#222, item 4), the tracker of what has been hand-reviewed and the queues to come (#225), comparing with libpostal (#215), the Web Data Commons answer on research use (#395), larger MessyStreets tiers (#403).
  - *Added since the list closed:* a ZIP+4 written with a space (#519), a number and a word on line 2 under a highway or a street with no suffix word (#531), the line-2 unit rules on a comma-separated second segment (#534), `STAR RT` as a rural route (#538), a place plus a repeated `NEW YORK` in the city (#553), a unit at the end of line 1 with a stray word on line 2 (#558), a spelled-out number alone on line 2 (#559), a thousands comma in a house number (#560), the FM number before the road type (#316), the rest of #321.
  - *Parsing ideas:* a street line that already ends in the city, state and ZIP (#397), repeated state, a county-only segment and `USA` after the ZIP (#435). An opening parenthesis with no closing one that loses the ZIP in the one-line parse (#516); parentheses as the edge of a segment (#291).
  - *Data, API, docs and speed:* Florida pack gaps (#11), more state data (#213), the address-structure labels usaddress has (#35), Canadian addresses (#203), the usaddress comparison post (#88), the examples notebook as a page (#253),
    the docs site move off Material for MkDocs (#233), further performance leads (#418), the post on how rule changes are tested (#491, 0.6.x), and an architecture idea, shape-first parsing (#490).
- **0.6.x:** the post on how rule and performance changes are tested (#491) moved out of 0.6.0 on 2026-11-05: revisit it with 0.6.1, the speed and performance release, when the release-cycle chart spans more releases and there is another round of improvements to show.
- **Tooling** (never shipped, never closed): evaluating MessyStreets (#323); the Try page (#434) is in review; the ny-corps CEO ingest (#609, from the major review); the version-comparison follow-ups, per-rule progression and regression scans (#566); the parser showdown repository (#616); benchmarks from a look at fastaddress (#511: a warning-versus-error AUC, a speed column, about 540 labeled messy rows).
- **Major review follow-ups** (#586, milestone *major review*): the geocode benchmark down 0.1 to 0.2 points since v0.3.1 (#581, answered by `version-comparison.md`; closes with its PR) and the 194,045 warning changes in the NAD sample from PR 494 (#583, answered by B1 and B5; open until the owner closes it).
- **More shapes and rules** not tied to a state, known and not yet an issue: named buildings without a building word (`THE GARRETT`, `UPTOWN SQUARE`);
  highway modifiers before a city on one line
  (`NORTH HIGHWAY 71 BUSINESS LOWELL`); a comma after a directional (`3324 N, ANDREWS AVE`); a PO box on line 2 beside a street with no number; a unit
  followed by business words (`STE 903 BLU SPA`); and `possibly_truncated` firing on some complete units.
- **A public Arrow result and a Polars expression namespace** only if there is demand (#24 is closed: the helpers build their columns in Rust).
- **usaddress compatibility** (#9, decided): the drop-in module is done (#36); the labels in #35 proceed when someone needs them. Recipient and name
  lines, landmarks and street corners stay out of scope; that text goes to `unparsed`.
- **Data and benchmarks:** a benchmark built from a national address source rendered in several styles and compared per state and per shape; a
  hand-labeled sample of real messy data in the shapes people actually have.

## Researched, but not supported

International addresses are **not supported** (see below). Two questions about them are being **researched**, not planned: Canadian addresses, as country
support, a layer or a separate crate (#203), and a comparison with libpostal, which is international, with the question of whether a libpostal-shaped
output is worth adding (#215; the written comparison, [`libpostal-compat.md`](libpostal-compat.md), is done, the measurements are not). A result would become its own issue; neither changes the list above.

## Not planned

- **Address validation or deliverability.** That needs postal-service-certified data.
- **Geocoding, fuzzy matching, address correction.**
- **International addresses.**
- **A machine-learned model.** The parser is rules plus place data on purpose, so a fix is a
  rule or a line of data, and the same input gives the same output.
