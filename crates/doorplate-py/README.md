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

> **Alpha release (0.6.0).** Expect rough edges; names in the API and the warning codes may still change before 1.0.
> The match key is versioned (`k5:`) and later versions will probably change it, so store
> the prefix with your keys and plan to re-key. `k5` has only been checked on the project's own data (public records). Accuracy and speed are measurements on a few datasets, not guarantees.
>
> **Help wanted: messy addresses.** If it parses your addresses badly (odd abbreviations, typos, cut-off lines, units in
> strange places, county or mailing-list exports), please
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
a.street_name, a.unit_number   # ("MAIN", "4")
a.to_usps()["line1"]           # "123 N MAIN ST APT 4"
a.key()                        # "k5:S|123|N|MAIN|ST||FL|33101"
a.slug()                       # "123-n-main-st-apt-4-miami-fl-33101"
a.warnings                     # []

dp.parse_fields(line1="THE COVE", line2="1111 ASBURY WAY", city="Orlando", state="FL", zip="32801")
dp.parse_many(["1 Main St, Miami FL", "PO Box 5, Tampa FL"])  # GIL released
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

## Guides

- [Python guide](https://doorplate.readthedocs.io/en/latest/python/) (the tour) and [Python reference](https://doorplate.readthedocs.io/en/latest/python-api/) (every function and class).
- [pandas, Polars and DuckDB](https://doorplate.readthedocs.io/en/latest/dataframes/): a column, split fields, a table or a CSV file, one call per shape. `parse_many` uses every core with the GIL released.
- [Custom layers](https://doorplate.readthedocs.io/en/latest/custom-layers/): `doorplate.load_layer("DIR")` adds your own spellings, words, places and ZIPs; a layer can change a key, so every parse reports it.
- [Anonymizing data](https://doorplate.readthedocs.io/en/latest/anonymizing/): `doorplate.Anonymizer` keeps the shape and loses names and numbers. Obfuscation, not anonymity: read the output before you share it.
- [Coming from usaddress](https://doorplate.readthedocs.io/en/latest/usaddress-compat/): `import doorplate.compat as usaddress` (label compatibility, not identical output).

## Accuracy and speed

| 0.6.0 | doorplate | usaddress |
|---|---|---|
| Whole address right, [benchmark suite](https://doorplate.readthedocs.io/en/latest/benchmark-suite/), `natural` stratum (16,001 addresses written in five styles) | 98.7% | 96.1% |
| Whole address right, [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark) dev split (60,522 one-line addresses) | 94.4% | 88.1% |
| Addresses per second from Python, one thread (suite inputs, 4 CPUs) | about 65,000 | about 9,300 |

Measured against the Python library [usaddress](https://github.com/datamade/usaddress) on a few data sets, not promises for
yours; every figure by build, the caveats and how to rerun them: [benchmarks](https://doorplate.readthedocs.io/en/latest/benchmarks/)
and [speed, size and memory](https://doorplate.readthedocs.io/en/latest/speed-and-size/).

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
- [Documentation site](https://doorplate.readthedocs.io/en/latest/): the [key](https://doorplate.readthedocs.io/en/latest/key-format/), [warnings](https://doorplate.readthedocs.io/en/latest/warnings/) and [how it works](https://doorplate.readthedocs.io/en/latest/how-it-works/).
- [Project README](https://github.com/jeremeybingham/doorplate#readme): what it does, the Rust library, the command-line tool.
- [Examples](https://github.com/jeremeybingham/doorplate/tree/main/examples): a notebook tour and a pipeline for each DataFrame library.

Licensed under either of MIT or Apache-2.0 at your option.
