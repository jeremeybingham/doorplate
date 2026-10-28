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

> **Alpha release (0.4.1).** The match key is versioned (`k3:`) and will probably
> get new versions, so store the version prefix with your keys. `k3` is new in 0.4.0 and has only been checked on the project's own test data, so a `k4` may follow soon. Options and output
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
doorplate anonymize in.csv --column address -o shareable.csv   # same shape, other digits and names
doorplate parse "123 Oak Trayl, Miami FL 33101" --custom-layer DIR   # your own spellings and places (below)
doorplate layer check DIR                                    # load a custom layer: every problem, or what it holds
```

```sh
$ doorplate parse "123 N. Main St #4, miami, fl 33101" | jq -r .key
k3:S|123|N|MAIN|ST||FL|33101
```

`doorplate --help` lists every option.

## CSV files
`parse-file` reads a CSV file and writes it back with the parsed columns appended (`addr_street_number`, `addr_key`,
`addr_warnings`, ...). Every input column is kept, and a blank row stays blank instead of stopping the run:

```sh
doorplate parse-file addresses.csv --column address -o parsed.csv                                    # a column of whole addresses
doorplate parse-file split.csv --column line1 --line2 line2 --city city --state state --zip zip -o parsed.csv   # split columns
```

The columns, the state hint and the speed are in the [command-line guide](https://doorplate.readthedocs.io/en/latest/command-line/).

## Custom layers
`doorplate layer check DIR` and `--custom-layer DIR` add your own spellings, words, places and ZIPs on top of the shipped
tables. A layer can change a key, so every record reports it (`provenance.custom_layer`). The files, the rules and a template
are in [Custom layers](https://doorplate.readthedocs.io/en/latest/custom-layers/).

## Sharing messy data
`doorplate anonymize in.csv --column address -o shareable.csv` rewrites address-like text so it keeps its shape and loses its
names and numbers, even when it does not parse. **It is obfuscation, not anonymity:** read the output before you share it.
The rules and limits are in [Anonymizing data](https://doorplate.readthedocs.io/en/latest/anonymizing/). For a data frame, SQL or a notebook, the
[Python package](https://pypi.org/project/doorplate/) has pandas, Polars and DuckDB helpers over the same parser.

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
- [Documentation site](https://doorplate.readthedocs.io/en/latest/): the [command-line guide](https://doorplate.readthedocs.io/en/latest/command-line/) and [reference](https://doorplate.readthedocs.io/en/latest/cli/), the [key](https://doorplate.readthedocs.io/en/latest/key-format/) and [how it works](https://doorplate.readthedocs.io/en/latest/how-it-works/).
- [Project README](https://github.com/jeremeybingham/doorplate#readme).
- The library is [`doorplate`](https://crates.io/crates/doorplate); the Python package is [`doorplate` on PyPI](https://pypi.org/project/doorplate/).

Licensed under either of MIT or Apache-2.0 at your option.

