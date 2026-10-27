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
be taken apart, with the output, as you type. The parser runs on your machine; nothing is sent anywhere.

This library formats and parses; it **does not validate** that an address exists or can
receive mail. Pub 28 formatting is not deliverability, and validation needs
postal-service-certified data; warnings such as `zip_city_mismatch` are hints about the
input, not verdicts.

> **Alpha release (0.4.0).** Expect rough edges. This documentation MAY describe features from pre-release versions. The match key is versioned (`k3:`) and
> will probably get new versions as the parser improves, so store the version prefix
> with your keys and plan to re-key. `k3` is new in 0.4.0 and has only been checked on the project's own test data, so a `k4` may follow soon. Accuracy and speed are measurements on a few
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
a.key()                             # "k3:S|123|N|MAIN|ST||FL|33101"
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
k3:S|123|N|MAIN|ST||FL|33101
```

## Features

- **Any shape of address.** Street addresses with directionals, suffixes, units and a second unit; PO boxes;
  rural and highway-contract routes; military and general delivery; highways with a state or county prefix;
  intersections and care-of lines are recognized and set apart. Missing pieces (no ZIP, no state, no commas)
  parse, with a warning that says what is missing ([what each warning tells you](docs/warnings.md)).
- **One line or separate fields.** `parse` takes a single string; `parse_fields` takes `line1`, `line2`, `city`,
  `state` and `zip` as your data has them, in whatever combination is filled in.
- **Output you can load.** Components, USPS Publication 28 lines, RESO Data Dictionary 2.0 fields, a display
  form for people, usaddress-style labels, a canonical match key (`k3:...`), a URL-safe slug.
- **Diagnostics.** Stable warning codes and the text it could not place, so doubtful rows go to review instead
  of into your database.
- **Place data.** A national list of 50,375 places and 41,154 ZIPs finds the city on a line with no commas and
  completes a cut-off city; `default_state` is a hint for input with no state.
- **DataFrames, SQL and CSV files.** pandas, Polars and DuckDB helpers, a batch call that uses every core, and a
  command that parses a CSV file ([below](#works-with-your-data)).
- **Offline and deterministic.** The same input gives the same output on every platform. Rust, Python and the
  command line share one parser.

## Works with your data

Addresses arrive in different shapes. Pick the call that matches yours; all of them give the same components,
keys and warnings.

| Your data | Use |
|---|---|
| A column of whole addresses (`123 N Main St Apt 4, Miami FL 33101`) in **pandas** or **Polars** | `doorplate.pandas.parse_column` / `doorplate.polars.parse_column` |
| The same, in **DuckDB** (a table, or a CSV or Parquet file it reads; `parse_column` is lazy, so tables larger than memory work) | `doorplate_parse(address)` in SQL, or `doorplate.duckdb.parse_column` on a relation |
| Separate columns (street line, unit line, city, state, ZIP), complete or with gaps | `parse_fields_many` (lists), `doorplate_parse_fields(...)` in DuckDB |
| A **CSV file**, without writing any Python | `doorplate parse-file in.csv --column address -o out.csv`, or `--column line1 --line2 ... --city ... --state ... --zip ...` for split columns |
| Messy real addresses you want to share in a bug report | `doorplate anonymize` (CLI) or `doorplate.Anonymizer` (Python): same shape, other digits and names. Obfuscation, not anonymity: [what it keeps](https://github.com/jeremeybingham/doorplate/blob/main/CONTRIBUTING.md#sharing-messy-data) |
| One address per line in a text file or a pipe | `doorplate parse - < addresses.txt` (JSON lines out) |
| A mix of street addresses, PO boxes, rural routes, military, units in line 2, missing ZIPs | One call parses them all; the `address_type`, `warnings` and `key` columns say which is which |
| Any list of strings, in code | `parse_many` (all cores, GIL released) |

```python
import pandas as pd
from doorplate.pandas import parse_column

