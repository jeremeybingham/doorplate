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

### Warnings that say why

Making the warnings say how far to trust a parse (issue #102):

- a table of how reliable each warning is, measured on labeled data (the National Address
  Database sample, the NC voter snapshot) with `tools/harness/label_score.py`, so a reader
  knows which codes mean "wrong" and which mean nothing about the parse;
- named warnings where the parser knows it is guessing, starting with a lone letter after the
  house number (`123 A MAIN ST`: a number suffix or a street named `A MAIN`);
- removing the reserved `confidence` field, which is always `None`, in 0.4.0.

### Customization packs

A way to add your own spellings, places, ZIPs and state-scoped readings without editing
the shipped tables: an add-only layer in the state-pack format, loaded at run time,
validated on load, deterministic, and reported in the output so stored keys can be tied to
the layer in use. Today the tables are fixed at compile time, and a misparse is fixed by
reporting it. The design is settled; it waits for real examples of what people need to add
(a local community the place list lacks, a street spelling, a state-specific suffix).

### More state packs

Florida is the first curated pack. Another state's pack starts from real data for that
state. Known candidates: `RR` as Ranch Road in Texas, `PR 462` (a Texas private road or a
Puerto Rico road), county road names such as `LEE ROAD 2004`, Queens-style hyphenated house
numbers, and Puerto Rico urbanizations.

### More shapes and rules

Known gaps that are not tied to a state:

- named buildings without a building word (`THE GARRETT`, `UPTOWN SQUARE`);
- highway modifiers before a city on one line (`NORTH HIGHWAY 71 BUSINESS LOWELL`);
- a comma after a directional (`3324 N, ANDREWS AVE`);
- a PO box on line 2 beside a street with no number;
- a unit followed by business words (`STE 903 BLU SPA`);
- `possibly_truncated` firing on some complete units.

Whether to model more of what usaddress labels (recipient and name lines, landmarks,
street corners with cross-street fields) is open; today that text goes to `unparsed`.

### More output

- Done: `to_display()` and `to_long()` (display only, not Pub 28) and the batch call for
  pre-split fields (`parse_fields_many`).
- A columnar or Arrow result for DataFrames (issue #24): reading attributes from Python
  objects is most of the time in a pandas or Polars pipeline.
- A Polars expression namespace, if there is demand.

### The key

`k2` starts with 0.3.0 and collects the key-affecting changes found with the data on hand (the
plan and checklist are issue #44; the key drops leading zeros from route numbers and keeps them in box numbers).
More outside data (hand-labeled real data and a second national source) is wanted before any `k3`.

### Data and benchmarks

- A benchmark built from a national address source (NAD or similar), rendered in several
  styles and compared per state and per shape, to find parser bugs and place-list gaps.
- A cleaner blind test: a hand-labeled sample of real messy data in the shapes people
  actually have.
- More of the `parse` slowdown (issue #14 was mostly fixed in 0.2.0): about 8% of an
  earlier build's speed is still spread across allocation in the place keys and `Vec` growth.
- The pack infrastructure: report a pack's version in the output, and require a golden
  corpus per pack in CI.

## Not planned

- **Address validation or deliverability.** That needs postal-service-certified data.
- **Geocoding, fuzzy matching, address correction.**
- **International addresses.**
- **A machine-learned model.** The parser is rules plus place data on purpose, so a fix is a
  rule or a line of data, and the same input gives the same output.
