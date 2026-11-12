# The backlog: how issues are organized

The rules for sorting issues, the labels and milestones, and how work moves from an issue to a release. The current plan is
in [`roadmap.md`](roadmap.md). **Last reviewed 2026-11-12.**

## The release plan

| Milestone | What it is |
|---|---|
| **0.6.0** | The `k5`, the next key-changing release: the `version:K` issues measured at P2 or above, plus the short curated place list; the list is on [`roadmap.md`](roadmap.md). Tracker #416 |
| **0.6.x** | Point releases with no key change: tooling, documentation and performance |
| **Later** | Wanted or known, not planned: new API surface, parse rules below the P2 line, anything waiting on demand or a decision. The list by kind is on [`roadmap.md`](roadmap.md), "Waiting" |
| **Tooling** | Tooling not planned for a release (harness, review tool, benchmarks and CI items waiting for a rule or a decision): never shipped, never closed |
| **Won't Do** | Decided against, with the reason: tracker #417 |

Earlier releases are in [`CHANGELOG.md`](../CHANGELOG.md). `main` is the 0.6 line and carries a `-dev` version until the release pull request
sets the release version; 0.5.x patches, if any, are cut from `release/0.5.x` and ported back. The project has few users, so a patch release
needs a good reason: a wrong key or a panic on valid input, a security or supply-chain problem, or a broken published artifact.

**Key-affecting rules merge to `main` unreleased**, as ordinary pull requests, each measured against the frozen keys of the last key release with
`tools/compare/key_diff.py diff`, by source and role, for the sources its issue names (the loop is in [`tools/harness.md`](tools/harness.md)).
A rule that only reads or moves a unit changes no property-level key, so dump both builds with `--unit` and read the unit-level counts too.

**"Key-neutral" is a claim about that comparison**, not about warnings or flagged rows: #97 was called key-neutral from warning counts and then
changed 8.7% of the IRS file's keys (the 0.3.1 record in [`key-format.md`](key-format.md)). The comparison parses whole records files with both builds
(`parse_fields_many`) and compares `a.key()` row by row; the dumps record the commit as well as the version, because between releases `main` still
reports the last release's version. A pull request that says its keys do not change includes the count (counts only, never street text).

## Labels

| Label | Meaning |
|---|---|
| `research` | An issue whose first output is a measurement or a decision, not code . It says what outcome would close it |
| `size:S` / `M` / `L` / `D` | Hours; a day or two; several pull requests or a design; a decision with no code |
| `version:K` | Changes a key (the number, directionals, street name, suffix, state, ZIP or unit; place data that moves the street/city split). Held for the next key release (the `k5`, tracker #416); it can merge to `main` unreleased, measured row by row against the frozen keys |
| `version:B` | Breaks an API: removes or renames a public thing |
| `version:O` | Changes output without a key: a warning, a new field, a new opt-in API |
| `version:N` | No user-visible change: docs, tooling, tests, internal |
| `priority:P0` to `P3` | P0 a correctness bug in shipped output or a release blocker; P1 do next; P2 planned; P3 held until data, a decision or demand |
| `area:architecture` | How the core works: state data, the lexicon, the layer format |
| `area:rules` | Parser rules and warnings: what an input parses to |
| `area:api` | The public surface: Rust, Python, CLI, JSON, warning codes |
| `area:tooling` | Harness, review tool, benchmarks, CI |
| `area:docs` | Documentation, the site, the announcement |
| `tracker` | A meta issue that lists other issues |

The milestone says **which release**; `version:` says **what kind of change**; `area:` says **which part of the
project**. An issue that is `version:K` is in the 0.6.0 milestone (the `k5`) once it is planned, and in Later until then.

## Where an issue comes from

- **A misparse report** or a finding from a harness run goes through the rule loop in [`tools/harness.md`](tools/harness.md): reproduce with an
  invented address, find a source, add a corpus case, measure before and after.
- **A review of real rows** ([`tools/review.md`](tools/review.md)) produces a tracker with the counts and then one issue per finding, labeled as above.
  Examples in issues are invented from scratch, never real rows ([`data-policy.md`](data-policy.md)).
- **A decision** is `size:D` and says what outcome would close it.
- **A new issue gets its labels and a milestone when it is filed** (`version:`, `priority:`, `size:`, `area:`, a milestone; a research issue also
  `research`), so that none sits outside the plan.

## Ordering by how common

The issues of a release are ordered by a score, not by feel: `rows affected x harm / effort`.

- **Rows affected**: the probe's matches over the large sources (`tools/harness/probes.py`), multiplied by the precision when a review has
  measured it (1 until then). The denominator is the unsampled probe scan (289M rows); name it whenever a threshold is quoted.
- **Harm**: 3 for a wrong key with no warning, 2 for a wrong key with a warning, 1 for a warning or a component only.
- **Effort**: the size label, S 1, M 2, L 4, D 2.
- **Priority from the rows affected:** P1 from 25,000 rows (about 0.01% of the scan); P2 from 2,000 rows; P3 below. A new finding above 25,000 rows is P1
  by definition. Only an issue measured P2 or above leaves `Later`. A review queue's share is larger than the rows share (a comparison queue holds
  only the rows the two parsers disagree on), so both are looked at.

Refresh the numbers after each batch of rules (the same probes are the before and after of a rule PR) and when a source is added.

## Keeping it current

After a batch of issues closes, and at each release: tick the boxes of the open tracker, update the "Next" part of the roadmap, move what no longer
fits a milestone, and change the "Last reviewed" line on both pages. The label descriptions on GitHub (`gh label list`) follow the table above.
`python tools/docs/issue_states.py` (needs `gh`; run by hand) lists what no longer fits: a closed issue in a planned part, an issue in the wrong
milestone, an open issue neither page mentions, and a tracker box that disagrees with the issue.
