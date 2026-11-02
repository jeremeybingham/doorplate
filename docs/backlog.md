# The backlog: how issues are organized

How the open issues are sorted, what the labels and milestones mean, and how work moves from an issue to a
release. The current plan is in [`roadmap.md`](roadmap.md); this page is the rules. It replaces the
definitions that lived in the body of issue #103 (the backlog review), which now only holds its history.
**Last reviewed 2026-11-01 (#402, the 0.5.1 performance round and the docs pass #399), against the issues up to #451.**

## The release plan

One release, 0.4.0, in two phases (decided 2026-10-23: the `k3`, planned as 0.5.0, is folded into 0.4.0 because the
project has no users and the foundation went quickly; it saves a version and a release cycle). **0.4.0 was released on
2026-10-25**; the plan after it is the 0.4.x milestone, which becomes the 0.4.1 release (decided 2026-10-27), and the 0.5.0 milestone below.

| Milestone | What it is | Gate |
|---|---|---|
| **0.4.0** | **Phase 1, the foundation:** the architecture (state data folded into the core, an extension-ready lexicon) and the breaking API cleanup, with the key unchanged (`k2`) and no parsing changes. **Phase 2, the `k3`:** the parser rules already listed in #138, key-affecting or not (warnings and diagnostics included), cut together; the list is closed (see "Scope" below) | Phase 1 ends at the **checkpoint**: zero key differences with 0.3.1 over the large sources, and those keys frozen as the baseline. The release: the measured before and after against that baseline, in [`key-format.md`](key-format.md) ("Changing the key"). The checkpoint passed on 2026-10-23 (commit `1819acd`: zero differences over 36.9M rows) |
| **0.4.x** | **Tooling, documentation and extensibility**, no key change, released as **0.4.1** (decided 2026-10-27): the custom layer (#3), the anonymizer (#105), `doorplate.compat` (#36), faster columns (#24), harness scorers (#112), review tool v2 (#132), per-state counts (#53), the documentation site (#107, #229) and coverage (#211): all done and released as 0.4.1 on 2026-10-28 (the site, #107 and #229, was closed 2026-10-28; what follows the release is #252). Milestone closed after #252 |  Tracker #200; the release checklist in `CONTRIBUTING.md` |
| **0.5.0** | The key-changing release, the `k4`: the parser rules that change keys, from the reviews of real rows and the harness counts; **released 2026-10-31** (the list was closed once #247 merged; the rules and their counts are in the changelog). Milestone closed after the release | Tracker #201 (closed with the release); the measured before and after against the `k3` keys, the probes and the full Netsyms run on 0.4.1 and on the cut |
| **0.5.x** | **Tooling, documentation and performance point releases**, no key change (decided 2026-10-31): the performance round (about half the time per parse of 0.4.1, keys unchanged; [`speed-and-size.md`](speed-and-size.md)) is done; what is left is the docs edit pass (#399, with #277) | Tracker #402 |
| **0.6.0** | The `k5`, the next key-changing release: every `version:K` issue not yet scheduled; nothing is planned for it yet | Tracker #416 |
| **Later** | Wanted or known, not planned for a release: new API surface, parse rules below the P2 line, review data and trackers, anything waiting on demand or a decision. The list by kind is in [`roadmap.md`](roadmap.md), "Waiting" | |
| **Tooling** | Tooling that is not planned for a release (the harness, review tool, benchmarks and CI items waiting for a rule or a decision): never shipped, never closed. Now holds #323 (MessyStreets); #434 (the Try page) is in review | |

`main` is the 0.5 line. It carries the next patch version with a `-dev` suffix (`0.5.1-dev` until the 0.5.1 release, then `0.5.2-dev`; decided 2026-10-31) until the release pull request sets the release version, so a build from `main` reports a version no release has used (it said the last release until 2026-10-31). There is no 0.3.2. The project has no users, so a release is not made for a minor
fix. **A 0.3.x patch needs a very good reason:** a correctness bug in shipped output that matters (a wrong key, a panic
on valid input: the never-panic rule), a security or supply-chain problem, or a broken published artifact (a wheel that
does not install, a crate that does not build). It goes on a `release/0.3` branch cut from the `v0.3.1` tag, with the
full release checklist. The tracker (`tracker` label) lists the order: #138 for 0.4.0 (closed; #139, the `k3` tracker,
was merged into it), #200 for 0.4.x and #201 for 0.5.0. #225 is a different kind of tracker: the record of which sources have been
hand-reviewed and the queues to come.

**Scope of phase 2** (decided 2026-10-23, issue #138). The list of rules is closed: phase 2 works the issues that are in the 0.4.0 milestone and does not go looking for new rules, so the backlog does not grow faster than it is worked. In practice:

- A finding that surfaces while working an issue is filed under **Later**, unless the issue cannot be fixed correctly without it (then it is part of that issue).
- Tooling is built **just in time**, for a rule that is in the list (as the checkpoint tool was), and not as a standing evidence phase. Tooling that only finds new things (the review tool's comparison mode, #132) or that no listed rule needs (#112, #53) waited in the **Tooling** milestone (moved to 0.4.x after the release, #200).
- The state-dependent rules and the reading that feeds them (#8, #11, #29, #92) are in **Later**; #110, the small architectural fix, stays.

**The checkpoint.** Until it is passed, no parsing change merges, so that the comparison with 0.3.1 can be zero
and any difference is the refactor's. It is one run, `tools/compare/checkpoint.py` (it prints a plan and needs
`--confirm`): every records file is parsed with the released build and the current build, the keys are compared row
by row, and the current build's dumps are kept in `local-data/keycompare/checkpoint-<commit>` with a `FROZEN.md`
note. After it, `version:K` and other parsing work merges to `main` as ordinary pull requests (and stays unreleased
until the release); each key-affecting one is measured against the frozen keys with `key_diff.py diff`, by source
and role, for the sources its issue names. The release does the full before and after over all of them once more.

**The comparison.** Install the released version in a throwaway environment, parse whole records files with both
builds (`parse_fields_many`) and compare `a.key()` row by row, by source. `tools/compare/key_diff.py` does it: `dump`
in each environment (`dump-all` does every source in `local-data/keycompare/sources.txt` in one call), then `diff` (counts only, never street text); the dumps record the commit as well as the version, because between releases `main` still reports the last release's version. "Key-neutral" is a claim about this
comparison, not about warnings or flagged rows: #97 was called key-neutral from warning counts and then changed
8.7% of the IRS file's keys (the 0.3.1 record in `key-format.md`). A rule pull request that says its keys do
not change includes the count.
A rule that only reads or moves a unit changes no property-level key, so dump both builds with `--unit` and read the "unit level" counts (the unit-level key and the unit fields, by source and role) as well.

## Labels

| Label | Meaning |
|---|---|
| `research` | An issue whose first output is a measurement or a decision, not code (#131, #203, #215, #236). It says what outcome would close it |
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

- **A misparse report** (the issue template) or a finding from a harness run goes through the rule loop in
  [`docs/tools/harness.md`](tools/harness.md): reproduce with an invented address, find a source, add a
  corpus case, measure before and after.
- **A review of real rows** ([`docs/tools/review.md`](tools/review.md)) produces a tracker with the
  counts (#125 was the first) and then one issue per finding, labeled as above. Examples in issues are invented
  from scratch, never real rows ([`data-policy.md`](data-policy.md)).
- **A decision** is `size:D` and says what outcome would close it.
- **A new issue gets its labels and a milestone when it is filed** (`version:`, `priority:`, `size:`, `area:`, and a milestone; a research issue also
  `research`), so that none sits outside the plan. The second review of real rows (#245) filed each finding that way and added the key-changing ones to the
  0.5.0 tracker.

## Ordering by how common

The issues of a release are ordered by a score, not by feel (#298): `rows affected x harm / effort`.

- **Rows affected**: the probe's matches over the large sources (`tools/harness/probes.py`, [`docs/tools/harness.md`](tools/harness.md)), multiplied by the
  precision when a review has measured it (the share of matches that are really the pattern and really wrong; 1 until then). A full Netsyms run adds
  `agg_probes` over all 146.6M rows.
- **Harm**: 3 for a wrong key with no warning, 2 for a wrong key with a warning, 1 for a warning or a component only.
- **Effort**: the size label, S 1, M 2, L 4, D (a decision) 2.
- **Priority from the score**, with the rows share as the floor: P1 above 0.1% of the rows or 5% of a review queue; P2 above 0.01%; P3 below. A review queue's share
  is larger than the rows share (a comparison queue holds only the rows the two parsers disagree on), so both are looked at.

Refresh the numbers after each batch of rules (the same probes are the before and after of a rule PR, next to `key_diff.py`) and when a source is added.

## Keeping it current

- At each release, refresh the milestones: move what slipped, close the finished milestone, and update
  [`roadmap.md`](roadmap.md) from them.
- **Also after a batch of issues closes**, not only at a release (this page and the roadmap were a week behind after the 0.4.x work merged, #237): tick the
  boxes of the open tracker (#402 for 0.5.x), update the "Released" and "Next" parts of the roadmap, move what no longer fits a milestone, and change the
  "Last reviewed" line at the top of both pages. The label descriptions on GitHub (`gh label list`) follow the table above. `python tools/docs/issue_states.py` (needs `gh`; run by hand) lists what
  no longer fits: a closed issue in a planned part, an issue in the wrong milestone, an open issue neither page mentions, and a tracker box that disagrees with the
  issue.
- #103 (closed 2026-10-25) holds the history of the first review (2026-10-20); a new full review is only needed if the structure
  here stops fitting.