df = pd.read_csv("addresses.csv")                                # a column named "address"
out = df.join(parse_column(df["address"], default_state="FL"))   # addr_street_name, addr_zip5, addr_key, addr_warnings, ...
```

```python
import polars as pl
import doorplate as dp
from doorplate.polars import parse_column

df = pl.read_csv("addresses.csv")
out = df.hstack(parse_column(df["address"]))                     # whole addresses in one column

split = pl.read_csv("split.csv", infer_schema_length=0)          # line1, line2, city, state, zip, with gaps
rows = dp.parse_fields_many(line1=split["line1"].to_list(), line2=split["line2"].to_list(),
                            city=split["city"].to_list(), state=split["state"].to_list(),
                            zip=split["zip"].to_list())          # one ParsedAddress per row
```

```python
import duckdb
from doorplate import duckdb as dd

con = duckdb.connect()
dd.register(con, columns=["street_name", "city", "state", "zip5", "key", "warnings"])
con.sql("SELECT id, doorplate_parse(address).key AS key FROM read_csv('addresses.csv')")
con.sql("SELECT doorplate_parse_fields(line1, line2, city, state, zip).key FROM read_csv('split.csv', all_varchar=true)")
```

```sh
doorplate parse-file addresses.csv --column address -o parsed.csv                       # appends addr_* columns
doorplate parse-file split.csv --column line1 --line2 line2 --city city --state state --zip zip -o parsed.csv
```

Every helper adds the same columns: the components, `address_type`, `key`, `slug`, `warnings` (codes joined by
commas), and optionally the USPS lines, the unit-level key and the unparsed text. A blank or missing row stays
blank instead of failing. The helpers are built over `parse_many`, which parses on every core it is given: on
the benchmark suite's inputs, under its 4-CPU, 8 GB profile, it handles about 152,000 addresses per second
(`usaddress.parse` in a loop: about 8,900). Runnable versions with data of several shapes are in [`examples/`](examples/README.md) (a notebook, a pandas, a Polars and a DuckDB
pipeline); the full API and the recipes are in
[`crates/doorplate-py/README.md`](crates/doorplate-py/README.md).

## What you get

One address, followed through:

| Input | `123 north main street apt 4, Miami FL 33101` |
|---|---|
| Components | street number `123`, predirectional `N`, name `MAIN`, suffix `ST`, unit `APT 4`, city `MIAMI`, state `FL`, ZIP `33101` |
| Place | `MIAMI`, Dade County, found by name (`city` keeps what you wrote) |
| USPS (Pub 28) | `123 N MAIN ST APT 4` / `MIAMI FL 33101` |
| RESO | `StreetNumber` `123`, `StreetDirPrefix` `N`, `StreetName` `MAIN`, `StreetSuffix` `ST`, `UnitNumber` `APT 4`, `City` `MIAMI`, `StateOrProvince` `FL`, `PostalCode` `33101`, `UnparsedAddress` `123 N MAIN ST APT 4, MIAMI, FL 33101` |
| Key | `k3:S\|123\|N\|MAIN\|ST\|\|FL\|33101` (with the unit: `k3:S\|123\|N\|MAIN\|ST\|\|FL\|33101\|4\|`) |
| Slug | `123-n-main-st-apt-4-miami-fl-33101` |
| Warnings | none |

**The key** identifies a property for deduplication and joins. It uses the street
parts, state and ZIP, not the city, and it is versioned: the `k3:` format will not
change in place. [`docs/key-format.md`](docs/key-format.md) is the contract.
**The slug** is for URLs and display; it is not unique. **Warnings** are stable
snake_case codes (`missing_zip`, `unparsed_remainder`, `dual_address`, ...) meant
for a database column; the list is in [`docs/how-it-works.md`](docs/how-it-works.md).

Input does not have to be tidy. Messy and incomplete addresses still parse, with
warnings that say what is missing:

```python
>>> a = doorplate.parse("12 elm st. #5 orlando fl")
>>> a.to_usps()["line1"], a.key(), a.warnings
('12 ELM ST # 5', 'k3n:S|12||ELM|ST||FL|', ['missing_zip'])
```

With no ZIP the key starts `k3n:` (a weaker match), and `missing_zip` says why.
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

### Python

```python
import doorplate

