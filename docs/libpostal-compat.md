# Compared with libpostal

[libpostal](https://github.com/openvenues/libpostal) is a C library that parses and normalizes street addresses from
anywhere in the world with a statistical model. `doorplate` is a US-only parser that works with rules and place data and
also standardizes, builds a key and reports diagnostics. This page compares the two: what each does, where the outputs
line up, and the first measurements (one run, 2026-11-07, to be repeated).

The figures in "Measured so far" are notes from that first run, not the published figures; the published ones will go in
[`benchmarks.md`](benchmarks.md) and [`speed-and-size.md`](speed-and-size.md). The facts about libpostal come from its
README and from Senzing's model repository, read on 2026-11-07; what those pages do not say is marked as not stated.
Examples are invented. This library formats and parses; it does not validate that an address exists or can receive mail.

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
world, so it does not say how libpostal reads US government exports or messy county data. And the figures are not measured
the same way: neither is a claim about the other.

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

So a comparison is on the fields they share: house number, road (as one field), unit, PO box, city, state and ZIP. The
scoring rules are the ones in [`usaddress-compat.md`](usaddress-compat.md#scoring-rules), with the libpostal mapping below.

## Normalization and keys

`expand_address` turns one messy address into several normalized spellings so that two records written differently can be
matched by search or hashing. `doorplate` reads an address into one canonical form instead: the [match key](key-format.md)
and the slug are what two records are compared on. A key is one string per address, not a set of variants, so the two are
alternatives for the same job (finding duplicates), not equivalents.

## The model the comparison uses

libpostal ships a default model and an alternative from Senzing, "for improved parsing on US, UK and Singapore addresses".
The comparison uses **the Senzing model from the start**, because it is the one meant for US data. It is chosen when
libpostal is built (`./configure ... MODEL=senzing`); its data is about 2.2 GB, against 1.8 GB for the default.

- Neither the README nor Senzing's repository
  ([`Senzing/libpostal-data`](https://github.com/Senzing/libpostal-data), Apache-2.0) says which model version `MODEL=senzing`
  fetches, or how to choose one after the build. The build on 2026-11-07 fetched the Senzing **1.2.0 parser**.
- Senzing's own figure (4.3% better than the default on its test set) is not a comparison with libpostal.
- Every libpostal figure therefore carries the libpostal commit, the model version and a checksum of the data directory,
  which the comparison tools print. Senzing's published US score is in [`benchmarks.md`](benchmarks.md#other-checks).

## Running the comparison

The comparison tools run libpostal in its own folder and virtualenv, so doorplate's environment does not need the C library.
Build it once (a C toolchain with `autoconf`, `automake` and `libtool`; about 3 GB of data):

```sh
git clone https://github.com/openvenues/libpostal src && cd src && ./bootstrap.sh
./configure --prefix=$HOME/projects/libpostal-senzing/install --datadir=$HOME/projects/libpostal-senzing/data MODEL=senzing
make -j8 && make install
uv venv --python 3.13 ../venv
CFLAGS="-I$HOME/projects/libpostal-senzing/install/include" LDFLAGS="-L$HOME/projects/libpostal-senzing/install/lib" \
  uv pip install -p ../venv/bin/python postal
```

Then, from the repository, with `--libpostal-home` (default `$LIBPOSTAL_HOME`, then `~/projects/libpostal-senzing`):

```sh
python benchmarks/suite.py compare --with-libpostal
python tools/compare/compare_usaddress.py --out report.md gold FILES.xml --with-libpostal
```

Both add a third column to a table of **common labels**, beside the unchanged two-way tables. The common set folds usaddress's
labels because libpostal gives `unit` and `po_box` as one piece (street parts are `StreetName`, occupancy is `Occupancy`, box
type and identifier are `USPSBox`). A label with no match (`category`, `near`, `country_region`, `world_region`) never agrees
with a gold label. `suburb`, `city_district`, `island` and `state_district` count as `PlaceName`, and `level`, `staircase` and
`entrance` as `Occupancy`. *Shared labels* leaves out records with a gold label libpostal cannot produce; *all records* leaves
nothing out. `tools/compare/test_libpostal_provider.py` tests the mapping on invented addresses.

## Measured so far (2026-11-07; one run, before the release)

One run: libpostal commit `25099c5`, the Senzing 1.2.0 parser (data checksum `7afb91d6ef19`), and doorplate on a 0.6.0 pre-release build (`main` on that
date; the accuracy rows were not re-run for the release). The two speed rows are a later run of all three in one session, on
0.6.1 (`9f2418b`, the same parser code as the tag) on 2026-11-13, usaddress from its cache. Accuracy is the share of records right (whole address, on the fields both have), with common labels, and the suite's
intervals are 95% Wilson. Speed is the best-of-N method on an otherwise idle machine, with the suite's 4-CPU, 8 GB profile. Timings
on this machine vary by 10 to 60% from run to run, so read ratios, not absolute figures; the model load time is left out of
every timing and reported apart.

| Measure | doorplate | usaddress | libpostal |
|---|---|---|---|
| Suite, `natural`, shared labels (15,275) | 98.8% | 97.2% | 96.4% |
| Suite, `natural`, all records (16,001) | 98.3% | 96.3% | 93.8% |
| Suite, whole suite, shared labels (18,120) | 95.1% | 89.0% | 94.5% |
| Suite, whole suite, all records (19,586) | 92.4% | 86.0% | 89.5% |
| Suite, `hard` stratum (2,585) | 55.1% | 20.2% | 65.8% |
| Suite, `hand` stratum (1,000) | 94.3% | 90.3% | 80.3% |
| usaddress's test files, not in its training files (2,248) | 99.1% | 100.0% | 98.1% |
| Geocode benchmark `dev` (60,522) | 94.3% | 88.1% | 80.0% |
| libpostal's own US tests (53 cases) | 86.8% | 90.6% | 96.2% |
| Senzing's test set, US rows (2,233) | 97.6% | 90.0% | 98.6% |
| Strings per second, suite, one thread | 76,748 (`parse_tokens`); 105,293 (`parse_many`) | 9,297 | 14,337 (one process) |
| Strings per second, suite, four workers | 304,753 (`parse_many`, four threads) | n/a | 46,524 (four processes) |
| Memory after loading | 17 MB | n/a | 2,950 MB per process |

How to read it:

- **Ordinary input.** On the suite's `natural` records doorplate leads libpostal by 2.4 to 4.5 points. libpostal leads on `hard`,
  which was drawn from doorplate's and usaddress's blind spots, so that row is not a fair test of a third library. usaddress's
  own test files are its regression tests, so its near 100% says nothing.
- **The geocode `dev` gap.** The inputs are one line with no commas. When the city is rare, misspelled or several words,
  libpostal's `road` runs on into it: the biggest class of its wrong tokens is a city word read as part of the road. Case is not
  the cause (uppercase and title-case inputs parsed identically on a 3,000-address sample), and neither are commas. doorplate looks
  the city up in its US place data, keyed by state and ZIP; libpostal reads the line with one model trained on addresses from
  everywhere. This is a difference in design on this input, not a ranking of the parsers.
- **libpostal's own tests.** libpostal returns exactly the expected components for 51 of its 53 cases; the Senzing model is not
  the one the tests were written for. With 53 cases the interval for doorplate is 75 to 94%. Of doorplate's seven misses, three
  are outside its scope (an organisation or venue name before the house number, and a search phrase), three are shapes worth a
  look in the rule loop (a floor written as an ordinal after the street, a county between the city and the state, and `Apt No. 4`),
  and one has a line break inside a one-line string.
- **Senzing's test set.** It is the nearest thing to held-out data, but nearly all of it is OpenStreetMap address tags written out as
  one line: clean, uniform input, close to what libpostal was trained on. libpostal leads doorplate there by one point, with intervals
  that overlap at the edges. Senzing's own US failure rate (4.58% in v1.2.0) uses a definition of failure that is not stated.
- **Cost.** On one thread doorplate (`parse_tokens`) takes about a fifth of libpostal's time, and on four threads or processes it is
  about 6.5 times as fast (0.6.1; the speed figures are from one run). libpostal's README claims 10 to 30 thousand
  addresses per second per thread; this is inside that range. The Senzing model is about 3 GB per process and loads in 4 to 6 s; the
  default model (1.8 GB of data) was not measured. libpostal runs in its own processes, because a `parse_address` call holds the
  Python GIL, and each process loads its own copy of the model: four workers took about 11,760 MB together against 253 MB for doorplate's
  `parse_many` on all threads of one process.

## What a fair comparison needs

- The same inputs and the same scoring rule for both, with the intervals the [benchmark suite](benchmark-suite.md) prints. Use
  `natural` and the outside sets, not `hard`.
- Say what each was trained near. libpostal was trained on OpenStreetMap and OpenAddresses, and the National Address Database
  that the suite draws on overlaps OpenAddresses. doorplate's rules were written while reading some of the sets (the geocode
  benchmark's `test` split, see [`benchmarks.md`](benchmarks.md)), so a score on those is optimistic.
- Cost beside accuracy: install effort, model size, load time, memory and addresses per second, with the load time apart from the
  per-address speed. Defaults only: no retraining of either side.

The plan for a full comparison, with a hand-labeled golden set, is in issue [#616](https://github.com/jeremeybingham/doorplate/issues/616).

## Sources

The libpostal [README](https://github.com/openvenues/libpostal), the [`pypostal` README](https://github.com/openvenues/pypostal)
and Senzing's [`libpostal-data`](https://github.com/Senzing/libpostal-data), all read on 2026-11-07. Status of the comparison:
issue [#215](https://github.com/jeremeybingham/doorplate/issues/215).
