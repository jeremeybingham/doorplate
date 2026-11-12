# Canonical key and slug spec (version k5)

This page specifies the **key** (below) and the **slug** (last section).

The key is versioned, and a given version is a contract: stored keys must keep
meaning the same thing, so any change to what an input produces needs a new version
prefix (`k6:`) and an update here. `k5` is never edited in place.

**This is an alpha release.** Expect new key versions as the parser improves: the
parser's behavior is still settling, and every fix that changes how an input is read
changes its key. If you store keys, store the version prefix with them (it is part of
the key) and plan to re-key when a new version appears. Keys of different versions
are never equal. To re-key, parse the original addresses again: a stored key cannot be
converted.

A key says two inputs name the same place as far as this library can tell. It
does not say the address exists or is deliverable (see README).

## Format

```
k5:S|<number>|<predir>|<name>|<suffix>|<postdir>|<state>|<zip5>[|<unit>|<unit2>]
k5:P|<box>|<state>|<zip5>
k5:R|<RR|HC>|<route>|<box>|<state>|<zip5>
k5:M|<kind>|<number>|<box>|<post office>|<state>|<zip5>
k5:G|<state>|<zip5>
```

- Prefix `k5:`, then a one-letter **form**, then segments separated by `|`.
  Every form has a fixed number of segments, and an empty value leaves an
  empty segment (`...||...`).
- Forms: `S` street, `P` PO Box, `R` rural or highway contract route, `M`
  military or Department of State line, `G` general delivery. Because the
  form is part of the key, a PO Box key can never equal a street key.
- `S`: `<name>` is the street name; for a street named after a highway it is
  the standard prefix plus the route (`COUNTY ROAD 23`), after the state code
  when the highway name holds a state (`KY STATE HIGHWAY 625`, Pub 28
  Appendix F), and followed by any name words after the route
  (`HIGHWAY 66 FRONTAGE`). `<suffix>` and the
  directionals are Pub 28 abbreviations.
- **Route numbers:** leading zeros before another digit are dropped from a rural
  or highway contract route and from a highway route in a street name, so `RR 02`
  and `RR 2` share a key, as do `COUNTY ROAD 023` and `COUNTY ROAD 23`; an
  all-zero route keeps one zero (`00` is `0`). Pub 28 sections 242 and 252 call
  the zero unnecessary. Box numbers (`BOX 04`) and PO Box numbers keep theirs: section
  282 says the ZIP+4 file marks significant box zeros. The USPS output writes the
  route as given.
