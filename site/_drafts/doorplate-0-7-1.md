---
layout: post
title: "doorplate 0.7.1: the beta, better Puerto Rico, and what happens now"
description: "doorplate 0.7.0 is the first beta and 0.7.1 is a speed release on top of it. Puerto Rico addresses read much better, the state packs are gone, and the project now needs users more than it needs rules."
date: 2026-11-23
tags: [python, rust, address-parsing, open-source, puerto-rico]
---

[doorplate](https://github.com/jeremeybingham/doorplate) 0.7.1 is out. It is the first release after the **beta**: 0.7.0 made doorplate a beta, and
0.7.1 adds speed on top of it with no change to what any address parses to. Together they bring more accuracy and more speed, and much better handling
of addresses in Puerto Rico. doorplate is an open-source US address parser written in Rust, with a
[Python package](https://pypi.org/project/doorplate/) and a [command-line tool](https://crates.io/crates/doorplate-cli).

*doorplate parses and formats addresses. It does not validate that an address exists or can receive mail.*

## The state packs are gone

After no breaking changes to the API for several releases, 0.7.0 made the last one I plan: it removed the "state packs". A state pack was a separate data
structure for state-specific rules, and Florida was its only user. It was an unnecessary and outmoded idea. What Florida still needed moved into the core as
ordinary place names, and so did 46 new New York City neighborhood names (a line like `100 EXAMPLE AVE, BRONX, NEW YORK, NY 10451` now keeps `BRONX` as
the city). Future places are handled the same way: a row in the place list, with its evidence. Anyone who needs specific output or special handling can
still use a custom layer.

If you read `state_data_version` from the diagnostics, the Python object or the JSON, it is gone. No parse output changed with it.

## The beta

From 0.7.0 the public API, the command-line options and the warning codes are stable. A name changes only after a deprecation announced one release ahead,
and a new key version (the 0.7 series is `k6`) comes only in a minor release, never in a patch. The rules are in
[`docs/api-surface.md`](https://github.com/jeremeybingham/doorplate/blob/main/docs/api-surface.md). If you store keys, store the `k6:` prefix with them: a `k5`
key does not match a `k6` key, so re-parse to re-key.

## More accurate

0.7.0 added a long list of rules (the [changelog](https://github.com/jeremeybingham/doorplate/blob/main/CHANGELOG.md) has each one), each measured against the keys of the build before it merged. Compared with 0.6.2 on 36.9 million rows from seven private
sources, the keys changed on about 48,000 rows, and each changed shape traces to one rule. The rules cover glued words (`123 OAKBLVD`, `POBOX481`, `123 5THST`),
names and attention lines ahead of a street or a box, `STAR RT` routes, ranges like `3 & 5 E 41ST STREET`, and Puerto Rico.

On the [parser showdown](https://github.com/jeremeybingham/address-parser-showdown), which scores doorplate, usaddress and libpostal on one hand-labeled golden set
and four outside sets, the published 0.7.0 wheel scores a Parser Score of **91.8** (90.7 to 92.9), against 90.9 for 0.6.2, 84.7 for usaddress and 80.8 for
libpostal. The gain is on the hard and nightmare tiers of the golden set (hard 91.2% to 92.4%, nightmare 69.0% to 73.0%); on ordinary address lines the three
parsers are close, and on the random public stratum doorplate and usaddress cannot be told apart at that size. 0.7.1 scores exactly the same as 0.7.0, because
every prediction is byte for byte the same. The author built the showdown, which is a conflict of interest that the
[report](https://github.com/jeremeybingham/address-parser-showdown/blob/main/report/REPORT.md) describes with its method; every prediction file is published.

## Puerto Rico

Addresses in Puerto Rico have shapes the rest of the country mostly lacks, and doorplate read many of them badly. 0.7.0 adds rules for the common ones:

- the number after the street, `CALLE LUNA 123`, and lettered numbers like `A-17 CALLE AMAPOLA`;
- Spanish box and route words: `APARTADO 825` is PO Box 825, and `RUTA RURAL 3 BUZON 12` is `RR 3 BOX 12`;
- condominium and residencial building lines: `COND VISTA REAL TORRE 2 APT 905` is the street `COND VISTA REAL`, building `2`, apartment `905`;
- `PR 462` as a road in Texas and the Puerto Rico highway in Puerto Rico.

The measure is the share of Puerto Rico rows that get a warning other than a missing city, state or ZIP. On a fixed sample of real Puerto Rico rows from public sources it fell from **45.4% to 38.2%** between 0.6.2 and 0.7.0 (FMCSA 54.3% to 43.0%, IRS 23.6% to 18.7%). It did not move on Netsyms
(53.0% to 52.9%), and a control sample from outside Puerto Rico showed no comparable change. That is better, not finished: standalone urbanization names
(`URB`, `VILLA`, `BO`) and some building lines are still open, and they are in the issue log.

## Faster

0.7.0's rules cost about 7% more time per parse than 0.6.2 (4.3% more instructions). 0.7.1 takes it back and a little more: on the pinned loop a parse takes
5.76 µs, against 6.39 µs for 0.7.0 and 6.06 µs for 0.6.2, about 10% and 5% less. The work was skipping scans that cannot match (the unit rules on a line whose
end rules out a unit, the box and route rules on a line with no box word, the tokenizer's join passes on a line with no hyphen or comma) and reusing buffers
instead of allocating them (a parse makes several allocations fewer). Every step was checked against the 0.7.0 build: the output hash of the
suite inputs is equal, and the seven-source key comparison has 0 changed keys, warnings or unit fields. The showdown's releases appendix timed the published
wheels at 113,770 strings per second in one process for 0.7.1 and 105,833 for 0.7.0, in sessions of their own, so read the ratios and not the digits.

There is one new option: `to_reso(suffix_form="word")` writes the RESO 2.1 `StreetSuffix` word (`Street`) instead of the Pub 28 abbreviation (`ST`). The default is unchanged.

## What happens now

Now that doorplate is in beta, development will slow significantly. I do not expect further significant API changes. Every issue left in the issue log affects
roughly 2,500 rows or fewer of the 290 million I test against. I suspect that meaningful new improvements will now come only from real user feedback and bug
reports, or from new data sets with specific quirks, as opposed to new-shaped human errors that I reproduce at a rate I can detect.

The best thing for the project now is users, so that is what doorplate will focus on for the near future. Please try it in your project and tell me how it
goes, especially if you find a problem. A bug report with an address is the most useful thing you can send; `doorplate anonymize` keeps the shape of an address
and changes the digits and names, so you can send the shape without sending the address.

## What this does not prove

The accuracy and speed figures are measured on one machine (an Intel Core i9-9900K under WSL2) and on particular address mixes, not promises about yours. The
[benchmarks page](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md) and the
[speed page](https://github.com/jeremeybingham/doorplate/blob/main/docs/speed-and-size.md) have every figure with its build and method.

```sh
pip install -U doorplate
```
