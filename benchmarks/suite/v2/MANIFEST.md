# Suite v2: manifest

`v2` has the same records as `v1` (19,586, built 2026-10-19; see [`../v1/MANIFEST.md`](../v1/MANIFEST.md) for the composition,
the build commit and the checksums). It holds no data files: `scoring.json` names the folder the records come from
(`"records_from": "v1"`) and turns on one scoring rule. `v1` is frozen and is not edited.

## What differs from v1

Only the comparison track's scoring. A gold token that is a single letter A to D, labelled `AddressNumberSuffix` and right
after an `AddressNumber`, is right when the library labels it `AddressNumber`, `AddressNumberSuffix` or `OccupancyIdentifier`
(the #487 convention: `123 B MAIN ST` is house number 123, unit B; `123B` is the same address). Nothing else changes, so a
parse error of any other kind scores as before. The decision is in #586 (R7); the rule is in
[`docs/benchmark-suite.md`](../../../docs/benchmark-suite.md#versions).

- 241 records have such a letter: 207 `hard`, 33 `natural`, 1 `hand`. None has `expect`, so the doorplate-only track is the same.
- doorplate on `main` `ad1ee05`, coarse, all records: whole suite 92.4% (`v1`) and 93.5% (`v2`); `natural` 98.3% and 98.5%;
  `hard` 54.8% and 62.1%; `hand` 94.3% and 94.4%. usaddress: no change.
