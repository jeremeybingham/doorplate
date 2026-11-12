# Python guide

This library formats and parses; it does not validate that an address exists or can receive mail.

```python
import doorplate as dp

a = dp.parse("123 north main street apt 4, Miami FL 33101")
a.street_name          # "MAIN"
a.unit_number          # "4"
a.place                # {"name": "MIAMI", "state": "FL", "county": "DADE", ...}
a.warnings             # []
a.to_usps()["line1"]   # "123 N MAIN ST APT 4"
a.to_display()["line1"]  # "123 N Main St Apt 4" (to_long(): "123 North Main Street Apartment 4"); display only, not Pub 28
a.key()                # "k5:S|123|N|MAIN|ST||FL|33101"
a.slug()               # "123-n-main-st-apt-4-miami-fl-33101"
a.to_reso()            # RESO Data Dictionary 2.0 fields
a.to_dict()            # everything above as plain Python values, and provenance (`library_version`, `state_data_version`)

dp.parse_fields(line1="THE COVE", line2="1111 ASBURY WAY",
                city="Orlando", state="FL", zip="32801")
dp.parse_many(["1 Main St, Miami FL", "PO Box 5, Tampa FL"])  # GIL released
dp.parse_fields_many(line1=["1 Main St", "PO Box 5"], city=["Miami", "Tampa"])
dp.parse("281 EVELYN DR DOTHAN", default_state="AL").city     # "DOTHAN"
```

Install: [Getting started](getting-started.md#install) (Python 3.10 or later; the extras are `[pandas]`, `[polars]` and
`[duckdb]`). This page is the tour; every function and class is in the [Python reference](python-api.md).

- Unusable input (no address text at all) raises `ParseError`, a `ValueError`; in `parse_many` that element is `None`.
  Anything else comes back with `warnings` ([what each one tells you](warnings.md)).
- `default_state` is a lookup hint for input with no state; it never fills `state`. A value that is not a US state, DC or
  territory raises `ValueError`.

## The API

| Call | Returns |
|---|---|
| `parse(text, default_state=None)` | a `ParsedAddress` |
| `parse_fields(line1=, line2=, city=, state=, zip=, default_state=None)` | a `ParsedAddress` from pre-split fields |
| `parse_fields_many(line1=, line2=, city=, state=, zip=, default_state=None)` | a batch of pre-split rows, given as columns (lists or tuples; an element may be `None`); any of the columns, all the same length |
| `parse_many(texts, default_state=None)` | a list of `ParsedAddress` (`None` for an element with no address text), in order; parses in parallel with the GIL released |
| `Parser(default_state=None)` | an object with the same `parse`, `parse_fields` and `parse_many` |
| `tag(text)` | `(dict, type)` with usaddress's labels and `"Street Address"` / `"PO Box"` / `"Ambiguous"` |
| `parse_tokens(text)` | `[(token, label)]` with usaddress's labels |
| `load_layer(path)`; `custom_layer=` on every call above | a `CustomLayer`: your own spellings, words, places and ZIPs on top of the shipped tables ([Custom layers](custom-layers.md)) |
| `Anonymizer(seed=None)`, `.anonymize(text)`, `.anonymize_many(texts)`; `anonymize(text, seed=None)` | an `Anonymized` (`text`, `faithful`), or just the text for `anonymize()` ([Anonymizing data](anonymizing.md)) |
| `address_type(text)` | `street`, `po_box`, `rural_route`, `military`, `general_delivery`, `dual` or `unknown` |

A `ParsedAddress` is read-only and typed (`py.typed`). It has the components (`street_number`, `street_name`, `unit_number`,
`city`, `state`, `zip5`, ...), `warnings`, `unparsed` and `input`, and computes its output formats when you ask, so take
only what you need: `key()`, `slug()`, `to_usps()`, `to_display()`, `to_long()`, `to_reso()`, `to_usaddress_tags()` and
`to_dict()`. The fields and methods are in the [reference](python-api.md); the key is a versioned contract
([key format](key-format.md)), and the slug is for display.

## A state hint

When the input names no state and has no known ZIP, `default_state` lets the parser look the city up in that state:
`281 EVELYN DR DOTHAN` finds `DOTHAN` with `AL`. It is a hint, never a fill: `state` stays empty, `missing_state` still
fires, and `default_state_applied` says when the hint decided something.

## Next

- Whole columns and files: [pandas, Polars and DuckDB](dataframes.md); the same parser from a shell, [command-line guide](command-line.md), or from Rust, [Rust guide](rust.md).
- Your own spellings and places: [Custom layers](custom-layers.md). Sharing messy rows: [Anonymizing data](anonymizing.md).
- A script that uses `usaddress.parse` and `usaddress.tag`: [Coming from usaddress](usaddress-compat.md).