- **A letter after the house number** keys three ways (#653): `123 B ELM ST` (a spaced `A` to `D`, a unit, #487) and `123 ELM ST APT B` both key as `123`; `123B ELM ST` (the letter stuck to the number) keys as `123B`, and carries the warning `glued_number_letter`. The counts over seven sources did not separate a lettered house number from a unit written tight, and a merged key cannot be corrected once a key version is cut, so the glued form is not merged. Review the rows with the warning if your data writes units tight. Letters `E` to `Z` are never read as a unit.
- **Queens house numbers:** when the resolved place is in Queens, NY, the hyphen of a house number of one to three
  digits, a hyphen, two digits and an optional letter is dropped, so `37-12 82ND ST` and `3712 82ND ST` (and `37-12A` and
  `3712A`) share a key. Elsewhere the hyphen stays (`20-22 W 45TH ST` in Manhattan is two numbers). The parsed
  `street_number` keeps what was written. A pair read with a space (`41 12 80TH AVE` in a New York City ZIP, Massachusetts or Hawaii, #313) keys like its hyphenated twin.
- `M`: `<kind>` is CPR, OPC, PSC, UPR or UNIT; `<post office>` is APO, FPO or
  DPO (empty when absent).
- `<state>` is the USPS code. `<zip5>` is five digits.
- **Dual addresses:** a record with a street address and a PO Box (Pub 28
  section 215, `dual_address` warning) uses form `S`, from the street; the box is
  not in the key. A box with street words after it and no house number (`PO BOX 190 ELM RD`, #366) is not a dual address: it uses form `P`, and the road is only in the components.
- **Floors:** a floor unit's value is a number (`5TH FLOOR` gives `5`).
- **Not in the key:** city, ZIP+4, unit type, the attention line, the
  building name, anything in
  `diagnostics`.
  - City is noisy and the field most likely to be corrected later; leaving it
    out keeps stored keys stable.
  - ZIP+4 varies within one building.

## Strong and partial keys

A key with both a state and a ZIP5 uses the `k5:` prefix. If either is
missing, the prefix is `k5n:` and the same body follows (`k5n:S|123||MAIN|ST||FL|`).
A partial key matches less reliably, and it can never equal a located key, so
the two kinds do not mix in a join by accident. `MissingState` or
`MissingZip` is also set in the diagnostics.

## Units

`KeyOptions { include_unit }`, default **`false`** (property level).

- `false`: units are not in the key; every unit in a building shares it.
- `true`: for form `S` only, two segments are appended: the first and second
  unit numbers. Unit **types are dropped**: `Apt 4`, `Unit 4` and `#4` all
  give `4`, so `Apt 4` and `#4` match. The cost is that
  `Apt 2` and `Fl 2` in one building collide at unit level.
- A unit-level key is the property key plus two segments. A unit-level key
  for an address with no unit still ends in `||`, so it differs from the
  property key and from any unit-bearing key.
- Other forms ignore the option.

## Normalization

Applied to every free-text segment (number, name, route, box, unit):

1. Uppercase; drop periods and apostrophes (`O'BRIEN` and `OBRIEN` match).
   Pub 28 lets punctuation be omitted (section 222) and lists periods and
   apostrophes for removal (section 354). Section 232 keeps the period in a
   name such as `39.2 RD`, and the USPS emitter does, but the key drops it,
   so `39.2 RD` and `392 RD` share a key.
2. Collapse whitespace to one space.
3. Percent-encode (`%XX`, uppercase hex, UTF-8 bytes) every character outside
   `A-Z 0-9 space / -`. This keeps `|` and `%` out of segments; `clean.rs`
   already folds accents, so it rarely applies.

Spelling variants (`North`/`N`, `Street`/`ST`, `Florida`/`FL`) are resolved by
the parser through the Pub 28 tables, not by the key. Sources for those
tables: `docs/usps-pub28-notes.md`. The key format itself (segments, form
letters, dropped unit type, `k5n`) is this library's own convention, not a
USPS rule.

## No key

`key()` returns `None` when there is nothing to key on: no street, PO Box,
route, military line or general delivery, a placeholder such as `NO SITUS`
(`Placeholder` warning), or an intersection (`MAIN ST & 1ST AVE`,
`IntersectionDetected` warning), because the first street alone would match every
address on it.

## Stability

`k5` is the format as of version 0.6.0. The key is a function of the parse, and
the parse is a function of the shipped tables and rules: a bug fix that changes what
an input produces is a key change and needs `k6`. The slug and `place` are not part
of the key and may change with parser improvements.

**A custom layer can change a key.** A layer ([`custom-layers.md`](custom-layers.md), #3) adds spellings
and words the shipped tables do not have, so the same input can parse, and key, differently with and
without it, or with another layer. This is not a key change in the sense above (the format and the
shipped rules are the same; `k5` stays `k5`), but stored keys are only comparable when they come from
the same layer. Every parse reports the layer it used (`Diagnostics::custom_layer`: its name, version
and a content fingerprint); store the fingerprint beside the keys, and re-key when the layer changes.
A parse with no layer is identical to one from a build without the feature.

## Changing the key

**What counts as key-affecting.** Anything that changes what an input parses to in the parts
the key reads: the number, directionals, street name, suffix, state, ZIP and unit. That includes
place data (the national list or a state's data) that changes where the street ends and the city
starts on a line with no commas. It does not include `city` or `place` reporting alone, new
warnings, new output fields, or labels added to the usaddress emitter only. When unsure, compare
the keys of a representative sample before and after: `tools/harness/compare.py` counts what
changed.

**Holding policy.** A new key version makes every stored key re-key and is a breaking change, so
key-affecting changes are cut together as one version, not released one by one. Such a change merges to `main` as an ordinary pull
request, measured against the frozen keys, and stays unreleased until the next key version is cut. Its issue is labeled `version:K`:
[issues labeled `version:K`](https://github.com/jeremeybingham/doorplate/issues?q=is%3Aissue+is%3Aopen+label%3Aversion%3AK).
Changes that do not alter a key (a new warning, a new output field, tooling, docs) ship as usual
([the roadmap](roadmap.md)).

**What a new key version needs.**

- an evidence base for each change (counts and a source, not a guess);
- a measured before and after against the frozen checkpoint keys: the golden corpus, a run over the large local
  sources (`tools/compare/key_diff.py diff`: how many keys change, by source and class), and the benchmark suite
  with its private twin;
- this page updated, a CHANGELOG note that keys changed (store the prefix, re-parse to re-key), and
  the corpus key expectations (`tests/corpus/keys.jsonl`, `tools/corpus/emit_expect.py`) rewritten
  from the spec.

**When to cut it.** Key-affecting rules are merged one pull request at a time under the current prefix, each measured against the frozen
keys, and the prefix changes in one pull request at the end (the cut), before the release. There is no count or evidence threshold:
the call is made from how smoothly the items progress.

## Version history

Each version's rules are listed in [`CHANGELOG.md`](../CHANGELOG.md) (the entries marked "held for the `k<n>`"). The
prefix is the only change to a key that no rule touched, so re-keying is a re-parse.

| Version | Release | Segment layout | What changed |
|---|---|---|---|
| `k5` | 0.6.0 (this page) | as `k4` | Some keys change, because 0.6.0 reads some inputs differently (the rules held for the `k5`, listed in [`CHANGELOG.md`](../CHANGELOG.md)). Frozen: a change to what an input produces needs `k6`. || `k4` | 0.5.0, retired in 0.6.0 | as `k3` | Some keys change, because 0.5.0 reads some inputs differently. |
| `k3` | 0.4.0, retired in 0.5.0 | as `k2` | Some keys change, because 0.4.0 reads some inputs differently. |
| `k2` | 0.3.0, retired in 0.4.0 | as `k1` | Some keys change. 0.3.1 corrected the keys of inputs with a `%` care-of line or `IN CARE OF` (the care-of text had pushed the tail of line 1 into the street name). If you stored `k2` keys from 0.3.0 for such addresses, re-parse them. |
| `k1` | 0.1.0 and 0.2.0 | | Retired: the library no longer produces it and cannot compute it. |

## Slug

`slug()` is a URL-safe, human-readable label. Unlike the key it is **not a
contract**: it is not unique, not versioned, and may change when parsing or
formatting improves. Never store it as an identifier; use the key.

- Built from the Pub 28 style output (`to_usps()`): delivery line with its
  unit, city, state, ZIP5. ZIP+4 is left out. Unlike the key, the city and
  the unit type are included, because a slug is for people to read.
- Lowercase ASCII letters and digits; every other run of characters becomes
  one hyphen, with none at either end. Apostrophes are dropped (`O'BRIEN` ->
  `obrien`) and `#` reads as `unit`, so `#4` gives `unit-4` while `Apt 4`
  gives `apt-4`.
- Missing parts are left out (`123-main-st`). `None` for a placeholder, an
  intersection or an address with no lines.
- A dual address (street and PO Box) is built from the street line and its
  units, not the PO Box the USPS output writes, so the slug, key and RESO
  output all name the street (`9418-cuba-rd-hayes-va-23072`).
- Example: `123 N. Main Street, Apt 4, Miami FL 33101` gives
  `123-n-main-st-apt-4-miami-fl-33101`.

## Tests

`tests/corpus/keys.jsonl` pins exact key and slug strings (`key`, `key_unit`
and `slug` fields); unit tests in `crates/doorplate/src/emit/key.rs` and
`slug.rs` cover the rules.
