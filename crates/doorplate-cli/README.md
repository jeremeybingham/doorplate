# doorplate-cli

[![CI](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml/badge.svg)](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml)
[![crates.io](https://img.shields.io/crates/v/doorplate-cli.svg)](https://crates.io/crates/doorplate-cli)
[![crates.io downloads](https://img.shields.io/crates/d/doorplate-cli.svg)](https://crates.io/crates/doorplate-cli)
[![License: MIT OR Apache-2.0](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](https://github.com/jeremeybingham/doorplate#license)

The `doorplate` command: parse US addresses from the shell or a CSV file into
components, USPS Publication 28 and RESO output, a canonical match key, a slug and
warnings. It wraps the [`doorplate`](https://crates.io/crates/doorplate) library.

This tool formats and parses; it **does not validate** that an address exists or can
receive mail.

> **Alpha release (0.3.1).** The match key is versioned (`k2:`) and will probably
> get new versions, so store the version prefix with your keys. Options and output
> fields may still change before 1.0. If it parses your addresses badly, please
> [open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md).

## Install

```sh
cargo install doorplate-cli        # installs the `doorplate` command
```

Rust 1.80 or later.

## Usage

```sh
doorplate parse "123 N Main St, Miami FL 33101" --pretty     # JSON: components, output, key, warnings, provenance
doorplate --version                                          # the library version, also in the JSON as provenance.library_version (and provenance.state_data_version)
doorplate parse "123 N. Main St #4, miami, fl 33101" --usps  # Pub 28 lines
doorplate parse-file in.csv --column address -o out.csv      # appends addr_* columns
doorplate parse --line1 "412 N HARBOR ST" --line2 "APT 3B" --city Tampa --state FL --zip 33602   # pre-split fields
doorplate parse "281 EVELYN DR DOTHAN" --default-state AL    # state hint
doorplate parse "123 N Main St, Miami FL 33101" --display    # mixed case; --long spells words out (not Pub 28)
doorplate parse "123 N Main St, Miami FL 33101" --tag        # usaddress-style joined labels
doorplate parse -  < addresses.txt                           # one address per line, JSON lines out
```

```sh
$ doorplate parse "123 N. Main St #4, miami, fl 33101" | jq -r .key
k2:S|123|N|MAIN|ST||FL|33101
```

`doorplate --help` lists every option.

## CSV files

`parse-file` reads a CSV file and writes it back with the parsed columns appended, so it works on the shape your
data already has:

```sh
# a column of whole addresses
doorplate parse-file addresses.csv --column address -o parsed.csv

# street line, unit line, city, state and ZIP in separate columns (any of them may be empty)
doorplate parse-file split.csv --column line1 --line2 line2 --city city --state state --zip zip -o parsed.csv

# a state hint for rows that name no state
doorplate parse-file addresses.csv --column address --default-state FL -o parsed.csv
```

Every input column is kept, and the new `addr_` columns are the components (`street_number`, `street_name`,
`unit_number`, `city`, `state`, `zip5`, ...), the shapes (`po_box`, `rural_route`, `military`, `general_delivery`),
`place`, the USPS lines, `key`, `key_unit`, `slug`, `warnings` (stable codes joined by commas) and `unparsed`. PO
boxes, routes, military addresses and street addresses can share one file. A blank row, or a row with no address
text, is written with empty new columns and counted on standard error instead of stopping the run. Without `-o`
the CSV goes to standard output, so it composes with other tools. On a Florida file with five address columns it
ran at about 30,000 rows per second on one thread, including reading and writing about 30 columns
([benchmarks](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md)).

For a data frame, SQL or a notebook, the [Python package](https://pypi.org/project/doorplate/) has pandas, Polars
and DuckDB helpers over the same parser. On the benchmark suite (19,586 labeled addresses neither library was made
from) it gets 98.3% of whole addresses right on the `natural` stratum, against 96.1% for the Python library
usaddress; the method, the caveats and the blind spots are in the
[benchmarks](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md). These are measurements on a
few data sets, not promises for yours.

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

- [Project README](https://github.com/jeremeybingham/doorplate#readme), [how it works](https://github.com/jeremeybingham/doorplate/blob/main/docs/how-it-works.md) and the
  [key format](https://github.com/jeremeybingham/doorplate/blob/main/docs/key-format.md).
- The library is [`doorplate`](https://crates.io/crates/doorplate); the Python package
  is [`doorplate` on PyPI](https://pypi.org/project/doorplate/).

Licensed under either of MIT or Apache-2.0 at your option.
