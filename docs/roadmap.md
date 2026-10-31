# Roadmap

What is planned, what depends on what, and what is deliberately not planned.
`doorplate` 0.4.1 is an alpha. Priorities follow the data people bring: the more real,
messy addresses it sees, the sooner the items below that need them can happen. To send
some, see [Sharing messy data](../CONTRIBUTING.md#sharing-messy-data).

**Last reviewed 2026-10-28, against the issues up to #277.** The rules for the labels, the milestones and the order are in
[`backlog.md`](backlog.md); the two trackers are #200 (0.4.x) and #201 (0.5.0, the `k4`).

## Stability while it is an alpha

- **Keys.** The match key is versioned (`k4:`) and each version is a contract
  ([`key-format.md`](key-format.md)), but expect new versions. A parser fix that changes
  what an input produces changes its key, and that needs a new version, so `k4:` and later
  are likely as the parser improves. Store the version prefix with the keys.
- **API and warning codes.** Names may change before 1.0, with a note in the changelog.
- **Accuracy and speed** are measured on a few datasets ([`benchmarks.md`](benchmarks.md))
  and are not guaranteed for yours.

## Released

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

## Next: 0.5.0, the `k4` (tracker #201)

The key-changing rules, cut together once the 0.4.x tooling has produced evidence (it has: three reviews of real rows: #125, closed, #245 and #225). Nothing is
scheduled; each rule needs a source, an invented corpus case, and a row-by-row measurement against the frozen `k3` keys.

- **Research first** (it may produce more issues, or none): campus boxes, box and route typos and recipient text after the suffix (#131); spelled-out
  building numbers (#221); more state data, and whether it is needed (#213); the Virginia SCC and Boston SAM data now in `local-data/` (its triage, #205, is closed; the ingest and review queues are in #225).
- **From the first review of real rows** (#125, IRS extract): done in 0.4.0, except what #131 holds.
- **From the second review** (#245, the FMCSA carriers against usaddress; 150 of 150 rows answered):
  - **A repeated string** (#236, P2): a line written twice, or a tail that repeats the city, state and ZIP, about 287 distinct strings in the sample. The first step is a
    warning (`version:O`, no key change; it could be added before the `k4`), then a rule for the repeated tail (`version:K`).
  - **Box and route forms** that are not read, glued words, `PO` with no `BOX`, `RUR RTE` (#248); a BOX beside a street (#240);
    unit forms left in the street name (#241: the glued floor `3FL` is done; the rest are one issue each, #288 to #296); grid-style house numbers (#242, which may be a warning rather than a rule: a leading letter is ambiguous); two suffix words and then a unit (#243); a building name before the house number (#281).
- **From the third review** (#225, the FCC amateur licensees against usaddress; 150 of 150 rows answered): care-of text at the front with no separator takes the whole line,
  key `None` and no warning (#259; a warning could come before the `k4`); a `PO BOX` on line 2 whose number equals the ZIP loses its number and leaves a stray `PO BOX` (#260, `version:O`,
  no key change); a spaced hyphen after the suffix keeps the unit or place in the street name (#261). The round adds evidence to #8, #92, #236, #240, #242, #243 and #248
  (a letter direction before a single number, route and box forms, Puerto Rico street-first forms, repeated text). The NY corporations queue (reviewed, 150 rows) adds the largest single group of the three rounds: a comma on line 1 that hides the street on line 2, 11.8% of its rows (#268, P1); also `SO` for `SOUTH` (#269), a decision on `46 A LINDEN AVE` (#270), a unit value that is also a suffix code such as `SUITE LA` (#272), placeholder text as the street (#273) and two house numbers joined by `&` (#274), with evidence on #221, #236, #240, #241, #242, #243, #244 and #261. The TX licensing queue (reviewed, 150 rows) adds a ZIP with its leading zero or its ZIP+4 cut short that makes the whole last line unplaced, 8.9% of its rows (#275, P1), and a unit with a second part on line 1 that hides the street on line 2 (#276), with evidence on #8, #236, #241, #242, #244, #248, #270 and #274.
- **From harness counts:** NAD unit text left in `unparsed_remainder` (#238); two bare numbers on line 2 glued into one unit (#196); a bare `BAY` with no number
  (#193, a warning, rides along).
- **State-dependent rules and the reading that feeds them:** Texas `RR`, `PR 462` and county road names (#8), Florida place gaps (#11), the
  [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark)'s place-name gap (#29), Puerto Rico and the uncited parts of Pub 28 (#92; the round-2
  review adds the `URB` shape).

## Waiting, on data or demand

- **Later** (the milestone): the examples notebook as a page on the site (#253); the usaddress comparison post (#88); the address-structure labels usaddress has (#35); research on Canadian addresses (#203);
  a unit or a box in the city field (#244, a warning); a half written without its slash (#247); the 0.4.1 size figures in the docs and the announcement (#277).
- **Tooling** (never shipped, never closed): the review tool's deferred sharing helpers (#222, item 4); the tracker of what has been hand-reviewed and the
  queues to come (#225; the FCC queue is reviewed, its findings are #259 to #261); comparing with libpostal (#215).
- **More shapes and rules** not tied to a state, known and not yet an issue: named buildings without a building word (`THE GARRETT`, `UPTOWN SQUARE`);
  highway modifiers before a city on one line
  (`NORTH HIGHWAY 71 BUSINESS LOWELL`); a comma after a directional (`3324 N, ANDREWS AVE`); a PO box on line 2 beside a street with no number; a unit
  followed by business words (`STE 903 BLU SPA`); and `possibly_truncated` firing on some complete units.
- **A public Arrow result and a Polars expression namespace** only if there is demand (#24 is closed: the helpers build their columns in Rust).
- **usaddress compatibility** (#9, decided): the drop-in module is done (#36); the labels in #35 proceed when someone needs them. Recipient and name
  lines, landmarks and street corners stay out of scope; that text goes to `unparsed`.
- **Data and benchmarks:** a benchmark built from a national address source rendered in several styles and compared per state and per shape; a
  hand-labeled sample of real messy data in the shapes people actually have; and more of the `parse` slowdown (about 8% of an earlier build's
  speed is still spread across allocation in the place keys and `Vec` growth).

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