doorplate.parse_fields(line1="THE COVE", line2="1111 ASBURY WAY",
                       city="Orlando", state="FL", zip="32801")   # pre-split fields
doorplate.parse_many(["1 Main St, Miami FL", "PO Box 5, Tampa FL"])  # parallel, GIL released
doorplate.parse_fields_many(line1=["1 Main St", "PO Box 5"],            # pre-split columns, same
                            city=["Miami", "Tampa"], state=["FL", "FL"])  # but a batch
doorplate.parse("281 EVELYN DR DOTHAN", default_state="AL").city     # "DOTHAN"
doorplate.tag("PO Box 12, Tampa FL 33601")    # ({...usaddress labels...}, "PO Box")
```

`parse_many` and `parse_fields_many` (pre-split columns) parse a list on all cores
and keep the order. For a pandas or
Polars column, `doorplate.pandas.parse_column` and `doorplate.polars.parse_column`
return component columns in one call; `doorplate.duckdb` adds `doorplate_parse(...)` functions
and `parse_column` for DuckDB (`pip install "doorplate[duckdb]"`). Details, the DataFrame recipes and the
types: [`crates/doorplate-py/README.md`](crates/doorplate-py/README.md).

### Rust

```rust
use doorplate::{KeyOptions, Parser};

let parser = Parser::new();
let a = parser.parse("123 north main street apt 4, Miami FL 33101")?;
assert_eq!(a.street_name.as_deref(), Some("MAIN"));
assert_eq!(a.unit_number.as_deref(), Some("4"));

