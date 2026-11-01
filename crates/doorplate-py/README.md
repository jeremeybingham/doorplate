# doorplate

[![CI](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml/badge.svg)](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/doorplate.svg)](https://pypi.org/project/doorplate/)
[![Python versions](https://img.shields.io/pypi/pyversions/doorplate.svg)](https://pypi.org/project/doorplate/)
[![PyPI downloads](https://img.shields.io/pypi/dm/doorplate.svg)](https://pypi.org/project/doorplate/)
[![License: MIT OR Apache-2.0](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](https://github.com/jeremeybingham/doorplate#license)

Parse US addresses into components, with USPS Publication 28 and RESO output, a
match key, a URL-safe slug, and diagnostics. A Rust library with Python bindings
(PyO3, abi3 wheels for Python 3.10 and later); no runtime dependencies and no data
to download.

This library formats and parses; it **does not validate** that an address exists or
can receive mail.

> **Alpha release (0.5.0).** Expect rough edges. The match key is versioned (`k4:`) and
> will probably get new versions as the parser improves, so store the version prefix
> with your keys and plan to re-key. `k4` is new in 0.5.0 and has only been checked on the project's own data (37 million rows of public records), and a `k5` is planned for an eventual 0.6.0 release. Accuracy and speed are measurements on a few
> datasets, not guarantees.
>
> **Help wanted: messy addresses.** If it parses your addresses badly, please
> [open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md)
> with a sample. I want to fix them. Private data can be anonymized first
> ([how](https://github.com/jeremeybingham/doorplate/blob/main/CONTRIBUTING.md#sharing-messy-data)).

## Quickstart

```sh
pip install doorplate
```

```python
import doorplate as dp

a = dp.parse("123 north main street apt 4, Miami FL 33101")
a.street_name          # "MAIN"
a.unit_number          # "4"
a.place                # {"name": "MIAMI", "state": "FL", "county": "DADE", ...}
a.warnings             # []
a.to_usps()["line1"]   # "123 N MAIN ST APT 4"
a.to_display()["line1"]  # "123 N Main St Apt 4" (to_long(): "123 North Main Street Apartment 4"); display only, not Pub 28
a.key()                # "k4:S|123|N|MAIN|ST||FL|33101"
a.slug()               # "123-n-main-st-apt-4-miami-fl-33101"
a.to_reso()            # RESO Data Dictionary 2.0 fields
a.to_dict()            # everything above as plain Python values, and provenance (the library version and the state data version; also `a.library_version`, `a.state_data_version`)

dp.parse_fields(line1="THE COVE", line2="1111 ASBURY WAY",
                city="Orlando", state="FL", zip="32801")
dp.parse_many(["1 Main St, Miami FL", "PO Box 5, Tampa FL"])  # GIL released
dp.parse_fields_many(line1=["1 Main St", "PO Box 5"], city=["Miami", "Tampa"])
dp.parse("281 EVELYN DR DOTHAN", default_state="AL").city     # "DOTHAN"
```

- Unusable input (no address text at all) raises `ParseError`, a `ValueError`; in
  `parse_many` that element is `None`. Anything else comes back with `warnings` ([what each one tells you, and how often it is wrong](https://github.com/jeremeybingham/doorplate/blob/main/docs/warnings.md)).
- `default_state` is a lookup hint for input with no state; it never fills `state`.
  A value that is not a US state, DC or territory raises `ValueError`.

## Install

```sh
pip install doorplate                  # the parser
pip install "doorplate[pandas]"        # plus the pandas helper
pip install "doorplate[polars]"        # plus the Polars helper
pip install "doorplate[duckdb]"        # plus the DuckDB functions (DuckDB and PyArrow)
```

Python 3.10 or later. Wheels are built for Linux (x86_64, aarch64), macOS
(universal2) and Windows (x64), and tested on Python 3.10 and 3.13. To build from
source (Rust 1.83 or later):

```sh
pip install maturin
cd crates/doorplate-py
maturin develop --release      # builds the extension into your virtualenv
pytest tests
```

## The API
The calls are `parse`, `parse_fields`, `parse_many`, `parse_fields_many`, `Parser`, `tag`, `parse_tokens`,
`load_layer`, `Anonymizer` and `address_type`; a `ParsedAddress` is read-only and typed (`py.typed`), with the components,
`warnings`, `unparsed`, and `key()`, `slug()`, `to_usps()`, `to_display()`, `to_reso()` and `to_dict()`. The tour is the
[Python guide](https://doorplate.readthedocs.io/en/latest/python/); every function and class is in the [Python reference](https://doorplate.readthedocs.io/en/latest/python-api/).

## Your data, by shape
A column of addresses in pandas, Polars or DuckDB, split columns, mixed shapes, a CSV file: see
[pandas, Polars and DuckDB](https://doorplate.readthedocs.io/en/latest/dataframes/) (one call per shape, with timings), or the examples in the repository.

## Batches, pandas, Polars and DuckDB
`parse_many(texts)` parses a list on every core with the GIL released (about 3x a loop of `parse`), and the helpers
`doorplate.pandas.parse_column`, `doorplate.polars.parse_column` and `doorplate.duckdb` build on it:

```python
from doorplate.polars import parse_column   # or doorplate.pandas

out = df.hstack(parse_column(df["address"]))                    # Polars
out = df.join(parse_column(df["address"], default_state="FL"))  # pandas
```

The columns, DuckDB in SQL, doing it by hand and the timings are in [pandas, Polars and DuckDB](https://doorplate.readthedocs.io/en/latest/dataframes/).

## Custom layers
Your data spells `TRAIL` as `TRAYL`, or lives in a place the shipped list lacks? `doorplate.load_layer("DIR")` adds your own
spellings, words, places and ZIPs on top of the shipped tables (`custom_layer=` on every call). A layer can change a key, so
every parse reports it. The files, the rules, a demo layer, a template and a prompt for an LLM are in
[Custom layers](https://doorplate.readthedocs.io/en/latest/custom-layers/).

## Sharing messy data
`doorplate.Anonymizer(seed=None).anonymize("123 N Zephyrmill Ave Apt 4, Miami, FL 33101")` gives a copy that keeps the shape and
loses the names and numbers, even when the text does not parse. **It is obfuscation, not anonymity:** read the output before
you share it. The rules, the limits and what it can leak are in [Anonymizing data](https://doorplate.readthedocs.io/en/latest/anonymizing/).

## Coming from usaddress
For a script that calls `usaddress.parse` and `usaddress.tag`, change one import (label compatibility, not identical output):

```python
import doorplate.compat as usaddress    # was: import usaddress
```

The same calls under doorplate's own names are `parse_tokens(s)` and `tag(s)`. The mapping and the differences are in
[Coming from usaddress](https://doorplate.readthedocs.io/en/latest/usaddress-compat/).

## Accuracy and speed

| | doorplate | usaddress |
|---|---|---|
| Whole address right, benchmark suite, `natural` stratum (16,001 addresses written in five styles) | 98.5% | 96.1% |
| Whole address right, [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark) dev split (60,522 one-line addresses) | 94.3% | 88.1% |
| Addresses per second, one thread (suite inputs) | about 43,400 | about 9,300 |

The suite is 19,586 labeled addresses that neither library was made from; it also holds both libraries' known blind spots
on purpose, so read its `natural` stratum as the estimate for ordinary input. Speed is on 4 CPUs, 8 GB. These are measurements on a few data sets, not promises for yours. Method and every other figure:
[accuracy](https://doorplate.readthedocs.io/en/latest/benchmarks/) and [speed and size](https://doorplate.readthedocs.io/en/latest/speed-and-size/); how to rerun them: [running the benchmarks](https://doorplate.readthedocs.io/en/latest/running-benchmarks/).

## Disclaimer

doorplate is provided "as is", without warranty of any kind, under the [MIT](https://github.com/jeremeybingham/doorplate/blob/main/LICENSE-MIT) or
[Apache-2.0](https://github.com/jeremeybingham/doorplate/blob/main/LICENSE-APACHE) license at your option; the license text is what governs. In plain
terms: **use it at your own risk.** Nothing here guarantees that a parse, a warning, a match key
or a figure is correct, complete or fit for your purpose. Accuracy and speed numbers are
measurements on particular datasets, not promises for yours. doorplate parses and formats
addresses; it does **not validate** that an address exists or can receive mail, and Pub 28
formatting is not certified validation. Check its output before you rely on it for anything with
legal, financial, safety or delivery consequences.

doorplate is an independent project. It is not affiliated with, endorsed by or certified by the
US Postal Service, RESO, DataMade (the authors of usaddress) or any data source it cites; those
names are used only to say what the output follows or is compared with.

## More
- [Documentation site](https://doorplate.readthedocs.io/en/latest/): the [Python guide](https://doorplate.readthedocs.io/en/latest/python/), [reference](https://doorplate.readthedocs.io/en/latest/python-api/), [pandas, Polars and DuckDB](https://doorplate.readthedocs.io/en/latest/dataframes/), the [key](https://doorplate.readthedocs.io/en/latest/key-format/), [warnings](https://doorplate.readthedocs.io/en/latest/warnings/) and [how it works](https://doorplate.readthedocs.io/en/latest/how-it-works/).
- [Project README](https://github.com/jeremeybingham/doorplate#readme): what it does, the Rust library, the command-line tool.
- [Examples](https://github.com/jeremeybingham/doorplate/tree/main/examples): a notebook tour and a pipeline for each DataFrame library.

Licensed under either of MIT or Apache-2.0 at your option.

