# The backlog: how issues are organized

How the open issues are sorted, what the labels and milestones mean, and how work moves from an issue to a
release. The current plan is in [`roadmap.md`](roadmap.md); this page is the rules. It replaces the
definitions that lived in the body of issue #103 (the backlog review), which now only holds its history.

## The release plan

Releases are staged so each one can be proven on its own:

| Milestone | What it is | Gate |
|---|---|---|
| **0.3.x** (`0.3.2`, ...) | Key-neutral patches: warnings, diagnostics, docs | A row-by-row key comparison with the last release shows zero differences |
| **0.4.0** | The foundation: the architecture (state data folded into the core, an extension-ready lexicon) and the breaking API cleanup. The key stays `k2` | The same zero-difference comparison against the last 0.3.x release |
| **0.5.0** | The `k3`: every key-affecting parser rule, cut together | The measured before and after in [`key-format.md`](key-format.md) ("Changing the key") |
| **Later** | Wanted, not planned for a release: new API surface, anything waiting on demand or a decision | |
| **Tooling** | Harness, review tool, benchmarks, CI: never shipped, never closed | |

After 0.3.2, `main` is the 0.4 line; a critical 0.3.x fix goes on a `release/0.3` branch cut from the last 0.3
tag. Nothing waits open "for the k3": key-affecting work merges to `main` once 0.4.0 is out. The trackers
(`tracker` label) list the order inside a release: #138 (0.4.0) and #139 (0.5.0).

**The comparison.** Install the released version in a throwaway environment, parse whole records files with both
builds (`parse_fields_many`) and compare `a.key()` row by row, by source. "Key-neutral" is a claim about this
comparison, not about warnings or flagged rows: #97 was called key-neutral from warning counts and then changed
8.7% of the IRS file's keys (the 0.3.1 record in `key-format.md`). A rule pull request that says its keys do
not change includes the count.

## Labels

| Label | Meaning |
|---|---|
| `size:S` / `M` / `L` / `D` | Hours; a day or two; several pull requests or a design; a decision with no code |
| `version:K` | Changes a key (the number, directionals, street name, suffix, state, ZIP or unit; place data that moves the street/city split). Held for the `k3` |
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
project**. An issue that is `version:K` is in 0.5.0 unless it is a research item that feeds one.

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
- #103 holds the history of the first review (2026-10-20); a new full review is only needed if the structure
  here stops fitting.
