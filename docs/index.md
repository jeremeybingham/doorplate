# doorplate

Parse US addresses into components, with USPS Publication 28 and RESO output, a canonical match key, a URL-safe
slug, and diagnostics. A Rust library with a Python package and a command-line tool; no runtime dependencies, no data
to download, no machine-learned model, and parsing never panics.

```python
import doorplate

a = doorplate.parse("123 north main street apt 4, Miami FL 33101")
a.to_usps()["line1"]   # "123 N MAIN ST APT 4"
a.key()                # "k5:S|123|N|MAIN|ST||FL|33101"
```

[Try it in your browser](https://jeremeybingham.github.io/doorplate/demo/): the parser runs on your machine, nothing is sent. The page also [parses or anonymizes a whole CSV file](https://jeremeybingham.github.io/doorplate/demo/#csv), with a sample file of invented addresses.

## Where to go

| If you want to | Go to |
|---|---|
| Install it and parse an address | [Getting started](getting-started.md) |
| Use it from Python, a shell, Rust or a DataFrame | [Python](python.md), [Command line](command-line.md), [Rust](rust.md), [pandas, Polars and DuckDB](dataframes.md) |
| Understand what it does and why | [How it works](how-it-works.md), [Warnings](warnings.md), [The match key](key-format.md) |
| See how accurate and fast it is | [Accuracy and speed](benchmarks.md) |
| Add your own spellings, or share messy data safely | [Custom layers](custom-layers.md), [Anonymizing](anonymizing.md) |
| Switch from usaddress | [Coming from usaddress](usaddress-compat.md) |
| Compare with libpostal | [Compared with libpostal](libpostal-compat.md) |
| Look up a function or an option | [Python reference](python-api.md), [Command-line reference](cli.md), [Rust on docs.rs](https://docs.rs/doorplate) |
| Know what data it uses | [Data policy](data-policy.md), [Places](places.md), [State data](states/README.md) |
| Fix a bug, add a rule, run the tools | [Development](change-checklist.md): the checklist, the tools, the tests, the benchmarks, the roadmap |

Install and a first parse are in [Getting started](getting-started.md); the tours are the [Python guide](python.md),
the [command-line guide](command-line.md), the [Rust guide](rust.md) and [pandas, Polars and DuckDB](dataframes.md).

!!! warning "It parses and formats; it does not validate"
    doorplate does not check that an address exists or can receive mail. Pub 28 formatting is not deliverability, and
    a warning such as `zip_city_mismatch` is a hint about the input, not a verdict.

!!! note "Alpha"
    Expect rough edges. The match key is versioned (`k5:`) and may get new versions as the parser improves, so store
    the version prefix with your keys. Accuracy and speed are measurements on a few data sets, not guarantees.
    If it parses your addresses badly, please
    [open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md).
