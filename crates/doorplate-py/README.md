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

> **Alpha release (0.2.0).** Expect rough edges. The match key is versioned (`k2:`) and
> will probably get new versions as the parser improves, so store the version prefix
> with your keys and plan to re-key. Accuracy and speed are measurements on a few
> datasets, not guarantees.
>
> **Help wanted: messy addresses.** If it parses your addresses badly, please
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
a.street_name          # "MAIN"
a.unit_number          # "4"
a.place                # {"name": "MIAMI", "state": "FL", "county": "DADE", ...}
a.warnings             # []
a.to_usps()["line1"]   # "123 N MAIN ST APT 4"
a.to_display()["line1"]  # "123 N Main St Apt 4" (to_long(): "123 North Main Street Apartment 4"); display only, not Pub 28
a.key()                # "k2:S|123|N|MAIN|ST||FL|33101"
a.slug()               # "123-n-main-st-apt-4-miami-fl-33101"
a.to_reso()            # RESO Data Dictionary 2.0 fields
a.to_dict()            # everything above as plain Python values

dp.parse_fields(line1="THE COVE", line2="1111 ASBURY WAY",
                city="Orlando", state="FL", zip="32801")
dp.parse_many(["1 Main St, Miami FL", "PO Box 5, Tampa FL"])  # GIL released
dp.parse_fields_many(line1=["1 Main St", "PO Box 5"], city=["Miami", "Tampa"])
dp.parse("281 EVELYN DR DOTHAN", default_state="AL").city     # "DOTHAN"
```

- Unusable input (no address text at all) raises `ParseError`, a `ValueError`; in
  `parse_many` that element is `None`. Anything else comes back with `warnings`.
- `default_state` is a lookup hint for input with no state; it never fills `state`.
  A value that is not a US state, DC or territory raises `ValueError`.
- `confidence` is reserved and always `None`: no score is computed.

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

## The API

| Call | Returns |
|---|---|
| `parse(text, default_state=None)` | a `ParsedAddress` |
| `parse_fields(line1=, line2=, city=, state=, zip=, default_state=None)` | a `ParsedAddress` from pre-split fields |
| `parse_fields_many(line1=, line2=, city=, state=, zip=, default_state=None)` | the same as a batch of pre-split rows, given as columns (lists or tuples; an element may be `None`). Give any of the columns; they must have the same length |
| `parse_many(texts, default_state=None)` | a list of `ParsedAddress` (or `None` for an element with no address text), in order; parses in parallel with the GIL released |
| `Parser(default_state=None)` | an object with the same `parse`, `parse_fields` and `parse_many` |
| `tag(text)` | `(dict, type)` with usaddress's labels and `"Street Address"` / `"PO Box"` / `"Ambiguous"` |
| `parse_tokens(text)` | `[(token, label)]` with usaddress's labels |
| `address_type(text)` | `street`, `po_box`, `rural_route`, `military`, `general_delivery`, `dual` or `unknown` |

A `ParsedAddress` is read-only and typed (`py.typed`, stubs in `__init__.pyi`). It
has the components (`street_number`, `street_dir_prefix`, `street_name`,
`street_suffix`, `street_dir_suffix`, `unit_type`, `unit_number`,
`second_unit_type`, `second_unit_number`, `po_box`, `attention`, `building`, `city`,
`state`, `zip5`, `zip4`, `military_post_office`), the structured shapes (`highway`,
`rural_route`, `military`, `place`, plain dicts), `general_delivery`, `warnings`
(stable snake_case codes), `unparsed`, `input` and `confidence`, and the methods
`key(unit=False)`, `slug()`, `to_usps(max_line=None)`, `to_display()`, `to_long()`,
`to_reso()`, `to_usaddress_tags()`, `tag()`, `address_type()`, `repeated_labels()` and
`to_dict()`.

A `ParsedAddress` computes its output formats when you ask, so take only what you
need. The key is a versioned contract
([key format](https://github.com/jeremeybingham/doorplate/blob/main/docs/key-format.md));
the slug is for display.

## Your data, by shape

Pick the call that matches how your addresses arrive; all of them give the same components, keys and warnings.

| Your data | Use |
|---|---|
| A column of whole addresses, in pandas or Polars | `doorplate.pandas.parse_column` / `doorplate.polars.parse_column` |
| The same in DuckDB (a table, or a CSV or Parquet file it reads) | `doorplate_parse(address)` in SQL, or `doorplate.duckdb.parse_column` on a relation |
| Separate columns (street line, unit line, city, state, ZIP), complete or with gaps | `parse_fields_many(line1=[...], ...)`, or `doorplate_parse_fields(...)` in DuckDB |
| A mix of street addresses, PO boxes, rural routes, military, units in line 2, missing ZIPs | one call parses them all; `address_type`, `warnings` and `key` say which is which |
| Any list of strings | `parse_many` (all cores, GIL released) |
| A CSV file with no Python | the `doorplate` command: [`doorplate-cli`](https://crates.io/crates/doorplate-cli), `doorplate parse-file in.csv --column address -o out.csv` |

Runnable versions with several data shapes: the
[examples](https://github.com/jeremeybingham/doorplate/tree/main/examples) (a notebook with pandas, Polars and DuckDB
sections, and a pipeline for each).

## Batches, pandas, Polars and DuckDB

`parse_many(texts)` takes a list or tuple of strings, releases the GIL, parses in
parallel with Rust threads, and returns the results in order. On 100,000 addresses
with 4 CPUs, the benchmark suite's profile (`crates/doorplate-py/benchmarks/bench_batch.py`, run under
`taskset -c 0-3` with `RAYON_NUM_THREADS=4`; more cores make the batch rows faster):

| | Time | Per second | Speed-up |
|---|---|---|---|
| a loop of `parse` | 1.79 s | 56,000 | 1x |
| `parse_many` | 0.62 s | 162,000 | 2.9x |
| `parse_many` and a pandas DataFrame of 7 columns | 0.77 s | 131,000 | 2.3x |
| `parse_many` and a Polars DataFrame of 7 columns | 0.69 s | 144,000 | 2.6x |
| DuckDB, `doorplate_parse(a)` with 7 columns | 0.64 s | 157,000 | 2.8x |

**Helpers.** Install the extra and parse a column in one call:

```python
from doorplate.polars import parse_column   # or doorplate.pandas

