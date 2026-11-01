# doorplate

[![CI](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml/badge.svg)](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jeremeybingham/doorplate/graph/badge.svg)](https://codecov.io/gh/jeremeybingham/doorplate)
[![crates.io](https://img.shields.io/crates/v/doorplate.svg)](https://crates.io/crates/doorplate)
[![crates.io downloads](https://img.shields.io/crates/d/doorplate.svg)](https://crates.io/crates/doorplate)
[![doorplate-cli on crates.io](https://img.shields.io/crates/v/doorplate-cli.svg?label=doorplate-cli)](https://crates.io/crates/doorplate-cli)
[![doorplate-cli downloads](https://img.shields.io/crates/d/doorplate-cli.svg?label=doorplate-cli%20downloads)](https://crates.io/crates/doorplate-cli)
[![docs.rs](https://docs.rs/doorplate/badge.svg)](https://docs.rs/doorplate)
[![PyPI](https://img.shields.io/pypi/v/doorplate.svg)](https://pypi.org/project/doorplate/)
[![Wheels](https://github.com/jeremeybingham/doorplate/actions/workflows/wheels.yml/badge.svg)](https://github.com/jeremeybingham/doorplate/actions/workflows/wheels.yml)
[![License: MIT OR Apache-2.0](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](#license)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](crates/doorplate-py/README.md)
[![Rust 1.80+](https://img.shields.io/badge/rustc-1.80%2B-orange.svg)](Cargo.toml)

Parse US addresses into components, with USPS Publication 28 and RESO output, a canonical
match key, a URL-safe slug, and diagnostics. A Rust library with a Python package and a
command-line tool (abi3 wheels for Python 3.10 and later); no runtime dependencies, no data
to download, no machine-learned model, and parsing never panics.

**[Try it in your browser](https://jeremeybingham.github.io/doorplate/demo/)**: type an address and watch it
be taken apart, with the output, as you type, or drop in a CSV file and download it with the parsed columns added (the
columns of `doorplate parse-file`). The parser runs on your machine; nothing is sent anywhere.

This library formats and parses; it **does not validate** that an address exists or can
receive mail. Pub 28 formatting is not deliverability, and validation needs
postal-service-certified data; warnings such as `zip_city_mismatch` are hints about the
input, not verdicts.

> **Alpha release (0.5.0).** Expect rough edges. This documentation may be outdated in places, describe features from pre-release versions, or just be overly wordy and dense. A documentation edit/update is coming soon, as of 11/1/2026. The match key is versioned (`k4:`) and
> will probably get new versions as the parser improves, so store the version prefix
> with your keys and plan to re-key. `k4` is new in 0.5.0 and has only been checked on the project's own data (37 million rows of public records), so a `k5` may follow. Accuracy and speed are measurements on a few
> datasets, not guarantees. Names in the API and the warning codes may still change
> before 1.0.
>
> **Help wanted: messy addresses.** If it parses your addresses badly (odd abbreviations,
> typos, cut-off lines, units in strange places, county or mailing-list exports), please
> [open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md)
> with a sample. I want to fix them. Private data can be anonymized first
> ([how](CONTRIBUTING.md#sharing-messy-data)).

## Quickstart

```sh
pip install doorplate
```

```python
import doorplate

a = doorplate.parse("123 north main street apt 4, Miami FL 33101")

a.street_name, a.unit_number        # ("MAIN", "4")
a.to_usps()["line1"]                # "123 N MAIN ST APT 4"
a.key()                             # "k4:S|123|N|MAIN|ST||FL|33101"
a.slug()                            # "123-n-main-st-apt-4-miami-fl-33101"
a.to_display()["line1"]             # "123 N Main St Apt 4" (mixed case, display only)
a.warnings                          # []
```

The same from the command line, and the same address written another way gives
the same key:

```sh
$ doorplate parse "123 N. Main St #4, miami, fl 33101" --usps
123 N MAIN ST # 4
MIAMI FL 33101
$ doorplate parse "123 N. Main St #4, miami, fl 33101" | jq -r .key
k4:S|123|N|MAIN|ST||FL|33101
```

## Features

- **Any shape of address.** Street addresses with directionals, suffixes, units and a second unit; PO boxes;
  rural and highway-contract routes; military and general delivery; highways with a state or county prefix;
  intersections and care-of lines are recognized and set apart. Missing pieces (no ZIP, no state, no commas)
  parse, with a warning that says what is missing ([what each warning tells you](docs/warnings.md)).
- **One line or separate fields.** `parse` takes a single string; `parse_fields` takes `line1`, `line2`, `city`,
  `state` and `zip` as your data has them, in whatever combination is filled in.
- **Output you can load.** Components, USPS Publication 28 lines, RESO Data Dictionary 2.0 fields, a display
  form for people, usaddress-style labels, a canonical match key (`k4:...`), a URL-safe slug.
- **Diagnostics.** Stable warning codes and the text it could not place, so doubtful rows go to review instead
  of into your database.
- **Place data.** A national list of 50,375 places and 41,154 ZIPs finds the city on a line with no commas and
  completes a cut-off city; `default_state` is a hint for input with no state.
- **Your own spellings and places.** A custom layer (a folder of small files) adds spellings, words, places and ZIPs your
  data uses on top of the shipped tables, without editing them: `doorplate parse --custom-layer DIR`, `doorplate.load_layer`,
  checked with `doorplate layer check`. A layer can change a key, so every parse reports it. The guide has a demo layer, a template and a
  prompt for an LLM ([docs](docs/custom-layers.md)).
- **Sharing messy data.** `doorplate anonymize` (and `Anonymizer` in Python and Rust) swaps the digits and names of
  address-like text, even text that does not parse, and keeps the shape, so a bug report can start from a real
  address. Obfuscation, not anonymity: read the output before you share it ([how it works](docs/anonymizing.md)).
- **DataFrames, SQL and CSV files.** pandas, Polars and DuckDB helpers, a batch call that uses every core, and a
  command that parses a CSV file ([below](#works-with-your-data)).
- **Offline and deterministic.** The same input gives the same output on every platform. Rust, Python and the
  command line share one parser.

## Works with your data
Addresses arrive as a column, split fields, a CSV file or a table. One call per shape gives the same components, keys and
warnings:

```python
import pandas as pd
from doorplate.pandas import parse_column

df = pd.read_csv("addresses.csv")                                # a column named "address"
out = df.join(parse_column(df["address"], default_state="FL"))   # addr_street_name, addr_zip5, addr_key, addr_warnings, ...
```

```sh
doorplate parse-file addresses.csv --column address -o parsed.csv    # a CSV file, no Python
```

Polars, DuckDB (in SQL), split columns and the timings are in [pandas, Polars and DuckDB](https://doorplate.readthedocs.io/en/latest/dataframes/); on the benchmark suite's
inputs `parse_many` handles about 152,000 addresses per second on 4 CPUs (`usaddress.parse` in a loop: about 8,900).
Runnable versions: [`examples/`](examples/README.md).

## What you get

One address, followed through:

| Input | `123 north main street apt 4, Miami FL 33101` |
|---|---|
| Components | street number `123`, predirectional `N`, name `MAIN`, suffix `ST`, unit `APT 4`, city `MIAMI`, state `FL`, ZIP `33101` |
| Place | `MIAMI`, Dade County, found by name (`city` keeps what you wrote) |
| USPS (Pub 28) | `123 N MAIN ST APT 4` / `MIAMI FL 33101` |
| RESO | `StreetNumber` `123`, `StreetDirPrefix` `N`, `StreetName` `MAIN`, `StreetSuffix` `ST`, `UnitNumber` `APT 4`, `City` `MIAMI`, `StateOrProvince` `FL`, `PostalCode` `33101`, `UnparsedAddress` `123 N MAIN ST APT 4, MIAMI, FL 33101` |
| Key | `k4:S\|123\|N\|MAIN\|ST\|\|FL\|33101` (with the unit: `k4:S\|123\|N\|MAIN\|ST\|\|FL\|33101\|4\|`) |
| Slug | `123-n-main-st-apt-4-miami-fl-33101` |
| Warnings | none |

**The key** identifies a property for deduplication and joins. It uses the street
parts, state and ZIP, not the city, and it is versioned: the `k4:` format will not
change in place. [`docs/key-format.md`](docs/key-format.md) is the contract.
**The slug** is for URLs and display; it is not unique. **Warnings** are stable
snake_case codes (`missing_zip`, `unparsed_remainder`, `dual_address`, ...) meant
for a database column; the list is in [`docs/how-it-works.md`](docs/how-it-works.md).

Input does not have to be tidy. Messy and incomplete addresses still parse, with
warnings that say what is missing:

```python
>>> a = doorplate.parse("12 elm st. #5 orlando fl")
>>> a.to_usps()["line1"], a.key(), a.warnings
('12 ELM ST # 5', 'k4n:S|12||ELM|ST||FL|', ['missing_zip'])
```

With no ZIP the key starts `k4n:` (a weaker match), and `missing_zip` says why.
Only input with no address text at all is an error.

## Install

**Python 3.10 or later** (one abi3 wheel per platform: Linux, macOS, Windows):

```sh
pip install doorplate                 # the parser
pip install "doorplate[pandas]"       # plus DataFrame helpers (or [polars])
```

**Rust:**

```sh
cargo add doorplate                   # the library
cargo install doorplate-cli           # the `doorplate` command
```

**From source** (Rust 1.80 or later; the Python extension needs 1.83):

```sh
git clone https://github.com/jeremeybingham/doorplate && cd doorplate
cargo build --release -p doorplate-cli          # target/release/doorplate
cd crates/doorplate-py && pip install maturin && maturin develop --release
```

## Using it
The tours, one per way of using it: the [Python guide](https://doorplate.readthedocs.io/en/latest/python/), the [command-line guide](https://doorplate.readthedocs.io/en/latest/command-line/) and the
[Rust guide](https://doorplate.readthedocs.io/en/latest/rust/). The functions and options are in the [Python reference](https://doorplate.readthedocs.io/en/latest/python-api/) and the
[command-line reference](https://doorplate.readthedocs.io/en/latest/cli/), and the Rust API is on [docs.rs](https://docs.rs/doorplate).

## How it works

```
input (one line or fields)
  -> clean and tokenize -> classify and tag -> assemble (ParsedAddress)
       -> USPS | RESO | key | slug | usaddress labels
  every step reads the Pub 28 tables, the place list and the state data (Lexicons)
```

The parser is rules plus place data. There is no machine-learned model, so the same
input gives the same output on every platform, and a fix is a rule or a line of
data rather than a retraining. The last line of the address (ZIP, state, city) is
read first, right to left, then the delivery line from both ends. A place list
tells a city from street words on a line with no commas. The output formats read the
parsed address and never re-parse it. Parsing never panics: odd input comes back
with warnings. [`docs/how-it-works.md`](docs/how-it-works.md) has the details.

### Place data


A **national list** of 50,375 places and 41,154 ZIPs (Census Gazetteer and GeoNames
postal codes) lets the parser find the city on a line with no commas, tell
`WINGATE ST, 32507` (a street) from `PALM BEACH, 33480` (a city), and complete a cut-off
city. A **state's data** is hand-checked data for one state, added where real data
shows a need; Florida is the first. Layers only add to each other. `city` always keeps
what the input said; the place found is reported beside it. Sources and licenses:
[`docs/places.md`](docs/places.md) and [`docs/states/fl.md`](docs/states/fl.md).

## Benchmarks
| | doorplate | usaddress |
|---|---|---|
| Whole address right, [benchmark suite](docs/running-benchmarks.md), `natural` stratum (16,001 addresses written in five styles) | 98.5% | 96.1% |
| Whole address right, [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark) dev split (60,522 one-line addresses) | 94.3% | 88.1% |
| Addresses per second from Python, one thread (suite inputs) | about 38,300 | about 8,900 |

The suite is 19,586 labeled addresses neither library was made from; it keeps both libraries' blind spots on purpose, so read
its `natural` stratum as the estimate for ordinary input. Speed is on 4 CPUs, 8 GB (read the ratios). These are measurements on
a few data sets, not promises for yours. The method, every other figure and the caveats are in
[accuracy](docs/benchmarks.md) and [speed, size and memory](docs/speed-and-size.md); how to rerun each benchmark is in
[running the benchmarks](docs/running-benchmarks.md).

## What it does not do

- It does not validate that an address exists or can receive mail.
- It does not geocode, match fuzzily, correct addresses, or handle international
  addresses. Recipient lines, landmarks and street corners are not modeled; text
  it cannot place goes to `unparsed` with a warning. `USA` after an address is
  ignored, and an intersection (`MAIN ST & 1ST AVE`) is reported, not keyed.
- It has no learned model.
- The shipped tables are fixed at compile time. If it misparses an address, report
  the input so the tables or rules can be fixed; a user-extensible layer of aliases
  and places is not part of this release.

## Where it is going
0.5.0 is out (an alpha: the `k4` key is new and a `k5` may follow). 0.5.0 is the key-changing release (`k4`); 0.5.x is for speed. What is planned, what depends on what, and what is deliberately not
planned (validation, geocoding, international addresses) are in [`docs/roadmap.md`](docs/roadmap.md).

## Coming from usaddress
The labels are usaddress's, so a pipeline built on them keeps working. For a script that only calls `usaddress.parse` and
`usaddress.tag`, change one import: `import doorplate.compat as usaddress` (label compatibility, not identical output). On the joined
dicts of usaddress's own test files the two agree on 99.3% of 8,103 addresses. The mapping, the differences and a feature comparison:
[`docs/usaddress-compat.md`](docs/usaddress-compat.md).

## Examples

[`examples/`](examples/README.md) has a notebook tour (`parse`, the output formats,
keys, messy lines, `parse_many`, a DataFrame, the CLI), Polars and pandas pipelines,
and small invented sample files.

## Documentation
**<https://doorplate.readthedocs.io/en/latest/>** is a searchable site built from the Markdown in [`docs/`](docs/README.md) (the index of every page, for
GitHub readers). Start with [Getting started](https://doorplate.readthedocs.io/en/latest/getting-started/); the pages most people want:

| Page | Contents |
|---|---|
| [`docs/how-it-works.md`](docs/how-it-works.md) | The pipeline, the design choices |
| [`docs/key-format.md`](docs/key-format.md), [`docs/warnings.md`](docs/warnings.md) | The `k4` key (the contract) and what each warning tells you |
| [`docs/custom-layers.md`](docs/custom-layers.md), [`docs/anonymizing.md`](docs/anonymizing.md) | Your own spellings and places; sharing messy data |
| [`docs/benchmarks.md`](docs/benchmarks.md) | Accuracy, speed and size |
| [`docs/roadmap.md`](docs/roadmap.md), [`CHANGELOG.md`](CHANGELOG.md) | Planned work; release notes |

## Development

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for reporting a misparse and fixing one.

```sh
cargo fmt --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features
cargo bench -p doorplate --bench parse

# Python (in a virtualenv with maturin and pytest)
cd crates/doorplate-py && maturin develop --release && cd ../..
pytest crates/doorplate-py/tests
```

Plain `cargo test` and `clippy` need no Python: the `doorplate-py` crate has no Rust
test target, and maturin supplies the extension-module build settings. The golden
corpus (`tests/corpus/`) is the regression suite: a parsing bug fixed gets a case.

## Disclaimer

doorplate is provided "as is", without warranty of any kind, under the [MIT](LICENSE-MIT) or
[Apache-2.0](LICENSE-APACHE) license at your option; the license text is what governs. In plain
terms: **use it at your own risk.** Nothing here guarantees that a parse, a warning, a match key
or a figure is correct, complete or fit for your purpose. Accuracy and speed numbers are
measurements on particular datasets, not promises for yours. doorplate parses and formats
addresses; it does **not validate** that an address exists or can receive mail, and Pub 28
formatting is not certified validation. Check its output before you rely on it for anything with
legal, financial, safety or delivery consequences.

doorplate is an independent project. It is not affiliated with, endorsed by or certified by the
US Postal Service, RESO, DataMade (the authors of usaddress) or any data source it cites; those
names are used only to say what the output follows or is compared with.

## License

Licensed under either of [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE) at your
option. The ZIP tables in `crates/doorplate/data/states/` and
`crates/doorplate/data/places/` are GeoNames data under CC BY 4.0; see
[`NOTICE`](NOTICE).

## About the author

I am Jeremey Bingham. I have worked in technology since 2007, with Python for about ten years
and Rust for about two. I spent years inside real estate data: the Realtor Association of the
Palm Beaches and [BeachesMLS](https://www.beachesmls.com/), the [Massachusetts Association of Realtors](https://www.marealtor.com/), where I was Director of
Information Technology, and [HouseCanary](https://www.housecanary.com/), where I built APIs over residential property records. I
also published [reso-client](https://github.com/jeremeybingham/reso_client), a Rust client for the
RESO Web API. My resume is at [resume.jeremeybingham.com](https://resume.jeremeybingham.com).
