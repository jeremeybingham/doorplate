# Rust guide

The `doorplate` crate is the parser itself; the Python package and the command-line tool wrap it. This page is the tour
and the cargo features; the API reference is on [docs.rs](https://docs.rs/doorplate). It formats and parses; it does not
validate that an address exists or can receive mail.

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
  it is wrong](warnings.md)) and the text it could not place.

Addresses arrive in different shapes. Whole lines, split columns, PO boxes, rural routes, military and
general delivery, units on a second line, and rows with gaps all go through the same calls:

```rust
use doorplate::{Fields, Parser};

let parser = Parser::new();
let rows = vec![
    Fields { line1: Some("412 N HARBOR ST".into()), line2: Some("APT 3B".into()),
             city: Some("TAMPA".into()), state: Some("FL".into()), zip: Some("33602".into()) },
    Fields { line1: Some("PO BOX 4821".into()), city: Some("JACKSONVILLE".into()),
             state: Some("FL".into()), ..Fields::default() },
    Fields::default(), // no address text: an error for this row only
];
for r in parser.parse_fields_many(&rows) {
    match r {
        Ok(a) => println!("{:?} {:?}", a.to_display().lines(), a.diagnostics.warnings),
        Err(e) => println!("{e}"),
    }
}
```

The runnable tour is [`examples/quickstart.rs`](https://github.com/jeremeybingham/doorplate/blob/main/crates/doorplate/examples/quickstart.rs)
(`cargo run -p doorplate --example quickstart` in a clone). For CSV files without writing code, install
[the command-line tool](command-line.md); for pandas, Polars and DuckDB, use the
[Python package](python.md), which wraps this crate.

`doorplate::Anonymizer` rewrites address-like text so it can be shared: digits and unknown words are replaced by
others of the same length and case, and what decides how the parser reads a line stays. It is obfuscation that keeps
the shape, not anonymity; read the output before you share it. The rules and limits are in
[Anonymizing address data](anonymizing.md).

```rust
let a = doorplate::Anonymizer::with_seed(7).anonymize("123 N Zephyrmill Ave Apt 4, Miami, FL 33101");
assert!(a.text.contains(" N ") && a.text.contains(", FL 331") && !a.text.contains("Zephyrmill"));
```

## Features

| Feature | Default | Adds |
|---|---|---|
| `places-us` | yes | the national place and ZIP list, used to find and name the city |
| `rayon` | no | parallel `Parser::parse_many` and `parse_fields_many` |
| `corpus` | no | the golden-corpus loader and runner (`doorplate::corpus`); pulls in serde |
| `custom-layer` | no | `CustomLayer::from_sources` and `from_dir`: your own spellings, words, places and ZIPs on top of the shipped tables, reported in `Diagnostics::custom_layer`; pulls in `toml`. A layer can change a key ([Custom layers](custom-layers.md)) |

## The match key

`a.key(...)` identifies a property for deduplication and joins. It uses the street
parts, state and ZIP, not the city, and it is versioned: the `k3:` format will not
change in place. [Key format](key-format.md) is the contract. The
slug is for URLs and display; it is not unique.
