---
layout: post
title: "Introducing doorplate"
description: "doorplate is an open-source US address parser in Rust with a first-class Python package and a command-line tool: components, USPS Publication 28 and RESO output, a stable match key and warnings. Version 0.4.0, an alpha that needs your messy addresses."
date: 2026-10-21
tags: [python, rust, address-parsing, usps, reso, real-estate, mls]
---

[doorplate](https://github.com/jeremeybingham/doorplate) is an open-source US address
parser written in Rust, with a [Python package](https://pypi.org/project/doorplate/) and a [command-line tool](https://crates.io/crates/doorplate-cli). Give it an address,
as one line or as separate fields, and it returns the components, [USPS Publication 28](https://pe.usps.com/text/pub28/) and
[RESO Data Dictionary 2.0](https://www.reso.org/data-dictionary/) output, a stable match key, and warnings that say when it is not
sure. It is version 0.4.0, an alpha, and I am announcing it now because it gets better
with real, messy addresses and with people who use it.

*doorplate parses and formats addresses. It does not validate that an address exists or
can receive mail.*

**[Try it in your browser](https://jeremeybingham.github.io/doorplate/demo/).** Type an address and
watch doorplate take it apart as you type: each part is colored by what the parser decided it is,
with the warnings, the USPS and RESO output and the match key beside it. The parser runs on your
machine as WebAssembly, so nothing you type is sent anywhere.

## What it is

```python
import doorplate

a = doorplate.parse("123 north main street apt 4, Miami FL 33101")

a.street_name, a.unit_number        # ("MAIN", "4")
a.to_usps()["line1"]                # "123 N MAIN ST APT 4"       (USPS Pub 28)
a.to_reso()                         # RESO Data Dictionary 2.0 fields
a.key()                             # "k3:S|123|N|MAIN|ST||FL|33101"
a.warnings                          # []
```

`123 N. Main St #4`, `123 north main street apt 4` and `123 N MAIN ST UNIT 4` are one door. doorplate turns all three into
the same components, the same output and the same key.

- **Components** for one line or pre-split fields (line 1, line 2, city, state, ZIP): street
  number, directionals, name, suffix, units, plus PO boxes, rural and highway routes, military
  and general-delivery forms, each with its position in the original text.
- **Output:** USPS Publication 28, RESO Data Dictionary 2.0, display forms for showing an
  address to a person, and usaddress-shaped labels if you are coming from that library.
- **Identifiers for databases:** a versioned match key and a URL-safe slug.
- **Diagnostics:** stable warning codes (`missing_zip`, `unparsed_remainder`, ...) and the text
  it could not place, so a pipeline can send doubtful rows to review instead of guessing.
- **Connections for big data:** `parse_many` runs in parallel with the Python GIL released,
  and there are [pandas](https://pandas.pydata.org/), [Polars](https://pola.rs/) and [DuckDB](https://duckdb.org/) helpers and a CSV command (`doorplate parse-file`).
  A full run over 146.6 million US rows of one address database took about 20 minutes on one
  machine and parsed every row.

It is deterministic and rule-based: rules plus data (the Pub 28 tables and a national place
list that tells a city from street words on a line with no commas), with no statistical model,
no training and no model file. Parsing never panics, and the default build has no runtime
dependencies and downloads nothing, so there are no transitive dependencies to audit or patch.

### How it compares with usaddress

[usaddress](https://github.com/datamade/usaddress) is the standard open-source choice in Python. On the [benchmarks](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md) in the repository (whole address right, coarse labels):

| | doorplate | usaddress |
|---|---|---|
| Benchmark suite, `natural` stratum (16,001 addresses) | 98.3% | 96.1% |
| Benchmark suite, whole suite (19,586) | 92.3% | 85.5% |
| [Geocode benchmark](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md#geocode-benchmark-one-line-no-commas), `dev` split (60,522) | 94.5% | 88.1% |
| usaddress's own regression tests (2,248 addresses) | 99.2% | **100.0%** |
| Addresses per second, one thread | 38,305 | 8,937 |
| Addresses per second, `parse_many`, 4 threads | 152,376 | (no batch call) |
| Installed size | 1.8 MB | 4.8 MB |
| Import time | 1 ms | 10 ms |

Read this with care. The benchmark suite is my own, built from public National Address Database
rows rendered in several styles, frozen and audited, with its blind spots left in on purpose
([how it was made](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmark-suite.md)).
On usaddress's own regression tests, usaddress wins, as you would expect; the gap there shows
where the two choose differently, not an accuracy contest. The rules were tuned against one
geocode split and checked on another. doorplate leaves some things unparsed on purpose
(recipient names, landmarks, street corners) and is weak on a few shapes, such as a number
prefix like `W 615`. The full tables, the weak spots and how to rerun everything are in
[the benchmarks page](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md).

## Who it is for

Any project that needs reliable US address parsing without a heavy dependency: a script that
cleans a county export, a listing or MLS feed, a mailing list, or a pipeline at institutional
scale. It is small enough to drop in (a 1.8 MB wheel, a 1 ms import), fast enough for large
files, and extensible through the pandas, Polars and DuckDB connectors. It is not for address
validation or deliverability, geocoding, fuzzy matching or international addresses.

## Why I built it

It is a problem I understand well. I have spent years in real estate data, where the same
address arrives from every source written a different way. The only native Rust parser I found is a 2021 port of usaddress, and Rust is fast and safe, so I made the Python package a first-class citizen
and the library easy to adopt from either side.

[usaddress](https://github.com/datamade/usaddress) is the standard open-source choice in Python, and it is good at what it does:
labeling tokens. It does not produce USPS Publication 28 or RESO output; that takes a second
library such as [usaddress-scourgify](https://pypi.org/project/usaddress-scourgify/). I wanted one library that goes from raw text to normalized output and a key.

I also bet that a deterministic parser was the right architecture. Address parsing is a
bounded problem that rewards a great many small decisions and a close look at patterns in
large datasets, which I thought would suit an LLM-assisted workflow. The result,
on my own and independent benchmarks, is more accurate and faster, with the caveats above.

## How it was built

I drove the project with my own domain knowledge, which is how I keep the model pointed in the
right direction: what a real address looks like, which warnings a data pipeline needs, which
decisions should be rules and which should be left alone. The coding was done with Claude
(Sonnet 5.5, and occasionally Opus 5.5) through Claude desktop, in an Ubuntu environment on WSL,
with the repository and a `local-data` folder of the actual address files we parse.

Those files are what keep the rules honest. A harness runs the parser over a source, counts the
warnings and the unparsed remainders, and ranks the shapes that fail. Each lead is reproduced
with an invented address, given a source (Pub 28 or the data itself), and only then becomes a rule
with a test. About **204 million rows** have been parsed in this way, from public or open sources:

| Source | Rows parsed |
|---|---|
| An aggregated US address database | 146.6 million |
| A state voter file (current, and a snapshot with the address in labeled parts) | 16.2 million; 20.9 million |
| The federal motor carrier census | 9.0 million |
| A state business registry | 5.9 million |
| The IRS list of exempt organizations | 2.0 million |
| A federal radio-license list | 1.7 million |
| The National Address Database (a 1-million-row sample of 99.2 million) | 1.0 million |
| A state licensing list | 0.2 million |

The totals overlap, so they are an upper bound on distinct addresses. Nothing is trained on this
data, none of it is redistributed, and no row or name ever leaves the machine: only counts,
shapes and invented examples do ([the data policy](https://github.com/jeremeybingham/doorplate/blob/main/docs/data-policy.md)).

## About me

I am Jeremey Bingham. I have worked in technology since 2007, with Python for about ten years
and Rust for about two. I spent years inside real estate data: the Realtor Association of the
Palm Beaches and [BeachesMLS](https://www.beachesmls.com/), the [Massachusetts Association of Realtors](https://www.marealtor.com/), where I was Director of
Information Technology, and [HouseCanary](https://www.housecanary.com/), where I built APIs over residential property records. I
also published [reso-client](https://github.com/jeremeybingham/reso_client), a Rust client for the
RESO Web API. My resume is at [resume.jeremeybingham.com](https://resume.jeremeybingham.com).

## Where to find it

- Source and issues: [github.com/jeremeybingham/doorplate](https://github.com/jeremeybingham/doorplate)
- Python: [pypi.org/project/doorplate](https://pypi.org/project/doorplate/) (`pip install doorplate`)
- Rust: [crates.io/crates/doorplate](https://crates.io/crates/doorplate) and the command-line
  tool [crates.io/crates/doorplate-cli](https://crates.io/crates/doorplate-cli)
- How it works: [the docs](https://github.com/jeremeybingham/doorplate/blob/main/docs/how-it-works.md)
- For comparison: [usaddress](https://github.com/datamade/usaddress) and
  [usaddress-scourgify](https://pypi.org/project/usaddress-scourgify/)

## When, and what is next

doorplate 0.4.0 is available now and is an alpha. The match key is versioned, so store the
version prefix with your keys and plan to re-key as the parser improves, and names in the API
and warning codes may still change before 1.0. I plan to keep developing it if there is activity,
users and interest.

What it needs most is users and messy data, especially addresses it parses badly: odd
abbreviations, typos, cut-off lines, units in strange places, county and mailing-list exports. If
it gets yours wrong,
[open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md)
with a sample; private data can be anonymized first
([how](https://github.com/jeremeybingham/doorplate/blob/main/CONTRIBUTING.md#sharing-messy-data)).

Later, and if there is demand: a way to add your own
spellings and places at run time, and data for more states. The full list is in the
[roadmap](https://github.com/jeremeybingham/doorplate/blob/main/docs/roadmap.md).