a.to_usps().line1;                // Some("123 N MAIN ST APT 4")
a.to_reso();                      // RESO Data Dictionary 2.0 fields
a.key(KeyOptions::property());    // Some("k3:S|123|N|MAIN|ST||FL|33101")
a.slug();                         // Some("123-n-main-st-apt-4-miami-fl-33101"), display only
a.to_display().line1;             // Some("123 N Main St Apt 4"); to_long(): "123 North Main Street Apartment 4"
a.diagnostics.warnings;           // e.g. MissingZip, UnparsedRemainder
```

`Parser::parse_fields` takes pre-split fields (`Fields`); `Parser::parse_many` and
`Parser::parse_fields_many` parse a batch, in parallel with the `rayon` feature.
`Parser::with_options(ParseOptions::new().default_state("FL"))?` sets a
state hint.

### Command line

```sh
doorplate parse "123 N Main St, Miami FL 33101" --pretty     # JSON: components, output, key, warnings, provenance
doorplate --version                                          # the library version, also in the JSON as provenance.library_version (and provenance.state_data_version)
doorplate parse-file in.csv --column address -o out.csv      # appends addr_* columns
doorplate parse "281 EVELYN DR DOTHAN" --default-state AL
doorplate parse "123 N Main St, Miami FL 33101" --display    # mixed case; --long spells words out (not Pub 28)
doorplate parse "123 N Main St, Miami FL 33101" --tag        # usaddress-style joined labels
doorplate parse -  < addresses.txt                           # one address per line, JSON lines out
doorplate anonymize in.csv --column address -o shareable.csv   # replace digits and names, keep the shape (read it before you share it)
```

`doorplate --help` lists every option.

### A state hint

When the input names no state and has no known ZIP, `default_state` lets the parser
look the city up in that state: `281 EVELYN DR DOTHAN` finds `DOTHAN` with `AL`. It
is a hint, never a fill: `state` stays empty, `missing_state` still fires, and
`default_state_applied` says when the hint decided something.

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

The headline numbers, then what each benchmark in the repository is, so you can tell them apart.

| | doorplate | usaddress |
|---|---|---|
| Whole address right, [benchmark suite](benchmarks/README.md#the-benchmark-suite), `natural` stratum (16,001 addresses written in five styles) | 98.3% | 96.1% |
| Whole address right, [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark) dev split (60,522 one-line addresses) | 94.5% | 88.1% |
| Addresses per second from Python, one thread (suite inputs; `parse_tokens` / `usaddress.parse`) | about 38,300 | about 8,900 |
| Addresses per second, `parse_many` on 4 threads (usaddress has no batch call) | about 152,000 | about 8,900 |
| Installed size | 1.8 MB wheel | 4.8 MB with dependencies |

The accuracy and speed rows of the suite come from `python benchmarks/suite.py all` (4 CPUs, 8 GB; the speed is
the best of three runs on one machine, so read the ratios: about 4.3x on one thread and 17x on four; the recorded run, and 0.3.1 against 0.4.0, are in `docs/benchmarks.md`). The geocode row is
an outside data set, and the size row is from `benchmarks/size_memory.py`. They were measured on a few data
sets and are not promised for yours. Method, every other figure and the caveats:
[`docs/benchmarks.md`](docs/benchmarks.md).

**0.3.1 to 0.4.0**, the same benchmarks on both builds, back to back on one machine (the full tables, with the Rust
and size figures, are in [`docs/benchmarks.md`](docs/benchmarks.md#031-to-040)):

| | 0.3.1 | 0.4.0 |
|---|---|---|
| Suite, `natural` stratum / whole suite | 98.3% / 92.2% | 98.3% / 92.3% |
| Geocode benchmark, dev | 94.4% | 94.5% |
| Fields input right / unit number right | 98.9% / 96.8% | 99.1% / 97.8% |
| Wrong parses that raised a warning | 43.9% | 54.7% |
| Python `parse`, geocode addresses, one thread | 34,149/s | 38,463/s (+13%) |
| Python `parse_many`, 4 threads | 113,873/s | 137,876/s (+21%) |
| One address in Rust, full one line | 17.3 µs | 12.4 µs (-28%) |

### The benchmarks, and which to run

| Name | What it measures | Run it | Data | For |
|---|---|---|---|---|
| **Benchmark suite** | Accuracy next to usaddress on 19,586 labeled addresses neither library was made from, a doorplate-only track (fields input, Pub 28 output, key stability, warnings), and speed under a fixed 4-CPU, 8 GB profile | `python benchmarks/suite.py all` (about 20 s) | In the repository (`benchmarks/suite/v1/`) | Anyone. **Start here** |
| **[Geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark)** | Accuracy on one-line, uppercase, comma-free US street addresses from an outside data set (60,522 in the `dev` split) | `python benchmarks/accuracy.py` | Not redistributable: download it into `local-data/` | Maintainers; the check that a rule fix generalizes |
| **Speed** | Addresses per second: Python (`speed_python.py`), batches and pandas, Polars and DuckDB frames (`bench_batch.py`), Rust (`speed_rust.py`, criterion) | the scripts in `benchmarks/` | Committed, invented addresses | Anyone; absolute figures belong to one machine, so read ratios |
| **Size and memory** | Wheel, binary and installed size; import time; resident memory, against usaddress | `python benchmarks/size_memory.py` | None | Anyone |
| **Checks on private data** | Rule changes and releases on real data: the Netsyms address database, the National Address Database sample, Florida records | `tools/harness/`, `tools/compare/` | `local-data/`, never published | Maintainers |

Two things that look like benchmarks are not: the **golden corpus** (`tests/corpus/`) is a regression set that
doorplate passes by construction, and **usaddress's own test files** are usaddress's regression tests (it
scores about 100% on them). Neither says how accurate either library is on new data.

On the suite, the `hard` stratum holds both libraries' known blind spots on purpose (doorplate 54%,
usaddress 18%), so read the `natural` figure as the estimate for ordinary input. doorplate scores 0% on a
house number with a letter prefix (`W 615 County Road C`). The suite's rows are anonymized National Address
Database rows (real streets, cities and ZIP codes, invented numbers), and a private twin built from an
unpublished seed checks that the public set was not tuned to.

The [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark)'s figure needs a caveat: the rules and the place list were first developed while
reading the errors of its *test* split (96.8%), so that figure is optimistic; later rules were fixed against
part of the train split (20% of it held out, unread, 94.2%) and checked on dev, and 94.5% is the estimate for
data of that shape (one line, US street addresses, a city and a state), not a guarantee for yours.

How to run each, what it needs, and the resource profile: [`benchmarks/README.md`](benchmarks/README.md).
The specification of the suite and the rules that keep it fair: [`docs/benchmark-suite.md`](docs/benchmark-suite.md).

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

0.4.0 is out (an alpha: the `k3` key is new and a `k4` may follow). The next point release, 0.4.x, is about tooling,
documentation and extensibility; the key-changing rules wait for the release after it. Roughly in this order:

- **Tooling.** An anonymizing tool so messy data can be shared safely, quieter harness scorers, a review tool that
  compares doorplate with usaddress, and per-state street-pattern counts.
- **Documentation.** A searchable, versioned documentation site.
- **Extensibility.** A custom layer: your own spellings, places, ZIPs and state-specific readings, loaded at run
  time without editing the shipped tables; a columnar result for DataFrames; a usaddress-shaped module.
- **0.5.0, a `k4`.** The parser rules that change keys, cut together, once the tooling has produced evidence: the
  state-dependent road conventions, the Florida place gaps, and the rest of the research on real data.

The details, and what is deliberately not planned (validation, geocoding, international
addresses), are in [`docs/roadmap.md`](docs/roadmap.md).

## Coming from usaddress

The labels are usaddress's, so a pipeline built on them keeps working:

| usaddress | doorplate (Python) |
|---|---|
| `usaddress.parse(s)`: `[(token, label)]` | `doorplate.parse_tokens(s)` |
| `usaddress.tag(s)`: `(dict, type)` | `doorplate.tag(s)` |
| `RepeatedLabelError` | not raised: the runs are joined and `parse(s).repeated_labels()` lists the labels |
| `Street Address`, `PO Box`, `Ambiguous` | `parse(s).address_type()` is finer; `tag(s)` returns the three |

On the joined dicts of usaddress's own test files the two agree on 99.3% of 8,103
addresses. Tokens doorplate cannot place are left out of `tag()`, and some labels
(landmarks, corners, recipients) are not modeled. The full mapping, the differences
and a feature comparison: [`docs/usaddress-compat.md`](docs/usaddress-compat.md).

## Examples

[`examples/`](examples/README.md) has a notebook tour (`parse`, the output formats,
keys, messy lines, `parse_many`, a DataFrame, the CLI), Polars and pandas pipelines,
and small invented sample files.

## Documentation

| Page | Contents |
|---|---|
| [`docs/how-it-works.md`](docs/how-it-works.md) | The pipeline, the design choices, the layout |
| [`docs/key-format.md`](docs/key-format.md) | The `k3` key and the slug: the contract |
| [`docs/reso-mapping.md`](docs/reso-mapping.md) | RESO field mapping |
| [`docs/usps-pub28-notes.md`](docs/usps-pub28-notes.md) | The source of every table and parser rule |
| [`docs/usaddress-compat.md`](docs/usaddress-compat.md) | usaddress-shaped output, labels, migration |
| [`docs/benchmarks.md`](docs/benchmarks.md) | Accuracy, speed and size |
| [`docs/roadmap.md`](docs/roadmap.md) | Planned work, what is not planned, and what data would help |
| [`docs/places.md`](docs/places.md), [`docs/states/fl.md`](docs/states/fl.md) | The place list and the Florida state data: sources and licenses |
| [`tests/corpus/README.md`](tests/corpus/README.md) | The golden corpus format |
| [`crates/doorplate-py/README.md`](crates/doorplate-py/README.md) | The Python package |
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes |

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
