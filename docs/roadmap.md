# Roadmap

What is planned, what depends on what, and what is deliberately not planned.
`doorplate` 0.3.0 is an alpha. Priorities follow the data people bring: the more real,
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

Priorities come from a review of the open issues (issue #103). The rule for versions: a change
that does not alter a key ships in a 0.3.x patch; changes that alter keys or break the API are
held and batched into one 0.4.0, because every `k3` re-keys stored keys and every breaking
change costs a version.

### Next, in 0.3.x patches (no key change)

- **Warnings that say how far to trust a parse** (#102): a table of how reliable each warning is,
  measured on labeled data with `tools/harness/label_score.py`, and named warnings where the parser
  knows it is guessing, starting with a lone letter after the house number (`123 A MAIN ST`).
- **Line-2 diagnostics** (#45): say when a second line is skipped as a copy, merged into the
  street or kept as a building name.
- **Provenance** (#85): `doorplate --version`, and the library version in the command's JSON.
- **Profiling** (#90): a time-boxed look at where the time and memory go, and any easy gains that
  change no output.
- **A columnar or Arrow result for DataFrames** (#24), after profiling: reading attributes from
  Python objects is most of the time in a pandas or Polars pipeline. A Polars expression namespace
  only if there is demand. Done so far: `to_display()`, `to_long()` and `parse_fields_many`.
- **An anonymizing tool** (#105) for sharing messy data without sharing the data.

### 0.4.0: the `k3` and the breaking cleanup

Held on purpose and cut together: the held list is the `version:K` label on the issues, and the
process and what a `k3` needs are in [`key-format.md`](key-format.md) ("Changing the key"). Each
change needs a source and evidence. `k2` started with 0.3.0; the route-number and box rules are in
[`key-format.md`](key-format.md).

- **Key-affecting rules:** `CR` read as CIRCLE and `CTY HWY` as COUNTY HIGHWAY in every state (today
  only in Florida); a letter after a hyphenated house number (#100); a spaced letter after a rural
  route box (#95); Queens-style numbers and their unhyphenated twins keyed the same; Puerto Rico
  shapes (#92); state-specific road conventions such as Texas `RR` and county road names (#8);
  Florida place gaps (#11); the geocode benchmark's place-name gap (#29); and `CMR` only if a real
  case shows up (#77, decided: left out for now).
- **Breaking cleanup:** fold the Florida pack into the core as built-in state data, which drops the
  `state-fl` Cargo feature and renames `data/packs/` to `data/states/` (#101), and remove the reserved
  `confidence` field (#102).

### Later, waiting on data or demand

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
- **usaddress compatibility** (#9, decided): the address-structure labels (#35) and a drop-in module
  (#36) proceed when someone needs them. Recipient and name lines, landmarks and street corners stay
  out of scope; that text goes to `unparsed`.
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
