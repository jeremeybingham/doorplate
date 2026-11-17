---
layout: post
title: "The parser showdown: doorplate against usaddress and libpostal, on equal terms"
description: "A pinned, repeatable comparison of three US address parsers. doorplate scores 90.9 against 84.7 and 80.8, leads six of the seven scored parts, and parses five to eight times faster in 27 MB. The method, the results and the limits."
date: 2026-11-17
tags: [python, rust, address-parsing, benchmarks, open-source]
---

![Parser Score: doorplate 90.9 (95% interval 89.8 to 92.0), usaddress 84.7 (83.4 to 86.0), libpostal 80.8 (79.5 to 82.2).]({{ site.baseurl }}/assets/showdown-score.png)

Which US address parser is the most accurate, and which is the fastest? I wrote [doorplate](https://github.com/jeremeybingham/doorplate), so my
answer would be worth little unless it came with a method anyone can rerun. So I built one. The
[address-parser-showdown](https://github.com/jeremeybingham/address-parser-showdown) repository compares doorplate, usaddress and libpostal
on one neutral label schema, one hand-labeled test set, one scoring rule and one pinned run. Its
[report](https://github.com/jeremeybingham/address-parser-showdown/blob/main/report/REPORT.md) is the source of every number in this post.

The short version: **doorplate has the highest Parser Score, the highest accuracy on every part of that score except one, and the best speed and memory use
of the three.** The score and the speed were measured, not asserted, and each one comes with an interval, a sensitivity table or a stated limit. The
limits are part of the story, and they have their own section below.

*doorplate parses and formats addresses. It does not validate that an address exists or can receive mail.*

## The method

- **Three parsers, defaults only.** doorplate 0.6.0 (hand-written rules in Rust), usaddress 0.5.16 (a conditional random field) and libpostal with
  Senzing's 1.2.0 model (a perceptron CRF trained on OpenStreetMap and OpenAddresses). Nothing was retrained or tuned. Versions, model checksums and
  every set's SHA-256 are recorded in the run.
- **One schema.** Each parser's labels go through a mapping file into the same eight core fields: house number, street, unit, PO box, route, city,
  state and ZIP. Two conventions that have more than one defensible reading (a letter after the house number, a `#` before a unit) accept both
  readings for every parser. They were fixed before the first run.
- **A strict score.** A record is right only when every field the gold has is predicted with the same character span and label. A parser that labels a
  street only as a whole (libpostal) is not penalized for it.
- **A new golden set.** 2,439 hand-labeled records in three tiers: `normal`, `hard` and `nightmare`. They come from public records (the National Address
  Database, FCC licenses, FMCSA, SBA loans and others), invented hard shapes and real grid and military lines. I labeled it blind, on a page that
  shows only the text, with no parser output. Then I adjudicated disagreements, and the report publishes which way that moved the gold: 20 cards
  toward doorplate's reading, 20 toward usaddress's and 2 toward libpostal's.
- **Neutral sets too.** Four outside sets carry the other half of the score: the doorplate suite (two parts), Senzing's OSM-derived US rows and the
  60,522-string dev split of the geocoding benchmark. Each parser's own test files are reported apart, as home sets.
- **A formula fixed in advance.** The Parser Score is 50% golden (a sixth per tier) and 50% the four neutral parts (an eighth each). The formula was
  committed before the first run and never changed.

## The results

![Record accuracy on every scored part: doorplate leads six of seven. Golden normal 95.0, 93.6, 91.8; hard 91.2, 88.5, 70.9; nightmare 69.0, 51.3, 54.0; suite natural 98.6, 96.5, 95.0; suite hand 95.8, 91.1, 84.0; Senzing US 98.1, 90.6, 98.8; geocode dev 94.4, 88.4, 79.9, in the order doorplate, usaddress, libpostal.]({{ site.baseurl }}/assets/showdown-parts.png)

| | doorplate | usaddress | libpostal |
|---|---|---|---|
| Parser Score (95% interval) | **90.9** (89.8 to 92.0) | 84.7 (83.4 to 86.0) | 80.8 (79.5 to 82.2) |
| Field F1 score | **97.6** | 95.7 | 93.4 |

- **The intervals do not overlap.** doorplate leads by 6.2 points over usaddress and 10.1 over libpostal.
- **The ranking never flips.** The report re-scores with equal weights, with the doubtful records put back, and with each of the golden set, the doorplate
  suite, the geocode split and the Senzing set left out. doorplate is first in every row; without the suite it is 88.8 against 81.7 and 77.9.
- **The harder the address, the wider the gap.** On the golden `hard` tier doorplate reads 91.2% right against 88.5% and 70.9%. On `nightmare` it is
  69.0% against 51.3% and 54.0%. On the geocoding benchmark's dev split, 60,522 strings with real input errors, it is 94.4% against 88.4% and 79.9%.
- **By shape**, the lead is large on rural routes (97.2% against 92.6% and 40.7%), military lines (62.5%, 16.7%, 0.0%) and fraction forms (100%, 71.4%, 85.7%).

## Speed and size

![Five to eight times faster, in 27 MB. Strings per second in one process: doorplate 72,028, usaddress 8,952, libpostal 14,577. Memory after loading: 27, 27, 2,958 MB. Install size: 4.9, 4.8, 2,993.1 MB.]({{ site.baseurl }}/assets/showdown-speed.png)

These figures are never part of the Parser Score. They come from 100,000 strings, the median of five passes.

- **Throughput:** 72,028 strings a second in one process, against 14,577 for libpostal (4.9 times) and 8,952 for usaddress (8.0 times). With four
  processes: 223,510, 43,951 and 28,054.
- **Start-up:** doorplate imports and parses its first address in 0.003 s. usaddress takes 0.012 s and libpostal 3.48 s.
- **Memory and disk:** 27 MB loaded and a 4.9 MB install. libpostal needs 2,958 MB loaded and 2,993 MB on disk. Four libpostal processes together need
  11.8 GB, where four doorplate processes need 37 MB.

## What this does not show

I would rather you hear these from me than find them yourself, and the report lists them all in section 10.

- **doorplate does not win every row.** Each parser leads on its own home test set: usaddress on its own tests, libpostal on its own. On Senzing's
  US rows libpostal is ahead by 0.7 points (98.8 against 98.1). doorplate leads six of the seven scored parts.
- **On ordinary public addresses the three are close.** On the 829 records drawn at random from public records, the scores are 93.7, 93.0 and 91.3.
  doorplate against usaddress is not a significant difference there (p = 0.31); doorplate against libpostal is (p = 0.001). Most of the Parser Score's
  spread comes from rarer shapes: rural routes, military lines, units in odd places and typos. If your data is mostly plain street lines, any of
  the three will do the accuracy job, and speed and memory become the deciding factors.
- **I have a conflict of interest.** I built the repository, labeled the golden set and wrote the report. The mitigations are blind labeling, a
  formula and conventions fixed before the first run, published adjudication direction, every prediction file committed and a cap on how much of the
  hardest tier comes from doorplate's own research. They do not remove it. There was one labeler, so there is no agreement figure.
- **The hardest shapes are not solved by anyone.** Glued text (`8 OakSt Zeller,MO`), glued PO boxes and a letter joined to a house number
  (`31B Cedar St`) are missed by all three. doorplate reads only 26.9% of the `number-letter` class right; the report asks whether my gold reading is
  the right one.
- **Two changes were made after the first run**, both found by reading its results (a scorer fault and 140 highway cards that needed an accepted
  alternative). The first run is kept unchanged and the ranking is the same in both.
- **US addresses only**, in English. libpostal is built for the whole world, and none of this speaks to that. The speed numbers come from one machine.

## Rerun it, or add your own parser

Everything is in the repository. `just rescore runs/2026-11-16` scores the committed prediction files again and `git diff` shows no change; `just all` makes a new
pinned run in about four minutes. A new parser needs an adapter, a mapping file and a pinned version, and its own test files go in as a home set.
If you think a gold label, a mapping or a convention is wrong, an issue there is the most useful thing you can send.

- [Read the full report](https://github.com/jeremeybingham/address-parser-showdown/blob/main/report/REPORT.md) (also as a typeset PDF with eight charts)
- [The methodology and fairness rules](https://github.com/jeremeybingham/address-parser-showdown/blob/main/METHODOLOGY.md)

```sh
pip install -U doorplate
```
