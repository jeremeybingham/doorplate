# Python reference

The `doorplate` package: `pip install doorplate`, Python 3.10 or later. It formats and parses; it does not validate
that an address exists or can receive mail. This page is generated from the package's type stubs
(`crates/doorplate-py/python/doorplate/__init__.pyi`), so it describes the latest release (0.5.0) and, on the `latest`
version of this site, the code on `main`, which can be ahead of PyPI; the
[changelog](https://github.com/jeremeybingham/doorplate/blob/main/CHANGELOG.md) says what changed in each release. The tour is in the [package README](https://github.com/jeremeybingham/doorplate/blob/main/crates/doorplate-py/README.md) and the
[notebook](https://github.com/jeremeybingham/doorplate/blob/main/examples/quickstart.ipynb).

A result is a [`ParsedAddress`](#doorplate.ParsedAddress). Parsing never raises on odd input: it returns a result with
`warnings` (see [Warnings](warnings.md)). The one exception is [`ParseError`](#doorplate.ParseError), for input with no
address text at all; the batch functions return `None` for such an element instead. `default_state` is a lookup hint for
input with no state; it never fills `state`. `custom_layer` takes a [`CustomLayer`](#doorplate.CustomLayer) or a folder
path ([Custom layers](custom-layers.md)); a layer can change a key.

## Parsing one address

::: doorplate.parse
    options:
      heading_level: 3

::: doorplate.parse_fields
    options:
      heading_level: 3

::: doorplate.tag
    options:
      heading_level: 3

::: doorplate.parse_tokens
    options:
      heading_level: 3

::: doorplate.address_type
    options:
      heading_level: 3

## Parsing many

::: doorplate.parse_many
    options:
      heading_level: 3

::: doorplate.parse_fields_many
    options:
      heading_level: 3

## The result

::: doorplate.ParsedAddress
    options:
      heading_level: 3
      members_order: source

### Types of the values

The dictionaries a result returns are typed dictionaries:

::: doorplate.Highway
    options:
      heading_level: 3
      show_root_full_path: false
      members: false


::: doorplate.RuralRoute
    options:
      heading_level: 3
      show_root_full_path: false
      members: false


::: doorplate.Military
    options:
      heading_level: 3
      show_root_full_path: false
      members: false


::: doorplate.Place
    options:
      heading_level: 3
      show_root_full_path: false
      members: false


::: doorplate.Usps
    options:
      heading_level: 3
      show_root_full_path: false
      members: false


::: doorplate.Display
    options:
      heading_level: 3
      show_root_full_path: false
      members: false


::: doorplate.LayerInfoDict
    options:
      heading_level: 3
      show_root_full_path: false
      members: false


::: doorplate.Provenance
    options:
      heading_level: 3
      show_root_full_path: false
      members: false


::: doorplate.ParsedAddressDict
    options:
      heading_level: 3
      show_root_full_path: false
      members: false

## A parser with settings

::: doorplate.Parser
    options:
      heading_level: 3
      members_order: source

## Errors

::: doorplate.ParseError
    options:
      heading_level: 3

::: doorplate.LayerError
    options:
      heading_level: 3

## Custom layers

::: doorplate.load_layer
    options:
      heading_level: 3

::: doorplate.CustomLayer
    options:
      heading_level: 3
      members_order: source

## Anonymizing

::: doorplate.anonymize
    options:
      heading_level: 3

::: doorplate.Anonymizer
    options:
      heading_level: 3
      members_order: source

::: doorplate.Anonymized
    options:
      heading_level: 3

## Helpers for data frames and SQL

The three helpers import their library when called, so the package works without them
(`pip install "doorplate[pandas]"`, `"doorplate[polars]"` or `"doorplate[duckdb]"`).

::: doorplate.pandas
    options:
      heading_level: 3
      members_order: source

::: doorplate.polars
    options:
      heading_level: 3
      members_order: source

::: doorplate.duckdb
    options:
      heading_level: 3
      members_order: source
## Coming from usaddress

::: doorplate.compat
    options:
      heading_level: 3
      members_order: source