out = df.hstack(parse_column(df["address"]))                    # Polars
out = df.join(parse_column(df["address"], default_state="FL"))  # pandas
```

`parse_column(series, *, columns=None, prefix="addr_", default_state=None)` returns a
DataFrame with one string column per name, in the same order (and, in pandas, the
same index) as the input. A null, blank or non-string row, or one with no address
text, is null in every column. The default columns are `street_number`,
`street_dir_prefix`, `street_name`, `street_suffix`, `street_dir_suffix`,
`unit_type`, `unit_number`, `city`, `state`, `zip5`, `zip4`, `address_type`, `key`,
`slug` and `warnings` (codes joined by commas). `AVAILABLE_COLUMNS` in either module
lists the rest (`key_unit`, `usps_line1`, `usps_line2`, `usps_last_line`, `po_box`,
`attention`, `building`, `unparsed`, ...). They are built over `parse_many`.

**DuckDB.** `pip install "doorplate[duckdb]"`, then register two functions on a connection and use them in SQL:

```python
import duckdb
from doorplate import duckdb as dd

con = duckdb.connect()
dd.register(con, columns=["street_name", "city", "state", "zip5", "key"])
con.sql("SELECT doorplate_parse(address).street_name, doorplate_parse(address).key FROM addresses")
con.sql("SELECT doorplate_parse_fields(line1, line2, city, state, zip).key FROM split")

rel = dd.parse_column(con.table("addresses"), "address", connection=con)   # input columns + addr_* columns, lazy
```

`doorplate_parse` returns a STRUCT of VARCHAR fields (`columns` defaults to the same list as the other helpers; `AVAILABLE_COLUMNS` has the rest) and NULL for a NULL, blank or no-address-text row. Each row is parsed once however many fields you read, in batches of 2,048 rows that Rust parses in parallel with the GIL released. Choose only the columns you need: building every column costs more (about 154,000 addresses/s with all 15 against 238,000 with 7). `parse_column` stays lazy, so it works on tables larger than memory. Pass `connection=` unless the relation came from `duckdb.sql(...)`.

**Polars by hand** (when you want other fields):

```python
import polars as pl
import doorplate as dp

df = pl.read_csv("addresses.csv")
parsed = dp.parse_many(df["address"].fill_null("").to_list())  # None for a blank row

