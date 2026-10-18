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

> **Alpha release (0.1.0).** Expect rough edges. The match key is versioned (`k1:`)
> and will probably get new versions as the parser improves, so store the version
> prefix with your keys and plan to re-key. Names in the API and the warning codes may
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
a.key(KeyOptions::property());    // Some("k1:S|123|N|MAIN|ST||FL|33101")
a.slug();                         // Some("123-n-main-st-apt-4-miami-fl-33101"), display only
a.diagnostics.warnings;           // e.g. MissingZip, UnparsedRemainder
```

- `Parser::parse_fields` takes pre-split fields (`Fields`).
- `Parser::parse_many` parses a batch, in parallel with the `rayon` feature.
- `Parser::with_options(ParseOptions { default_state: Some("FL".into()) })?` sets a
  state hint. It is a lookup hint, never a fill: `state` stays empty and
  `missing_state` still fires.
- Only input with no address text at all is an error; anything else comes back as a
  `ParsedAddress` with warnings (stable snake_case codes) and the text it could not
  place.

## Features

| Feature | Default | Adds |
|---|---|---|
| `places-us` | yes | the national place and ZIP list, used to find and name the city |
| `state-fl` | yes | the curated Florida pack |
| `rayon` | no | parallel `Parser::parse_many` |
| `corpus` | no | the golden-corpus loader and runner (`doorplate::corpus`); pulls in serde |

## The match key

`a.key(...)` identifies a property for deduplication and joins. It uses the street
parts, state and ZIP, not the city, and it is versioned: the `k1:` format will not
change in place. [Key format](https://github.com/jeremeybingham/doorplate/blob/main/docs/key-format.md) is the contract. The
slug is for URLs and display; it is not unique.

## More

- [Project README](https://github.com/jeremeybingham/doorplate#readme): what it does, accuracy and speed, the Python package.
- [API documentation](https://docs.rs/doorplate).
- [How it works](https://github.com/jeremeybingham/doorplate/blob/main/docs/how-it-works.md),
  [Pub 28 and rule sources](https://github.com/jeremeybingham/doorplate/blob/main/docs/usps-pub28-notes.md),
  [RESO mapping](https://github.com/jeremeybingham/doorplate/blob/main/docs/reso-mapping.md) and the
  [roadmap](https://github.com/jeremeybingham/doorplate/blob/main/docs/roadmap.md).
- The command-line tool is [`doorplate-cli`](https://crates.io/crates/doorplate-cli);
  the Python package is [`doorplate` on PyPI](https://pypi.org/project/doorplate/).

Licensed under either of MIT or Apache-2.0 at your option.
