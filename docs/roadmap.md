# Roadmap

What is planned, what depends on what, and what is deliberately not planned.
`doorplate` 0.5.0 is an alpha. Priorities follow the data people bring: the more real,
messy addresses it sees, the sooner the items below that need them can happen. To send
some, see [Sharing messy data](../CONTRIBUTING.md#sharing-messy-data).

**Last reviewed 2026-11-01, against the issues up to #451.** The rules for the labels, the milestones and the order are in
[`backlog.md`](backlog.md); the open trackers are #402 (0.5.x, in order), #416 (0.6.0, the `k5`) and #417 (decided against).

## Stability while it is an alpha

- **Keys.** The match key is versioned (`k4:`) and each version is a contract
  ([`key-format.md`](key-format.md)), but expect new versions. A parser fix that changes
  what an input produces changes its key, and that needs a new version, so `k4:` and later
  are likely as the parser improves. Store the version prefix with the keys.
- **API and warning codes.** Names may change before 1.0, with a note in the changelog.
- **Accuracy and speed** are measured on a few datasets ([`benchmarks.md`](benchmarks.md))
  and are not guaranteed for yours.

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

- **Performance (done on `main`, 0.5.1-dev):** the engine takes about half the time per parse of 0.4.1 (31.1 to 15.6 µs on one pinned CPU;
  85,900 instructions per parse against 157,500), with every key, warning and unit field unchanged. The figures, what was done and the leads
  for a later round are on [`speed-and-size.md`](speed-and-size.md); #418 holds the leads in Later.
- **Docs (done):** the edit pass (#399: current figures, no build history in the user pages) and the wheel-size correction (#277).
- **Release:** the 0.5.1 checklist is #453.
- **Tooling:** MessyStreets findings (#323) and the Try page (#434) are in the Tooling milestone.
- **Parse rules** found since the list closed are in **Later** (each is measured, none reached the P2 line). The next key version is `k5`, planned
  for an eventual 0.6.0 release (#416); nothing is scheduled for it.

## Waiting, on data or demand

- **Later** (the milestone): wanted or known, none at the P2 line, none scheduled. By kind:
  - *Units:* two suffix words then a unit (#243), a unit value that is a suffix code (#272), `SUT` and `STU` (#289), two units joined by `&` (#290), a floor in parentheses (#291), a
    unit of more than one part (#294), a building word after a route (#295), a unit between the house number and the street name (#296), unit text with no designator on line 2 (#320),
    words Pub 28 does not list as designators (#321), `PIER` as a last word (#327), a bare number or letter after a street with no suffix (#345), a name and a floor on line 1 (#351),
    a word and a number after a suffix (#375), a campus box with two plain words (#384), NAD unit misses (#238), a bare `BAY` (#193).
  - *Boxes and routes:* glued box and route words (#304), a route after a street (#307), `PO BOX` with a placeholder on line 2 (#358), a box followed by street words (#366).
  - *House numbers and street names:* `SO` for `SOUTH` (#269), two house numbers joined by `&` (#274), a spaced hyphen between a building and a street (#310) or after a suffix (#341), grid numbers (#311),
    a letter before the house number (#312), Queens and Hawaii numbers written with a space (#313), a letter then a direction then a name (#360), a lost fraction before a lone letter (#387),
    a compass word with `KY` or `TR` (#388), and the letter after a house number (#391, a review queue).
  - *State and road forms:* Texas `PR` roads (#314), Alabama `<NAME> ROAD <number>` (#315), the FM number before the road type (#316), `AND` between two highways (#317); Puerto Rico (#318, #319, the epic #332, #92).
  - *City field and line 2:* a unit or a box in the city field (#244), the city field holds the state (#357), a `CO` prefix with a fuller name on line 2 (#367).
  - *Review data and tooling:* the review tool's deferred sharing helpers (#222, item 4), the tracker of what has been hand-reviewed and the queues to come (#225), comparing with libpostal (#215), the Web Data Commons answer on research use (#395), larger MessyStreets tiers (#403).
  - *Parsing ideas:* the tagger's known-word chains (#410), a street line that already ends in the city, state and ZIP (#397), missing-value strings in the city, state or ZIP (#419), repeated state, a county-only segment and `USA` after the ZIP (#435).
  - *Data, API, docs and speed:* Florida pack gaps (#11), more state data (#213), the address-structure labels usaddress has (#35), Canadian addresses (#203), the usaddress comparison post (#88), the examples notebook as a page (#253),
    the docs site move off Material for MkDocs (#233), and further performance leads (#418).
- **Tooling** (never shipped, never closed): evaluating MessyStreets (#323) and the Try page (#434).
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
output is worth adding (#215). A result would become its own issue; neither changes the list above.

## Not planned

- **Address validation or deliverability.** That needs postal-service-certified data.
- **Geocoding, fuzzy matching, address correction.**
- **International addresses.**
- **A machine-learned model.** The parser is rules plus place data on purpose, so a fix is a
  rule or a line of data, and the same input gives the same output.