cols = ["street_number", "street_name", "street_suffix", "unit_number", "city", "state", "zip5"]
flat = pl.DataFrame(
    {f"addr_{c}": [getattr(a, c) if a else None for a in parsed] for c in cols}
    | {
        "addr_key": [a.key() if a else None for a in parsed],
        "addr_warnings": [",".join(a.warnings) if a else None for a in parsed],
    },
    schema={f"addr_{c}": pl.String for c in cols}
    | {"addr_key": pl.String, "addr_warnings": pl.String},
)
out = df.hstack(flat)
```

(Give the schema: a column that is `None` in every row would otherwise be typed
`Null`.) For every field, build structs from `to_dict()` and pick fields from them:

```python
full = pl.DataFrame([a.to_dict() if a else None for a in parsed], infer_schema_length=None)
full.select(
    "street_name",
    pl.col("place").struct.field("name").alias("place_name"),
    pl.col("usps").struct.field("line1").alias("usps_line1"),
)
```

**pandas by hand:**

```python
import pandas as pd
import doorplate as dp

df = pd.read_csv("addresses.csv")
parsed = dp.parse_many(df["address"].fillna("").tolist())  # None for a blank row

cols = ["street_number", "street_name", "street_suffix", "unit_number", "city", "state", "zip5"]
flat = pd.DataFrame([{c: getattr(a, c) for c in cols} if a else {} for a in parsed])
flat["key"] = [a.key() if a else None for a in parsed]
flat["warnings"] = [",".join(a.warnings) if a else None for a in parsed]
out = pd.concat([df, flat.add_prefix("addr_")], axis=1)
```

For every field with pandas, use `to_dict()` and
`pd.json_normalize([a.to_dict() if a else {} for a in parsed])`.

Calling `to_dict()` on every row costs about as much as parsing again (a loop with
`to_dict` ran at 26,000 per second), and reading attributes from 100,000 Python
objects is now most of the time, so pick columns when you can. Pre-split columns
(`line1`, `city`, ...): call `parse_fields_many(line1=df["line1"].tolist(), city=...)`.

## Coming from usaddress

| usaddress | `doorplate` |
|---|---|
| `usaddress.parse(s)` | `parse_tokens(s)`: `[(token, label)]` |
| `usaddress.tag(s)` | `tag(s)`: `(dict, "Street Address" \| "PO Box" \| "Ambiguous")` |
| `RepeatedLabelError` | not raised: the runs are joined and `parse(s).repeated_labels()` lists the labels |
| (none) | `parse(s).address_type()`: `street`, `po_box`, `rural_route`, `military`, `general_delivery`, `dual`, `unknown` |
| (none) | `parse(s, default_state="FL")`: a state hint for input with no state |

Tokens that cannot be placed are left out of `tag()`, and some usaddress labels
(landmarks, corners, recipients) are not modeled. `parse_tokens` also cuts a few strings into different tokens
from `usaddress.parse` (`#4` stays one token, and a comma with no space after it ends a token differently), so
compare labels by character span, not by token index
([issue 78](https://github.com/jeremeybingham/doorplate/issues/78)). The mapping and the differences:
[usaddress compatibility](https://github.com/jeremeybingham/doorplate/blob/main/docs/usaddress-compat.md).

## Accuracy and speed

| | doorplate | usaddress |
|---|---|---|
| Whole address right, benchmark suite, `natural` stratum (16,001 addresses written in five styles) | 98.3% | 96.1% |
| Whole address right, geocode benchmark dev split (60,522 one-line addresses) | 94.4% | 88.1% |
| Addresses per second, one thread (suite inputs) | about 33,900 | about 9,100 |
| Addresses per second, `parse_many` on 4 threads | about 120,000 | about 9,100 (no batch call) |
| Installed size | 1.8 MB wheel | 4.8 MB with dependencies |

The suite is 19,586 labeled addresses that neither library was made from (anonymized National Address Database
rows with invented numbers, plus PO boxes, routes, military and hand-labeled shapes); it also holds both
libraries' known blind spots on purpose, so read its `natural` stratum as the estimate for ordinary input. Speed is
on 4 CPUs, 8 GB. These are measurements on a few data sets, not promises for yours. Method and every other figure:
[benchmarks](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md); how to rerun them:
[`benchmarks/README.md`](https://github.com/jeremeybingham/doorplate/blob/main/benchmarks/README.md).

## More

- [Project README](https://github.com/jeremeybingham/doorplate#readme): what it does,
  the Rust library, the command-line tool.
- [How it works](https://github.com/jeremeybingham/doorplate/blob/main/docs/how-it-works.md),
  [benchmarks](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmarks.md)
  and the [roadmap](https://github.com/jeremeybingham/doorplate/blob/main/docs/roadmap.md)
  (a confidence score and customization packs are planned).
- [Examples](https://github.com/jeremeybingham/doorplate/tree/main/examples): a
  notebook tour (rare shapes, place data, pandas, Polars, DuckDB, the command line) and a pipeline for each
  DataFrame library.

Licensed under either of MIT or Apache-2.0 at your option.
