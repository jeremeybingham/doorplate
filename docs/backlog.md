# The backlog: how issues are organized

How the open issues are sorted, what the labels and milestones mean, and how work moves from an issue to a
release. The current plan is in [`roadmap.md`](roadmap.md); this page is the rules. It replaces the
definitions that lived in the body of issue #103 (the backlog review), which now only holds its history.

## The release plan

One release, 0.4.0, in two phases (decided 2026-10-23: the `k3`, planned as 0.5.0, is folded into 0.4.0 because the
project has no users and the foundation went quickly; it saves a version and a release cycle). **0.4.0 was released on
2026-10-25**; the plan after it is the 0.4.x and 0.5.0 milestones below.

| Milestone | What it is | Gate |
|---|---|---|
| **0.4.0** | **Phase 1, the foundation:** the architecture (state data folded into the core, an extension-ready lexicon) and the breaking API cleanup, with the key unchanged (`k2`) and no parsing changes. **Phase 2, the `k3`:** the parser rules already listed in #138, key-affecting or not (warnings and diagnostics included), cut together; the list is closed (see "Scope" below) | Phase 1 ends at the **checkpoint**: zero key differences with 0.3.1 over the large sources, and those keys frozen as the baseline. The release: the measured before and after against that baseline, in [`key-format.md`](key-format.md) ("Changing the key"). The checkpoint passed on 2026-10-23 (commit `1819acd`: zero differences over 36.9M rows) |
| **0.4.x** | **Tooling, documentation and extensibility**, no key change: the anonymizer (#105, done), harness scorers (#112), review tool v2 (#132), per-state counts (#53, done), the documentation site (#107), the custom layer (#3), columnar output (#24) and the usaddress-shaped module (#36) | Tracker #200 |
| **0.5.0** | The next key-changing release, the `k4`: the parser rules that change keys (#131 first, #196, #29, #11, #8, #92; #193 rides along). Held until the 0.4.x work has produced evidence | Tracker #201; the measured before and after against the `k3` keys, as for the `k3` |
| **Later** | Wanted, not planned for a release: new API surface, anything waiting on demand or a decision | |
| **Tooling** | Tooling that is not planned for a release (the harness, review tool, benchmarks and CI items waiting for a rule or a decision): never shipped, never closed. Empty after the 0.4.x plan moved its items | |

`main` is the 0.4 line and carries the version `0.4.0-dev` (a build from `main` never reports a released version; the
release pull request sets `0.4.0`): there is no 0.3.2. The project has no users, so a release is not made for a minor
fix. **A 0.3.x patch needs a very good reason:** a correctness bug in shipped output that matters (a wrong key, a panic
on valid input: the never-panic rule), a security or supply-chain problem, or a broken published artifact (a wheel that
does not install, a crate that does not build). It goes on a `release/0.3` branch cut from the `v0.3.1` tag, with the
full release checklist. The tracker (`tracker` label) lists the order: #138 for 0.4.0 (closed; #139, the `k3` tracker,
was merged into it), #200 for 0.4.x and #201 for 0.5.0.

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
in each environment, then `diff` (counts only, never street text). "Key-neutral" is a claim about this
comparison, not about warnings or flagged rows: #97 was called key-neutral from warning counts and then changed
8.7% of the IRS file's keys (the 0.3.1 record in `key-format.md`). A rule pull request that says its keys do
not change includes the count.

## Labels

| Label | Meaning |
|---|---|
| `size:S` / `M` / `L` / `D` | Hours; a day or two; several pull requests or a design; a decision with no code |
| `version:K` | Changes a key (the number, directionals, street name, suffix, state, ZIP or unit; place data that moves the street/city split). Waits for the checkpoint, then merges and is released with the `k3` |
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
project**. An issue that is `version:K` is in 0.4.0, phase 2, if it is in the list of #138; any other `version:K` issue is in Later.

## Where an issue comes from

- **A misparse report** (the issue template) or a finding from a harness run goes through the rule loop in
  [`tools/harness/README.md`](../tools/harness/README.md): reproduce with an invented address, find a source, add a
  corpus case, measure before and after.
- **A review of real rows** ([`tools/review/README.md`](../tools/review/README.md)) produces a tracker with the
  counts (#125 was the first) and then one issue per finding, labeled as above. Examples in issues are invented
  from scratch, never real rows ([`data-policy.md`](data-policy.md)).
- **A decision** is `size:D` and says what outcome would close it.

## Keeping it current

- At each release, refresh the milestones: move what slipped, close the finished milestone, and update
  [`roadmap.md`](roadmap.md) from them.
- #103 (closed 2026-10-25) holds the history of the first review (2026-10-20); a new full review is only needed if the structure
  here stops fitting.
