# Compared with libpostal

[libpostal](https://github.com/openvenues/libpostal) is a C library that parses and normalizes street addresses from
anywhere in the world with a statistical model. `doorplate` is a US-only parser that works with rules and place data and
also standardizes, builds a key and reports diagnostics. This page is for people who use libpostal or are choosing between
the two: what each does, where the outputs line up, and what is not comparable.

**This page is a written comparison, not a measurement.** No libpostal accuracy or speed figure is reported here, because
libpostal has not been run against `doorplate` yet. When it is, the figures go in [`benchmarks.md`](benchmarks.md) and
[`speed-and-size.md`](speed-and-size.md), measured with the **Senzing model** (see "The model the comparison will use").
The facts about libpostal below come from its README and from Senzing's model repository, read on 2026-11-07; what those
pages do not say is marked as not stated. Examples are invented. This library formats and parses; it does not validate that
an address exists or can receive mail.

## Two different tools

| | libpostal | doorplate |
|---|---|---|
| Language, license | C; MIT. Official bindings for Python (`pypostal`, installed as `postal`), Ruby, Go, Java, PHP and NodeJS; others are unofficial | Rust; MIT or Apache-2.0. A Python package and a command-line tool |
| Scope | The world: the parser is trained for every inhabited country; normalization covers "60+ languages" | The United States only, by design |
| How it parses | A conditional random field (CRF) trained on over a billion addresses (OpenStreetMap, OpenAddresses and templates for formatting addresses) | Rules, a lexicon and place data; no model to train or ship |
| What it returns | `parse_address`: a flat list of labeled pieces. `expand_address`: normalized variants of the input | Components, USPS Publication 28 lines, RESO fields, a key, a slug, warnings and byte spans |
| Standardization | Normalization for search, not Pub 28 | Pub 28 output (`to_usps`), display and long forms |
| Diagnostics | None beyond the labels | Warnings, the unparsed text, address type |
| Install | Build from source (a C toolchain and autotools), then download a model of about 1.8 GB (about 2.2 GB for the Senzing model); the README asks for "a few GB" of disk for the data. `pypostal` needs the C library first | `pip install doorplate`: one wheel of about 2 MB, nothing to download |
| Stated speed and memory | 10 to 30 thousand addresses per second in one thread on the platforms the authors tried; designed to fit in under 1 GB of RAM per process | See [`speed-and-size.md`](speed-and-size.md) |
| Stated accuracy | 99.45% full-parse accuracy (every token right) on its own held-out data; the README does not name that data further | See [`benchmarks.md`](benchmarks.md) |

Two cautions on the last two rows. libpostal's figure is on addresses like the ones it was trained on, from all over the
world, so it does not say how libpostal reads US government exports or messy county data; the same is true of any score
`doorplate` has on its own sets. And the figures are not measured the same way: neither is a claim about the other.

The README does not say when the last release was or whether the project is still maintained. Check the repository before
you depend on it.

## What the output looks like

libpostal labels pieces of one input string. Its parser can use any label defined in its training data; the README lists
twenty. The table says where each lands in `doorplate`, for a US address.

| libpostal label | In doorplate |
|---|---|
| `house` (a venue or building name) | `building` |
| `category`, `near` (search phrases such as a type of shop and "near") | no equivalent: they belong to place search, not to mailing addresses |
| `house_number` | `street_number` |
| `road` | the street name with its directionals and suffix, which `doorplate` keeps as separate fields (`street_dir_prefix`, `street_name`, `street_suffix`, `street_dir_suffix`). Highway and rural-route text is in `road` too; `doorplate` has fields for them (`highway`, `rural_route`) |
| `unit` | `unit_type` and `unit_number` (and the second unit) |
| `level` (a floor) | a unit with the Pub 28 floor designator |
| `staircase`, `entrance` | no equivalent |
| `po_box` | `po_box` |
| `postcode` | `zip5` and `zip4` |
| `suburb`, `city_district` | no separate field: a neighborhood or borough written where the city goes is the `city` as written, and `place` reports the mail name when the place list knows it |
| `city` | `city` |
| `island`, `country_region`, `world_region` | no equivalent |
| `state_district` (a county) | no equivalent |
| `state` | `state` |
| `country` | a trailing `USA` or `US` is dropped with the warning `country_ignored` |

So a comparison of the two is a comparison on the fields they share: house number, road (as one field), unit, PO box,
city, state and ZIP. `doorplate` has more fields on the US side (the Pub 28 lines, the key, the warnings); libpostal has
more on the world side. [`usaddress-compat.md`](usaddress-compat.md) has the same kind of mapping for usaddress, and the
scoring rules there (compare by character span, fold the street parts) are the ones a libpostal comparison would reuse.

## Normalization and keys

`expand_address` turns one messy address into several normalized spellings so that two records written differently can be
matched by search or hashing. `doorplate` goes the other way: it reads an address into one canonical form, and the
[match key](key-format.md) and the slug are what two records are compared on. A key is one string per address, not a set of
variants, so the two are alternatives for the same job (finding duplicates), not equivalents. libpostal's README does not
name a function for finding near-duplicates; it presents deduplication as a use of the library.

## The model the comparison will use

libpostal ships a default model and an alternative made by Senzing, "for improved parsing on US, UK and Singapore
addresses and improved US rural route address handling". The comparison will use **the Senzing model from the start**, not the
default, because it is the one meant for US data. Facts from the README and from Senzing's repository,
[`Senzing/libpostal-data`](https://github.com/Senzing/libpostal-data) (Apache-2.0):

- It is chosen when libpostal is built: `./configure --datadir=DIR MODEL=senzing`. The data for it is about 2.2 GB, against 1.8 GB
  for the default.
- Senzing trained it on OpenAddresses, OpenStreetMap and data it generated (about 1.2 billion records from over 230 countries),
  and says it parsed 4.3% better than the default model on its own test set. That is Senzing's figure, on its test set.
- Senzing lists its changes by version: 1.0.0 improved US rural routes, US addresses without a state, Singapore and British
  addresses; 1.1.0 Japanese addresses and Mexican state codes; 1.2.0 Chinese, Taiwanese and Korean addresses. The latest
  version on the page is 1.2.0.
- Not stated by either page: which model version `MODEL=senzing` downloads, and how to choose a model when libpostal is
  already built. The measurement will therefore record the libpostal commit, the model version and the checksum of the data it
  used, and quote them next to every figure.

A secondary check already exists: Senzing publishes the test set it scores its models on, and `doorplate` was scored on its US
rows without running libpostal ([`benchmarks.md`](benchmarks.md), "Senzing's libpostal test set"). That score is not a
comparison with libpostal.

## What a fair comparison needs

- The same inputs for both, and the same scoring rule (whole address right, on the fields both have), with the intervals the
  [benchmark suite](benchmark-suite.md) prints. The suite's `hard` stratum was drawn from the blind spots of `doorplate` and
  usaddress, so it is not a fair test of a third library; `natural` and the outside sets are.
- Say what each was trained near. libpostal was trained on OpenStreetMap and OpenAddresses, and the National Address Database
  that the suite draws on overlaps OpenAddresses. `doorplate` has no training data, but its rules were written while reading
  some of the sets (the geocode benchmark's `test` split, see [`benchmarks.md`](benchmarks.md)), so a score on those is optimistic.
- Cost beside accuracy: install effort, model size, model load time, memory and addresses per second on the suite's
  4-CPU, 8 GB profile, with the load time reported apart from the per-address speed.
- Defaults only: no retraining of either side.

## Sources

The libpostal [README](https://github.com/openvenues/libpostal), the [`pypostal` README](https://github.com/openvenues/pypostal)
and Senzing's [`libpostal-data`](https://github.com/Senzing/libpostal-data), all read on 2026-11-07. Plan and status of the
comparison: issue [#215](https://github.com/jeremeybingham/doorplate/issues/215).
