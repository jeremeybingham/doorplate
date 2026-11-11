# Version comparison: what changed between builds

How accuracy, speed, size and the keys moved from 0.3.1 to `main`, and why. The figures come from
**one measured run** (the away run of 2026-11-07, collected 2026-11-08, tools revision `0aff780`) and from the
review of that run (#586: causes bisected to the pull request, the blast radius of each rule, the benchmark
barriers). Every figure names its build. Counts only; the examples are invented.

This page is the record of that run. The current figures, what each benchmark is and how to run it are in
[`benchmarks.md`](benchmarks.md), [`speed-and-size.md`](speed-and-size.md) and
[`running-benchmarks.md`](running-benchmarks.md); the label conventions the benchmarks disagree about are in
[`usaddress-compat.md`](usaddress-compat.md) and are not repeated here. The checklist that uses this page's
release tolerance is [`change-checklist.md`](change-checklist.md#release-tolerance-for-the-benchmarks).

## What was measured

| Build | Commit | | Build | Commit |
|---|---|---|---|---|
| v0.3.1 | `9e8373d` | | v0.5.0 | `82e5541` |
| v0.4.0 | `cf3d96a` | | v0.5.1 | `20513e8` |
| v0.4.1 | `23f30e9` | | main (the run's) | `4b07638` |

Between v0.5.1 and `main` the run also built every merged rule pull request on its own (23 builds, `pr460` to
`pr564`), so a change can be assigned to the pull request that made it. All figures are deterministic: the run found
no input whose reading differed between v0.4.0 and v0.4.1, or between v0.5.0 and v0.5.1 (neither release changed
parse rules), so a difference between two builds is a real change, not noise.

`main` below is `4b07638`. Since then `crates/` has not changed (checked 2026-11-10: everything after the run is
documentation and tooling), so the run's `main` figures still describe the parser. Re-check that before quoting
one after a later parser change.

## Accuracy

### The headline: one decision explains the drift

Whole-address score, coarse scoring (`compare_usaddress.py`), geocode benchmark, per build:

| Split (addresses) | v0.3.1 | v0.4.0 | v0.4.1 | v0.5.0 | v0.5.1 | main | usaddress |
|---|---|---|---|---|---|---|---|
| train80 (118,538; rules were fixed against it) | 94.4 | 94.4 | 94.4 | 94.2 | 94.2 | 94.2 | 88.1 |
| train20 (29,635; held out, never read) | 94.1 | 94.2 | 94.2 | 94.1 | 94.1 | 94.0 | 88.4 |
| dev (60,522; partly looked at) | 94.4 | 94.5 | 94.5 | 94.3 | 94.3 | 94.3 | 88.1 |
| test (30,622; read while the rules were written, optimistic) | 96.7 | 96.8 | 96.8 | 96.7 | 96.7 | 96.6 | 88.2 |

Against v0.4.1 the splits lose 0.1 to 0.2 points. The held-out split falls as much as the fitted ones (0.2 against 0.2
from v0.4.1 to `main`), so the loss is not over-fitting to the benchmark: it is one reading that all four splits share.
usaddress does not change and is the control.

**Cause (R2: every lost string bisected over the merges between each build pair, 71 builds).** On geocode, from v0.4.1
to `main`, the strings right before and wrong after:

| Split | Lost | Gained | A letter after the house number | Everything else |
|---|---|---|---|---|
| dev | 112 | 1 | 98 (88%) | 14 (#563: 8, #369: 3, #364: 2, #370: 1) |
| test | 54 | 1 | 47 (87%) | 7 |
| train80 | 203 | 0 | 186 (92%) | 17 |
| train20 (labels only) | 57 (46 at v0.5.0, 11 more on `main`) | 0 | the same pattern: 43 of the 46 are a street name read as the house number, the 11 a street name read as a unit | |

The letter reading changed twice: v0.5.0 joined a letter A to D to the house number (#297, `123 A ELM ST` is `123A`),
and `main` reads it as a unit (#514, the #487 decision, with #526 for a letter before a suffix word). The
reference data labels the letter as part of the street name, so neither of our readings matches it. See
[`usaddress-compat.md`](usaddress-compat.md#label-conventions) for the three conventions.

**Most of these are not a letter.** About 80% of the lost geocode strings (72 of 91 on dev at v0.5.0, 38 of 44 on test,
156 of 189 on train80; a lower bound) are a street name the benchmark split with a stray space on purpose
(`318 D ELBERT LN` for DELBERT, its "space addition" error). The benchmark's label is right and both our readings
are wrong. In the seven large sources the shape is almost absent, so doorplate does not read through a stray space
([`benchmarks.md`](benchmarks.md#what-caps-the-geocode-score) has the full error classes and ceilings). The rest
(about 20 on dev) are true letters: one-letter streets, grid roads, initials, units.

### fastaddress files

Whole address right, coarse (`fa-eval`), "not in usaddress's training files", ours:

| File (addresses) | v0.3.1 | v0.4.0 | v0.4.1 | v0.5.0 | v0.5.1 | main |
|---|---|---|---|---|---|---|
| clean (134) | 89.6 | 89.6 | 89.6 | 87.3 | 87.3 | 87.3 |
| verdicts (218) | 65.1 | 66.5 | 66.5 | 69.3 | 69.3 | 67.4 |
| heldout (272) | 71.0 | 71.7 | 71.7 | 73.5 | 73.5 | 72.8 |
| all_distinct (404) | 77.0 | 77.5 | 77.5 | 78.0 | 78.0 | 77.5 |

- **`clean`: three strings, still lost on `main`.** Two are a real bug, a county road with three letters read as a recipient
  (`COUNTY ROAD QQQ`, #377; a guard is planned). One is #297 joining a lowercase initial to the number.
- **`verdicts`, `heldout`, `all_distinct`: a fall on `main` that gives back v0.5.0's gains.** Four addresses (a letter A or B
  before a direction) were gained at v0.5.0 under the number reading and returned under the unit reading. Against
  v0.4.1 the three files are +2, +3 and 0 addresses. This is the #487 convention (these files follow usaddress's
  labelling), not a new parse error.

### Benchmark suite (`compare` track)

Whole suite (19,586), coarse, all records: 92.2% (v0.3.1), 92.3% (v0.4.0, v0.4.1), 93.4% (v0.5.0, v0.5.1), **92.4% (main)**; usaddress
85.5% throughout. The `natural` stratum (16,001) is 98.3, 98.3, 98.3, 98.5, 98.5 and 98.3% in the same order. The gain at v0.5.0 is the rare shapes (the
`hard` stratum 54.6% to 61.8%). The `main` loss is the same letter: 212 strings on `compare`, all a letter A to D after the
number that suite v1 labels as part of the number. Suite v1 is frozen, so that cost is constant and known; **-212 on `compare` is
the #487 convention**, not a regression. Suite v2 will count the letter as right under either labelling
([`benchmark-suite.md`](benchmark-suite.md)).

### Is the loss paid for? Blast radius of each rule (R4)

Each rule since v0.5.1 was run on a 350,000-row sample of the seven sources (50,000 per source) and its changed
rows judged. **No rule changes much outside its own shape, and within the shape at least 74% of the changes are
right at the lower bound,** with these exceptions, all decided on 2026-11-10 and filed as rules:

| Rule | Finding | Decision |
|---|---|---|
| #377 (a county road with letters) | about 68% right (0.52 to 0.81); also cuts lettered route roads (about 600 rows) and names ending in OCEAN or GULF (about 430) | guard (P2) |
| #563 and #523, ranges | a second number a few above the first (`1710 1712 3RD AVE NE`) is read as a unit; 4 plus 2 judged-right cards broken | one range guard serves both (P1) |
| #523, the five-digit join | `23 207 STATION CT` read as `23207`: 94.1% of the shape repeats its first number on the same street (31.0% for true five-digit numbers), so it is a building plus a unit; at most 3 of 37 sample rows right | read as building plus unit (P1) |
| #565, a road number before the road type | 36 of 36 sample rows right | keep |
| #526, #369 | small, one-letter streets and `OLD 25A` | Later |

The cards a person judged under the earlier number-suffix reading (#270) and again under the unit reading (#487) are a decision conflict, not 69
regressions: those 69 verdicts are counted as stale and the 105 made under #487 are kept as its evidence.

### The geocode ceiling

On dev, 2,524 of 3,447 errors are injected by the benchmark itself (split names, doubled road types), 565 are
places no place list holds, 193 are documented conventions and 126 are genuine parse errors (the figures are
for `main`; the classes are in [`benchmarks.md`](benchmarks.md#what-caps-the-geocode-score)). That is why the geocode score is not a target by itself.

## Speed and size

| | v0.3.1 | v0.4.0 | v0.4.1 | v0.5.0 | v0.5.1 | main |
|---|---|---|---|---|---|---|
| Python `parse`, golden-corpus inputs, addresses per second (run 2 of 3, quiet machine) | 54,788 | 66,611 | 65,311 | 57,489 | 104,870 | 103,030 |
| Instructions for 4,000 inputs (callgrind, millions) | | 3,094 | 3,117 | 3,395 | 1,706 | 1,728 |
| CLI binary, release as built (MB) | 5.0 | 5.5 | 6.1 | 6.2 | 5.2 | 5.2 |
| CLI binary, stripped (MB) | 4.4 | 4.6 | 5.1 | 5.2 | 5.0 | 5.0 |
| Wheel (MB) | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 |

- **v0.5.0 is 8.9% more instructions than v0.4.1; v0.5.1 is 49.8% fewer than v0.5.0.** The extra tokenizer and tagger passes of the `k4`
  were accepted; the engine work of 0.5.1 won it back and more ([`speed-and-size.md`](speed-and-size.md)).
- **Since v0.5.1 `main` is +1.3% instructions** (1,706 to 1,728 million), in small steps: #494 +0.77% (the `missing_city`
  diagnostic for placeholder cities, intended, #468), #522 +0.20%, #526 +0.21%, #557 +0.14%, with #523 and #564 giving some back. No step is above the 2% threshold.
- **The binary grew 1.2 MB from v0.3.1 to v0.5.0** (the state data was folded into the core in 0.4.0, the `k4` tables in 0.5.0) and gave 1.0 MB back in 0.5.1 (release as built). The wheel did not move.
- The crate package is 0.8 MB in every build.

## What the keys did

Rows whose property key changed, over the run's 1,000,000 NAD rows, 1,138,982 Netsyms rows and the five other
key-comparison sources (a subset of the full sources):

| Step | Keys changed | Largest source (share) | Sources with 50 or more changes |
|---|---|---|---|
| v0.3.1 to v0.4.0 (`k3`) | 482,869 | ny-corps (69%) | 7 of 7 |
| v0.4.0 to v0.4.1 | 0 | | |
| v0.4.1 to v0.5.0 (`k4`) | 127,869 | ny-corps (37%) | 7 of 7 |
| v0.5.0 to v0.5.1 | 0 | | |
| v0.5.1 to `main` (the 0.6.0 rules, `k5`, 17 steps) | 96,666, summed over the steps (a key can change twice) | #562 alone: 17,511, ny-corps (94%) | |

**The `k3` and `k4` releases changed what they said they would; the 0.4.1 and 0.5.1 releases changed no key**, as promised. Between v0.5.1 and `main`, four rule steps put at least 90%
of their changed keys in one source (#507 95% Netsyms, #515 98% FMCSA, #556 99% Netsyms, #562 94% New York corporations). That is the pattern
the over-tuning check watches for: a rule seen in one source may be that source's quirk. The review (R7) kept all four. The per-step table is in the run's
`summary/key-changes.tsv`; it is not copied here.

Across the whole run, people had judged 105 rows right that v0.5.0 changed from v0.4.1; most were the letter reading (see above).

## Over-tuning and the held-out data

The geocode `train20` split was never read. It lost 0.1 (94.1 to 94.0) from v0.3.1 to `main`, `train80` (fitted) 0.2, `dev` 0.1 and `test` 0.1, and usaddress did not move. There is no sign the rules fit the
data they were made from. The two checks that would show it, the held-out split and the share of each step in one source, are both clean or explained above.

## Other checks in the run

- **Determinism:** the WebAssembly build and the native tool agree on all 30 output columns, and one thread agrees with thirteen on keys,
  warnings and unit fields, on 10,000,000 rows (0 differ).
- **Fuzzing:** 7,287,243 runs in 7,201 seconds on the parser, 0 crash artifacts.
- **Changed-rows queue:** 319,008 rows changed between v0.5.1 and `main` in key, unit or warnings; 191,702 were excluded as the
  `missing_city` diagnostic and 30,433 as the letter move, leaving 96,873 for review (#583).

## What was decided

Recorded 2026-11-10 on #586; the rules are issues in the 0.6.0 milestone (the `k5`, tracker #416) or in Later.

- **Guards for #377, the ranges (#563, #523), #523's five-digit join, a regional `<NAME> ROAD n` rule and a placeholder digit run on line 2.**
- **Keep** #565, #364, #370, #507, #515, #556 and #562.
- **The #487 letter reading stays.** Split names are out of scope: no read-through rule, a benchmark note only.
- **Suite v1 stays frozen;** v2 counts the letter as a convention.
- **A release tolerance** for the benchmarks: [`change-checklist.md`](change-checklist.md#release-tolerance-for-the-benchmarks).

## What this page does not say

- The accuracy figures are on benchmarks that inject their own errors or follow one tool's labelling; read them with
  [`benchmarks.md`](benchmarks.md) and [`usaddress-compat.md`](usaddress-compat.md). A fall that is a convention is not a parse error.
- Counts of rows are from sources that are not a random sample of addresses (see [`data-policy.md`](data-policy.md)); the
  key-comparison set is 1,000,000 NAD and 1,138,982 Netsyms rows, a subset of the full sources, and sample-based precisions
  carry the interval given with them in the issue.
- The speed rows come from one quiet machine (Intel Core i9-9900K, WSL2); the instruction counts are machine-independent.
- This run's `main` is `4b07638`. Later builds are not in it.
