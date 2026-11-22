# Roadmap

What is planned, what waits, and what is not planned. Priorities follow the data people bring, so the more real, messy
addresses `doorplate` sees, the sooner the items below can happen ([Sharing messy data](../CONTRIBUTING.md#sharing-messy-data)).
Labels, milestones and ordering: [`backlog.md`](backlog.md). What each release changed is in [`CHANGELOG.md`](../CHANGELOG.md).

**Last reviewed 2026-11-22.** 0.7.0 is the first **beta** and cuts the `k6`. Next: 0.7.x (no key change) and 0.8.0 (the `k7`).
Open trackers: #724 and #332 (closed with the 0.7.0 release), #761 (glued strings, Later), #417 (decided against).

## Stability: beta from 0.7.0

- **API and warning codes.** The three API surfaces and the warning codes are stable: a rename or removal is announced one
  release ahead ([`api-surface.md`](api-surface.md), "Deprecation").
- **Keys.** The match key is versioned and each version is a contract ([`key-format.md`](key-format.md)). `k6` is frozen.
  A later rule that changes what an input produces gets a new key version (`k7`), only in a minor release (0.8 and later),
  never in a patch, and the changelog says so. Store the version prefix with the keys.
- **Accuracy and speed** are measured on a few datasets ([`benchmarks.md`](benchmarks.md)), not on yours.

## Released

- **0.7.0, the first beta and the `k6`** (tracker #724, checklist #810). The state data structure is gone (#700, the last
  planned API break); the key-affecting rules measured at P2 or above (boxes and routes, glued words, units and floors, house
  numbers, one-line separators, names beside the street); the Puerto Rico rules of #332 (the urbanization field, street-first
  and lettered numbers, Spanish box and route words, building lines). The release key comparison against 0.6.2 traced every
  changed key to a merged rule; the regressions it found are in 0.8.0. The list by rule is in the changelog.
- **0.6.2 and 0.6.1:** speed, no key change (about 25% and 27% less time per parse than the release before). Blog post:
  [doorplate 0.6.1](https://jeremeybingham.github.io/doorplate/2026/11/13/doorplate-0-6-1.html).

## Next: 0.7.x, no key change

Point releases carry speed, tooling, documentation and opt-in output, never a key change; a 0.7.x patch is cut from
`release/0.7.x` once `main` carries `k7` work. A CI guard fails a pull request that adds more than 1% instructions per parse.

- **Puerto Rico follow-ups (#818):** the standalone urbanization names, wider probes, a flagged-share check.
- **RESO 2.1 (#729):** the full-word suffix (`Street`) as an option; the default stays the abbreviation.
- **usaddress dependents:** the survey #723, the pudl benchmark #728 and its rule list #731 (re-run on the released build).

## Planned: 0.8.0, the `k7`

Key-affecting rules, each measured against the frozen `k6` keys before it merges (the loop is in [`tools/harness.md`](tools/harness.md)).
First the four small regressions the 0.7.0 key comparison found, each with a few dozen to a few hundred rows:

- #820 a hyphenated street name split by the ` - ` tail rule (`ELM GROVE - OAK ROAD`).
- #821 a military line with `PO BOX` on line 2 loses the military form; a wrong `missing_street_number` on route lines.
- #822 `PO BOX POBOX 123` and `PO BOX HC 2 BOX 1234` fall back to a street key.
- #823 `SP` before a numbered highway becomes the street name.

Other rules leave Later when a review measures them at P2 or above ([`backlog.md`](backlog.md), "Ordering by how common").

## Waiting, on data or demand

One line per kind. Every open issue here is in the **Later** milestone (or **Tooling**, where noted); none is at the P2 line (200 rows; 2,500 for P1).

- **Units:** #243, #290, #295, #345, #238, #559, #534, #531, #558, #770 (a unit split from its designator), #778, #798 (a line-1 unit, then a bare unit on line 2), #802 (`TOP FLOOR` after a suffix).
- **Boxes and routes:** #358, #307 (a route after a street), #774 (a box after the ZIP; decided with pudl).
- **House numbers and street names:** #594, #643, #560, #360 and #312 (a letter before a direction or the number), #321 (designator words after the suffix), #824 (a decimal house number, `123.5 MAIN ST`).
- **Names beside the street and parentheses:** #351, #589, #644, #645.
- **City field and line 2:** #367, #480, #482, #483, #596, #597, #742.
- **Glued strings (split and re-parse):** the tracker #761 with #766, #742 (above) and #656; its other parts shipped in 0.7.0.
- **ZIP forms and odd text:** #601, #602.
- **Parsing ideas:** #397, #435.
- **Review data and tooling:** the Tooling milestone (never shipped, never closed): #225, #395, #403; the parser showdown (its own repository).
- **Data, API, docs and speed:** #233, #11 (Won't Do), #253, #712 (speed leads left); Pub 28 reading #811 (the military and State Department images) and #812 (Appendix J and A2).
- **Not yet issues:** a highway modifier before a city on one line, a comma
  after a directional, a unit followed by business words, and
  `possibly_truncated` firing on some complete units.
- **A public Arrow result and a Polars expression namespace** only if there is demand.
- **usaddress labels** (#35): the drop-in module is done; more labels proceed when someone needs them. Recipient and name lines,
  landmarks and street corners stay out of scope; that text goes to `unparsed`.

## Researched, but not supported

International addresses are **not supported**. Two questions about them are researched, not planned: Canadian addresses (#203)
and a libpostal-shaped output ([`libpostal-compat.md`](libpostal-compat.md)). A result would become its own issue.

## Not planned

- **Address validation or deliverability.** That needs postal-service-certified data.
- **Geocoding, fuzzy matching, address correction.**
- **International addresses.**
- **A machine-learned model.** The parser is rules plus place data on purpose, so a fix is a rule or a line of data, and the
  same input gives the same output.
