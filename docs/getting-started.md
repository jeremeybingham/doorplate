# Getting started

Install doorplate, parse an address, and see what comes back. It formats and parses; it does **not validate** that an
address exists or can receive mail.

## Install

**Python 3.10 or later** (one abi3 wheel per platform: Linux, macOS, Windows):

```sh
pip install doorplate                 # the parser
pip install "doorplate[pandas]"       # plus DataFrame helpers (or [polars], [duckdb])
```

**Rust** (1.80 or later):

```sh
cargo add doorplate                   # the library
cargo install doorplate-cli           # the `doorplate` command
```

From source, see the [Python guide](python.md#install) and the [repository](https://github.com/jeremeybingham/doorplate).

## Parse an address

Python:

```python
import doorplate

a = doorplate.parse("123 north main street apt 4, Miami FL 33101")
a.to_usps()["line1"]   # "123 N MAIN ST APT 4"
a.key()                # "k4:S|123|N|MAIN|ST||FL|33101"
a.warnings             # []
```

Command line:

```sh
$ doorplate parse "123 N. Main St #4, miami, fl 33101" --usps
123 N MAIN ST # 4
MIAMI FL 33101
$ doorplate parse "123 N. Main St #4, miami, fl 33101" | jq -r .key
k4:S|123|N|MAIN|ST||FL|33101
```

Rust:

```rust
use doorplate::{KeyOptions, Parser};

let a = Parser::new().parse("123 north main street apt 4, Miami FL 33101")?;
a.to_usps().line1;                // Some("123 N MAIN ST APT 4")
a.key(KeyOptions::property());    // Some("k4:S|123|N|MAIN|ST||FL|33101")
```

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
change in place. [`docs/key-format.md`](key-format.md) is the contract.
**The slug** is for URLs and display; it is not unique. **Warnings** are stable
snake_case codes (`missing_zip`, `unparsed_remainder`, `dual_address`, ...) meant
for a database column; the list is in [`docs/how-it-works.md`](how-it-works.md).

Input does not have to be tidy. Messy and incomplete addresses still parse, with
warnings that say what is missing:

```python
>>> a = doorplate.parse("12 elm st. #5 orlando fl")
>>> a.to_usps()["line1"], a.key(), a.warnings
('12 ELM ST # 5', 'k4n:S|12||ELM|ST||FL|', ['missing_zip'])
```

With no ZIP the key starts `k4n:` (a weaker match), and `missing_zip` says why.
Only input with no address text at all is an error.

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

## Where next

| You have | Read |
|---|---|
| A script, in Python | [Python guide](python.md), then the [reference](python-api.md) |
| A column, a table or a CSV file | [pandas, Polars and DuckDB](dataframes.md), or the [command line](command-line.md) |
| Rust code | [Rust guide](rust.md) |
| Addresses that misparse | [Custom layers](custom-layers.md); to report them safely, [Anonymizing data](anonymizing.md) |
| usaddress code | [Coming from usaddress](usaddress-compat.md) |
