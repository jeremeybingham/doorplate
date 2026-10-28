# doorplate

[![CI](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml/badge.svg)](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml)
[![crates.io](https://img.shields.io/crates/v/doorplate.svg)](https://crates.io/crates/doorplate)
[![crates.io downloads](https://img.shields.io/crates/d/doorplate.svg)](https://crates.io/crates/doorplate)
[![docs.rs](https://docs.rs/doorplate/badge.svg)](https://docs.rs/doorplate)
[![License: MIT OR Apache-2.0](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](https://github.com/jeremeybingham/doorplate#license)
[![Rust 1.80+](https://img.shields.io/badge/rustc-1.80%2B-orange.svg)](https://github.com/jeremeybingham/doorplate/blob/main/Cargo.toml)

Parse US addresses into components, with USPS Publication 28 and RESO output, a
canonical match key, a URL-safe slug, and diagnostics. Pure Rust: no runtime
dependencies by default, no data to download, no machine-learned model, and
parsing never panics.

This library formats and parses; it **does not validate** that an address exists or
can receive mail.

> **Alpha release (0.4.1).** Expect rough edges. The match key is versioned (`k3:`)
> and will probably get new versions as the parser improves, so store the version
> prefix with your keys and plan to re-key. `k3` is new in 0.4.0 and has only been checked on the project's own test data, so a `k4` may follow soon. Names in the API and the warning codes may
> still change before 1.0.
>
> **Help wanted: messy addresses.** If it parses your addresses badly, please
> [open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md)
> with a sample. Private data can be anonymized first
> ([how](https://github.com/jeremeybingham/doorplate/blob/main/CONTRIBUTING.md#sharing-messy-data)).

## Quickstart

```sh
cargo add doorplate
```

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
a.diagnostics.state_data_version; // Some("2026.10.5") for Florida, None for a state without curated data
```

- `Parser::parse_fields` takes pre-split fields (`Fields`: `line1`, `line2`, `city`, `state`, `zip`, each optional).
- `Parser::parse_many` and `Parser::parse_fields_many` parse a batch, in parallel
  with the `rayon` feature.
- `Parser::with_options(ParseOptions::new().default_state("FL"))?` sets a
  state hint. It is a lookup hint, never a fill: `state` stays empty and
  `missing_state` still fires.
- Only input with no address text at all is an error; anything else comes back as a
  `ParsedAddress` with warnings (stable snake_case codes; [what each one tells you, and how often
  it is wrong](https://github.com/jeremeybingham/doorplate/blob/main/docs/warnings.md)) and the text it could not place.

Batches, pre-split fields (`Fields`), PO boxes, military and general delivery go through the same calls; `doorplate::Anonymizer`
rewrites address-like text so it can be shared (obfuscation, not anonymity). These are in the [Rust guide](https://doorplate.readthedocs.io/en/latest/rust/). The runnable
tour is [`examples/quickstart.rs`](https://github.com/jeremeybingham/doorplate/blob/main/crates/doorplate/examples/quickstart.rs)
(`cargo run -p doorplate --example quickstart` in a clone). For CSV files without writing code, install
[`doorplate-cli`](https://crates.io/crates/doorplate-cli); for pandas, Polars and DuckDB, use the
[Python package](https://pypi.org/project/doorplate/), which wraps this crate.

## Features

| Feature | Default | Adds |
|---|---|---|
| `places-us` | yes | the national place and ZIP list, used to find and name the city |
| `rayon` | no | parallel `Parser::parse_many` and `parse_fields_many` |
| `corpus` | no | the golden-corpus loader and runner (`doorplate::corpus`); pulls in serde |
| `custom-layer` | no | `CustomLayer::from_sources` and `from_dir`: your own spellings, words, places and ZIPs on top of the shipped tables, reported in `Diagnostics::custom_layer`; pulls in `toml`. A layer can change a key ([Custom layers](https://github.com/jeremeybingham/doorplate/blob/main/docs/custom-layers.md)) |

## Accuracy and speed

| | doorplate | usaddress |
|---|---|---|
| Whole address right, benchmark suite, `natural` stratum (16,001 addresses written in five styles) | 98.3% | 96.1% |
| Whole address right, [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark) dev split (60,522 one-line addresses) | 94.5% | 88.1% |
| One address in Rust (median of the corpus shapes, criterion; `cargo bench -p doorplate --bench parse`) | 5 to 12 µs | |

The suite and the geocode benchmark are run from Python (the table compares with the Python library usaddress); see the
[accuracy](https://doorplate.readthedocs.io/en/latest/benchmarks/) and [speed](https://doorplate.readthedocs.io/en/latest/speed-and-size/) pages for the method and caveats, and [running the benchmarks](https://doorplate.readthedocs.io/en/latest/running-benchmarks/) to rerun them. These are
measurements on a few data sets, not promises for yours.

## The match key

`a.key(...)` identifies a property for deduplication and joins. It uses the street
parts, state and ZIP, not the city, and it is versioned: the `k3:` format will not
change in place. [Key format](https://github.com/jeremeybingham/doorplate/blob/main/docs/key-format.md) is the contract. The
slug is for URLs and display; it is not unique.

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
- [Rust guide](https://doorplate.readthedocs.io/en/latest/rust/), [API documentation](https://docs.rs/doorplate) and the [documentation site](https://doorplate.readthedocs.io/en/latest/) (how it works, the key, warnings, custom layers).
- [Project README](https://github.com/jeremeybingham/doorplate#readme): what it does, accuracy and speed, the Python package.
- The command-line tool is [`doorplate-cli`](https://crates.io/crates/doorplate-cli); the Python package is [`doorplate` on PyPI](https://pypi.org/project/doorplate/).

Licensed under either of MIT or Apache-2.0 at your option.

