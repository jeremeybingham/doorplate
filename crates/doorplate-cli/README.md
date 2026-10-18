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

> **Alpha release (0.2.0).** The match key is versioned (`k2:`) and will probably
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
doorplate parse "123 N Main St, Miami FL 33101" --pretty     # JSON: components, output, key, warnings
doorplate parse "123 N. Main St #4, miami, fl 33101" --usps  # Pub 28 lines
doorplate parse-file in.csv --column address -o out.csv      # appends addr_* columns
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

## More

- [Project README](https://github.com/jeremeybingham/doorplate#readme), [how it works](https://github.com/jeremeybingham/doorplate/blob/main/docs/how-it-works.md) and the
  [key format](https://github.com/jeremeybingham/doorplate/blob/main/docs/key-format.md).
- The library is [`doorplate`](https://crates.io/crates/doorplate); the Python package
  is [`doorplate` on PyPI](https://pypi.org/project/doorplate/).

Licensed under either of MIT or Apache-2.0 at your option.
