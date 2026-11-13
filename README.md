# doorplate

[![CI](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml/badge.svg)](https://github.com/jeremeybingham/doorplate/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jeremeybingham/doorplate/graph/badge.svg)](https://codecov.io/gh/jeremeybingham/doorplate)
[![crates.io](https://img.shields.io/crates/v/doorplate.svg)](https://crates.io/crates/doorplate)
[![crates.io downloads](https://img.shields.io/crates/d/doorplate.svg)](https://crates.io/crates/doorplate)
[![doorplate-cli on crates.io](https://img.shields.io/crates/v/doorplate-cli.svg?label=doorplate-cli)](https://crates.io/crates/doorplate-cli)
[![doorplate-cli downloads](https://img.shields.io/crates/d/doorplate-cli.svg?label=doorplate-cli%20downloads)](https://crates.io/crates/doorplate-cli)
[![docs.rs](https://docs.rs/doorplate/badge.svg)](https://docs.rs/doorplate)
[![PyPI](https://img.shields.io/pypi/v/doorplate.svg)](https://pypi.org/project/doorplate/)
[![Wheels](https://github.com/jeremeybingham/doorplate/actions/workflows/wheels.yml/badge.svg)](https://github.com/jeremeybingham/doorplate/actions/workflows/wheels.yml)
[![License: MIT OR Apache-2.0](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](#license)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](crates/doorplate-py/README.md)
[![Rust 1.80+](https://img.shields.io/badge/rustc-1.80%2B-orange.svg)](Cargo.toml)

Parse US addresses into components, with USPS Publication 28 and RESO output, a canonical
match key, a URL-safe slug, and diagnostics. A Rust library with a Python package and a
command-line tool (abi3 wheels for Python 3.10 and later); no runtime dependencies, no data
to download, no machine-learned model, and parsing never panics.

**[Try it in your browser](https://jeremeybingham.github.io/doorplate/demo/)**: type an address and watch it
be taken apart, with the output, as you type, or drop in a CSV file and download it with the parsed columns added (the
columns of `doorplate parse-file`). The parser runs on your machine; nothing is sent anywhere.

This library formats and parses; it **does not validate** that an address exists or can
receive mail. Pub 28 formatting is not deliverability, and validation needs
postal-service-certified data; warnings such as `zip_city_mismatch` are hints about the
input, not verdicts.

> **Alpha release (0.6.0).** Expect rough edges; names in the API and the warning codes may still change before 1.0.
> The match key is versioned (`k5:`) and later versions will probably change it, so store
> the prefix with your keys and plan to re-key. `k5` has only been checked on the project's own data (public records). Accuracy and speed are measurements on a few datasets, not guarantees.
>
> **Help wanted: messy addresses.** If it parses your addresses badly (odd abbreviations, typos, cut-off lines, units in
> strange places, county or mailing-list exports), please
> [open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md)
> with a sample. I want to fix them. Private data can be anonymized first
> ([how](CONTRIBUTING.md#sharing-messy-data)).

## Quickstart

```sh
pip install doorplate
```

```python
import doorplate

a = doorplate.parse("123 north main street apt 4, Miami FL 33101")

a.street_name, a.unit_number        # ("MAIN", "4")
a.to_usps()["line1"]                # "123 N MAIN ST APT 4"
a.key()                             # "k5:S|123|N|MAIN|ST||FL|33101"
a.slug()                            # "123-n-main-st-apt-4-miami-fl-33101"
a.to_display()["line1"]             # "123 N Main St Apt 4" (mixed case, display only)
a.warnings                          # []
```

The same from the command line; the same address written another way gives the same key:

```sh
$ doorplate parse "123 N. Main St #4, miami, fl 33101" --usps
123 N MAIN ST # 4
MIAMI FL 33101
$ doorplate parse "123 N. Main St #4, miami, fl 33101" | jq -r .key
k5:S|123|N|MAIN|ST||FL|33101
```

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

To build from source, see [Getting started](https://doorplate.readthedocs.io/en/latest/getting-started/#install).

## Benchmarks
| 0.6.1 | doorplate | usaddress |
|---|---|---|
| Whole address right, [benchmark suite](docs/benchmark-suite.md), `natural` stratum (16,001 addresses written in five styles) | 98.7% | 96.1% |
| Whole address right, [geocode benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark) dev split (60,522 one-line addresses) | 94.4% | 88.1% |
| Addresses per second from Python, one thread (suite inputs, 4 CPUs) | about 82,000 | about 8,900 |

Measured against [usaddress](https://github.com/datamade/usaddress) on a few data sets (the geocode benchmark is Yin, Li and
Goldberg, [arXiv:2310.14360](https://arxiv.org/abs/2310.14360)), not promises for yours; every figure by build, the
caveats and how to rerun them: [benchmarks](docs/benchmarks.md) and [speed, size and memory](docs/speed-and-size.md).

## What it does not do

- It does not validate that an address exists or can receive mail.
- It does not geocode, match fuzzily, correct addresses, or handle international addresses.
  Recipient lines, landmarks and street corners are not modeled; text it cannot place goes to
  `unparsed` with a warning.
- It has no learned model. A misparse is fixed by a rule or a line of data, and you can add your own
  spellings and places with a [custom layer](docs/custom-layers.md).

## Where it is going

An alpha; a `k5` key is planned for 0.6.0. What is planned, what depends on what and what is deliberately not
planned (validation, geocoding, international addresses) is in [`docs/roadmap.md`](docs/roadmap.md).

## Documentation

**<https://doorplate.readthedocs.io/en/latest/>** is a searchable site built from [`docs/`](docs/README.md) (the index of
every page, for GitHub readers). Start with [Getting started](https://doorplate.readthedocs.io/en/latest/getting-started/).

| Page | Contents |
|---|---|
| [Python guide](https://doorplate.readthedocs.io/en/latest/python/), [command-line guide](https://doorplate.readthedocs.io/en/latest/command-line/), [Rust guide](https://doorplate.readthedocs.io/en/latest/rust/) | The tours, one per way of using it; the reference is [Python](https://doorplate.readthedocs.io/en/latest/python-api/), [command line](https://doorplate.readthedocs.io/en/latest/cli/) and [docs.rs](https://docs.rs/doorplate) |
| [pandas, Polars and DuckDB](https://doorplate.readthedocs.io/en/latest/dataframes/) | A column, split fields, a table or a CSV file, one call per shape; runnable versions in [`examples/`](examples/README.md) |
| [`docs/how-it-works.md`](docs/how-it-works.md), [`docs/places.md`](docs/places.md) | The pipeline and the design choices; the place data |
| [`docs/key-format.md`](docs/key-format.md), [`docs/warnings.md`](docs/warnings.md) | The match key (the contract); what each warning tells you |
| [`docs/custom-layers.md`](docs/custom-layers.md), [`docs/anonymizing.md`](docs/anonymizing.md) | Your own spellings and places; sharing messy data |
| [`docs/usaddress-compat.md`](docs/usaddress-compat.md) | Coming from usaddress: `import doorplate.compat as usaddress` |
| [`docs/benchmarks.md`](docs/benchmarks.md) | Accuracy, speed and size |
| [`CONTRIBUTING.md`](CONTRIBUTING.md), [`docs/roadmap.md`](docs/roadmap.md), [`CHANGELOG.md`](CHANGELOG.md) | Reporting and fixing a misparse; planned work; release notes |

## Disclaimer

doorplate is provided "as is", without warranty of any kind, under the [MIT](LICENSE-MIT) or
[Apache-2.0](LICENSE-APACHE) license at your option; the license text is what governs. In plain
terms: **use it at your own risk.** Nothing here guarantees that a parse, a warning, a match key
or a figure is correct, complete or fit for your purpose. Accuracy and speed numbers are
measurements on particular datasets, not promises for yours. doorplate parses and formats
addresses; it does **not validate** that an address exists or can receive mail, and Pub 28
formatting is not certified validation. Check its output before you rely on it for anything with
legal, financial, safety or delivery consequences.

doorplate is an independent project. It is not affiliated with, endorsed by or certified by the
US Postal Service, RESO, DataMade (the authors of usaddress) or any data source it cites; those
names are used only to say what the output follows or is compared with.

## License

Licensed under either of [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE) at your
option. The ZIP tables in `crates/doorplate/data/states/` and
`crates/doorplate/data/places/` are GeoNames data under CC BY 4.0; see
[`NOTICE`](NOTICE).

## About the author

I am Jeremey Bingham. I have worked in technology since 2007, with Python for about ten years
and Rust for about two. I spent years inside real estate data: the [Realtor Association of the
Palm Beaches / BeachesMLS](https://www.beachesmls.com/), the [Massachusetts Association of Realtors](https://www.marealtor.com/), where I was Director of
Information Technology, and [HouseCanary](https://www.housecanary.com/), where I built APIs over residential property records. I
also published [reso-client](https://github.com/jeremeybingham/reso_client), a Rust client for the
RESO Web API. My resume is at [resume.jeremeybingham.com](https://resume.jeremeybingham.com).
