# Roadmap

What is planned, what depends on what, and what is deliberately not planned.
`doorplate` 0.3.1 is an alpha. Priorities follow the data people bring: the more real,
messy addresses it sees, the sooner the items below that need them can happen. To send
some, see [Sharing messy data](../CONTRIBUTING.md#sharing-messy-data).

## Stability while it is an alpha

- **Keys.** The match key is versioned (`k2:`) and each version is a contract
  ([`key-format.md`](key-format.md)), but expect new versions. A parser fix that changes
  what an input produces changes its key, and that needs a new version, so `k2:` and later
  are likely as the parser improves. Store the version prefix with the keys.
- **API and warning codes.** Names may change before 1.0, with a note in the changelog.
- **Accuracy and speed** are measured on a few datasets ([`benchmarks.md`](benchmarks.md))
  and are not guaranteed for yours.

## Planned

One release, 0.4.0, in two phases (decided 2026-10-23, issue #138; the `k3`, first planned as 0.5.0, is folded in
because the project has no users and the foundation went quickly). The rules for the labels, the milestones and the
order are in [`backlog.md`](backlog.md). There is no 0.3.2: with no users, a release is not made for a minor fix (a
0.3.x patch needs a very good reason, see [`backlog.md`](backlog.md)).

### 0.4.0, phase 1: the foundation (done; the key stays `k2`)

The architecture and the breaking cleanup, done once, so the core is close to final, with no parsing changes.
It ends at the **checkpoint**: a row-by-row key comparison with 0.3.1 over the large sources shows zero differences,
and those keys are frozen as the baseline for phase 2. What was done (#138):

- **Profiling** first (#90), then the speed work it found: about 38,400 to 50,300 addresses per second on the
  benchmark mix and 197 to 103 allocations per parse (#147, #148, #156; `docs/benchmarks.md`, "Profile").
- **State data:** the Florida data folded into the core as built-in state data, dropping the `state-fl` Cargo
  feature and renaming `data/packs/` to `data/states/` (#101); the state data version in the output (#7).
- **An extension-ready core** (#137): everything the tagger reads goes through `Lexicons`, and the layer interface
  is decided (`docs/how-it-works.md`), so the custom layer (#3) is a loader later.
- **API cleanup:** the reserved `confidence` field removed (#136), `parse_tokens` cut like usaddress (#78: the
  emitter, not the parser, so no key changes), and an audit of every public name (#135, `docs/api-surface.md`).

### 0.4.0, phase 2: the `k3`

The checkpoint passed on 2026-10-23. Phase 2 is the rules below, cut together; the list is closed (no new rules are
sought: [`backlog.md`](backlog.md), "Scope of phase 2"). The process and what a `k3` needs are in [`key-format.md`](key-format.md) ("Changing the key"). Each change needs a
source and evidence. The order is in #138. `k2` started with 0.3.0; the route-number and box rules are in
[`key-format.md`](key-format.md).

- **Warnings that say how far to trust a parse** (#102): a table of how reliable each warning is, measured
  on labeled data, and named warnings where the parser knows it is guessing, starting with a lone letter after
  the house number (`123 A MAIN ST`).
- **Line-2 diagnostics** (#45): say when a second line is skipped as a copy, merged into the street or kept as a
  building name; and the `%` care-of line leaving a copy or a number-led name unparsed (#126).
- **A county written as the city** (#113), and a `VILLAGE OF` prefix (#68).
- **From the first review of real rows (#125):** care-of text welded to the street (#127); units left in the street
  name (#128); spelled-out numbers (#129); lines with no street (#130); floor forms (#114).
- **From the survey of #131:** misspelled `PO BOX` words (#165) and a department name read as a unit (#166). The rest
  of #131 (campus boxes, text after the suffix) is in Later.
- **Misparses found since:** a word split before a trailing `CT`/`WY`/`KY`/`MT` suffix (#143), `BAY` read as a unit
  (#144), `LOOP` plus a number read as a route (#145).
- **Number forms:** a letter after a hyphenated house number (#100); a spaced letter after a rural route box (#95);
  Queens-style numbers and their unhyphenated twins keyed the same (#109).
- **`CR` and `CTY`** read as CIRCLE and COUNTY nationally, not only in Florida (#108), and the Florida data's
  scoped readings applied on pre-split input (#110).

### Later, waiting on data or demand

- **State-dependent rules and the reading that feeds them** (moved out of the 0.4.0 cut on 2026-10-23 to keep phase 2
  to the rules already listed): state road conventions such as Texas `RR`, `PR 462` and county road names (#8),
  Florida place gaps (#11), the geocode benchmark's place-name gap (#29), Puerto Rico and the uncited parts of Pub 28
  (#92), with the per-state counts that decide them (#53); `CMR` only if a real case shows up (#77, decided: left out).
- **Tooling that finds new things** (Tooling milestone): the review tool's comparison mode and second source (#132),
  less noise in the harness's scorers (#112). Built when a listed rule needs them.

- **A custom layer** (#3): a way to add your own spellings, places, ZIPs and state-scoped readings
  without editing the shipped tables, loaded at run time, validated on load, deterministic, and
  reported in the output so stored keys can be tied to the layer in use. Today the tables are fixed
  at compile time, and a misparse is fixed by reporting it. The design is settled; it waits for real
  examples of what people need to add (a local community the place list lacks, a street spelling).
- **State data beyond Florida:** a state's data starts from real data for that state (#7 adds the
  state data version to the output and a golden corpus per state in CI). Candidates: `RR` as Ranch
  Road in Texas, `PR 462`, county road names such as `LEE ROAD 2004`, and Puerto Rico urbanizations (#8).
- **More shapes and rules.** Known gaps that are not tied to a state: named buildings without a
  building word (`THE GARRETT`, `UPTOWN SQUARE`); highway modifiers before a city on one line
  (`NORTH HIGHWAY 71 BUSINESS LOWELL`); a comma after a directional (`3324 N, ANDREWS AVE`); a PO box
  on line 2 beside a street with no number; a unit followed by business words (`STE 903 BLU SPA`);
  and `possibly_truncated` firing on some complete units.
- **A columnar or Arrow result for DataFrames** (#24), after profiling: reading attributes from Python objects
  is most of the time in a pandas or Polars pipeline. A Polars expression namespace only if there is demand.
  Done so far: `to_display()`, `to_long()` and `parse_fields_many`.
- **A documentation site** (#107), once the docs stop moving, and a second post comparing with usaddress (#88).
- **usaddress compatibility** (#9, decided): the address-structure labels (#35) and a drop-in module
  (#36) proceed when someone needs them. Recipient and name lines, landmarks and street corners stay
  out of scope; that text goes to `unparsed`.
- **Tooling, never in a release** (milestone `Tooling`): the review tool's v2, with a comparison mode against
  usaddress (#132), an anonymizing tool for sharing messy data (#105), harness fixes (#112) and a coverage badge
  (#121).
- **Data and benchmarks:** a benchmark built from a national address source rendered in several styles
  and compared per state and per shape; a cleaner blind test, a hand-labeled sample of real messy data
  in the shapes people actually have; per-state street-pattern counts to decide the state rules (#53);
  and more of the `parse` slowdown (about 8% of an earlier build's speed is still spread across
  allocation in the place keys and `Vec` growth).

## Not planned

- **Address validation or deliverability.** That needs postal-service-certified data.
- **Geocoding, fuzzy matching, address correction.**
- **International addresses.**
- **A machine-learned model.** The parser is rules plus place data on purpose, so a fix is a
  rule or a line of data, and the same input gives the same output.
