---
layout: post
title: "Parsing messy US addresses in Python: doorplate vs usaddress"
description: "A rules-and-data US address parser in Rust with Python bindings, compared with usaddress on a public benchmark: 92.6% vs 88.1% whole-address accuracy, about 5x faster per call, with RESO and USPS Pub 28 output."
date: 2026-10-18
tags: [python, rust, address-parsing, usps, reso, real-estate, mls]
---

If you work with MLS feeds, county exports or mailing lists, you have met the same
address written five ways. `123 N. Main St #4`, `123 north main street apt 4` and
`123 N MAIN ST UNIT 4` are one door, and joining records on them is where projects
stall. I built [doorplate](https://github.com/jeremeybingham/doorplate) to turn all
three into the same components, the same output and the same match key. This post
covers what it does, how it compares with `usaddress`, and where it falls short.

*doorplate parses and formats addresses. It does not validate that an address exists
or can receive mail.*

## What it gives you

```python
import doorplate

a = doorplate.parse("123 north main street apt 4, Miami FL 33101")
a.street_name, a.unit_number      # ("MAIN", "4")
a.to_usps()["line1"]              # "123 N MAIN ST APT 4"       (USPS Pub 28)
a.to_display()["line1"]           # "123 N Main St Apt 4"       (mixed case, display only)
a.to_reso()                       # RESO Data Dictionary 2.0 fields
a.key()                           # "k1:S|123|N|MAIN|ST||FL|33101"
a.warnings                        # []
```

- **Components** for one line or pre-split fields: street number, directionals, name,
  suffix, units, city, state, ZIP, plus PO boxes, rural and highway routes, and military
  and general-delivery forms.
- **USPS Publication 28** and **RESO Data Dictionary 2.0** output.
- A **canonical match key** that uses the street, state and ZIP (not the city), and is
  versioned (`k1:`) so a changed key never silently replaces an old one.
- **Warnings** with stable codes (`missing_zip`, `unparsed_remainder`, ...) so you can
  send doubtful rows to review.
- pandas and Polars helpers, a batch call that releases the GIL, and a command-line
  tool for CSV files.

## How it differs from usaddress

`usaddress` is a learned model: a conditional random field tags each token. doorplate
is rules plus data: the Pub 28 tables, a national place and ZIP list, and optional
state packs. The last line (ZIP, state, city) is read right to left, then the delivery
line from both ends, and the place list tells a city from street words when there are
no commas.

That has practical effects. The same input gives the same output on every platform. A bad address is fixed by adding a rule or a line of data,
not by retraining. And there is no model file to download: the wheel is 1.7 MB against
4.8 MB for usaddress and its dependencies.

## Accuracy

I measured both on the public
[geocoding address-parsing benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark):
one-line US street addresses with injected typos and variants, labeled by token.
Neither library was trained on it. A whole address counts as right only when every
token is.

| Whole address, coarse labels | Addresses | doorplate | usaddress |
|---|---|---|---|
| dev split | 60,522 | **92.6%** | 88.1% |
| train split | 148,173 | 92.5% | 88.1% |
| test split | 30,622 | 96.4% | 88.2% |

Read the dev figure as the estimate. I wrote doorplate's rules and place list while
reading the *test* split's errors, so 96.4% is optimistic; the dev and train splits
were not read for that and agree with each other to 0.1 point. The gap is mostly
city names the place list does not know (neighborhoods and communities), which is the
next thing to fix, and the one label where usaddress still scores higher.

The benchmark has street addresses only: no units, PO boxes or routes. It cannot tell
you how either parser does on your data, which is why I would like yours (below).

## Speed

On one machine (i9-9900K, Python 3.13, 100,000 addresses):

| | doorplate | usaddress |
|---|---|---|
| One address, `parse` | 17 µs | 83 µs |
| 100,000 addresses, `parse_many` (all cores) | 0.26 s | 8.3 s |

The first row is one thread against one thread, about 5x. The second uses every core
with the GIL released against a single-threaded loop, so it is not a like-for-like
comparison; it is what you get from calling `parse_many`. The core is Rust, and the
Python package is a thin PyO3 binding.

## Where it falls short

It is an alpha. Keys will probably get new versions as the parser improves, so store
the `k1:` prefix with your keys. Some shapes are not modeled: recipient lines,
landmarks, street corners and international addresses. Apostrophes are dropped by the
parse, so `O'Brien` displays as `Obrien`. All of this is in the
[docs](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md), with
the method and the commands to rerun every number.

## Send me your messy addresses

The rules get better with real, messy data: odd abbreviations, units in strange places,
cities cut off at 30 characters. If doorplate parses yours badly,
[open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md)
with a sample. If the data is private, keep the shape and swap the names, numbers and
places; there is a
[guide](https://github.com/jeremeybingham/doorplate/blob/main/CONTRIBUTING.md#sharing-messy-data).

```sh
pip install doorplate     # or: cargo add doorplate
```
