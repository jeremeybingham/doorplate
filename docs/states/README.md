# State data

A state's data is hand-checked places, spellings and ZIPs for one state, added where real data shows the
national list is not enough. It is always compiled in: there is no feature per state, and the folder is the
whole switch. Florida is the first ([`fl.md`](fl.md)). The layers it sits in are in
[`how-it-works.md`](../how-it-works.md) ("Lexicon layers"); the rules for what data may ship are in
[`data-policy.md`](../data-policy.md).

## Adding a state

A folder `crates/doorplate/data/states/<st>/` (the USPS code in lower case) with:

| File | Holds |
|---|---|
| `state.toml` | the state, the data version and the sources |
| `places.tsv` | the places (`name`, `county`, `kind`, `sources`, `variants`) |
| `zips.tsv` | the ZIP to main place table |
| `places_added.tsv`, `variants_added.tsv`, `zips_observed.tsv` | optional: communities, spellings and ZIP pairs found in real data |
| `overrides.toml` | optional: spellings that mean something else in this state than in the base tables (a street suffix or a highway prefix). Each entry names its evidence |

Every entry cites its evidence, and a spelling or a ZIP pair needs at least 10 distinct addresses (write the
threshold down if a new state uses another). `build.rs` checks every file and fails the build on a malformed or
contradictory row.

A state also needs a golden-corpus file, `tests/corpus/<st>-state.jsonl`, with cases from that state (invented
addresses). A test fails when a folder under `data/states/` has no such file. Add a doc page, `docs/states/<st>.md`,
with the sources and the licenses, and check the table in [`../change-checklist.md`](../change-checklist.md).

The zip-to-place warning (`zip_city_mismatch`) is raised only in a state with curated data
(`Lexicons::has_state_data`): the national list names one place per ZIP, so elsewhere it would fire on addresses
that are fine.
