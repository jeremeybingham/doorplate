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
- Neither page says which model version `MODEL=senzing` downloads. A build on 2026-11-07 at libpostal commit `25099c5`
  (2025-12-06) fetched the Senzing **1.2.0 parser**, with the base data and the language classifier at 1.1.0. How to choose a
  model once libpostal is built is still not stated. Every libpostal figure therefore carries the libpostal commit, the model
  version and a checksum of the data directory, which the comparison tools print.

A secondary check already exists: Senzing publishes the test set it scores its models on, and `doorplate` was scored on its US
rows without running libpostal ([`benchmarks.md`](benchmarks.md), "Senzing's libpostal test set"). That score is not a
comparison with libpostal.

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

Both add a third column to a table of **common labels**, beside the unchanged two-way tables. The common set folds usaddress's labels
because libpostal gives `unit` and `po_box` as one piece: street parts are `StreetName` (as in the coarse score), occupancy type
and identifier are `Occupancy`, box type and identifier are `USPSBox`. libpostal's labels map as the table above shows, with
`suburb`, `city_district`, `island` and `state_district` all read as `PlaceName` (usaddress has one place label) and `level`,
`staircase` and `entrance` as `Occupancy`; a label with no match (`category`, `near`, `country_region`, `world_region`) never
agrees with a gold label. libpostal returns lowercase pieces, so they are found in the input ignoring case, in order, and cut at
spaces to tokens. *Shared labels* leaves out the records with a gold label libpostal cannot produce (a rural-route box group, a
recipient); *all records* leaves nothing out. The report prints the libpostal commit, the model version, the data checksum, the
model load time and the one-thread parse time (the last two are a check of the run, not the speed benchmark).
`tools/compare/test_libpostal_provider.py` tests the mapping on invented addresses.

## First measurement (2026-11-07; one run, to be repeated)

Measured once on the benchmark suite's comparison track (19,586 records), usaddress's own test files and the geocode benchmark's `dev`
split, with libpostal commit `25099c5` and the Senzing 1.2.0 parser (data checksum `7afb91d6ef19`), on the parser of doorplate
`main` at that date. Common labels, whole record or address right; the suite's intervals are 95% Wilson. These are notes from the first run,
not the published figures: they will be measured again in the away run and moved to [`benchmarks.md`](benchmarks.md) with the other
tables.

| Set | doorplate | usaddress | libpostal |
|---|---|---|---|
| Suite, `natural`, shared labels (15,275) | 98.8% | 97.2% | 96.4% |
| Suite, `natural`, all records (16,001) | 98.3% | 96.3% | 93.8% |
| Suite, whole suite, shared labels (18,120) | 95.1% | 89.0% | 94.5% |
| Suite, whole suite, all records (19,586) | 92.4% | 86.0% | 89.5% |
| Suite, `hard` stratum (2,585) | 55.1% | 20.2% | 65.8% |
| Suite, `hand` stratum (1,000) | 94.3% | 90.3% | 80.3% |
| usaddress's test files, not in its training files, all (2,248) | 99.1% | 100.0% | 98.1% |
| Geocode benchmark `dev` (60,522) | 94.3% | 88.1% | 80.0% |

How to read it:

- On the suite's `natural` records (the estimate for ordinary input) doorplate leads libpostal by 2.4 to 4.5 points. libpostal leads on
  `hard`, the stratum drawn from doorplate's and usaddress's blind spots, so that row is not a fair test of libpostal. usaddress's own
  files are its regression tests, so its near 100% says nothing.
- The geocode `dev` gap is the largest, and its cause is specific. The inputs are one line with no commas, and when the city is rare,
  misspelled or several words, libpostal's `road` runs on into it: of the wrong `dev` tokens, the biggest class by far is a city word
  read as part of the road. Case is not the cause (uppercase and title-case inputs gave identical parses on a 3,000-address sample), and
  commas alone are not (the suite's comma-less styles score 90 to 92% for libpostal, as well as its comma styles do). doorplate looks the
  city up in its US place data, keyed by the state and ZIP, where libpostal reads the line with one model trained on addresses from
  everywhere. This is a difference in design on this input, not a ranking of the parsers.
- Token-level and whole-record figures, the per-stratum and per-style tables and libpostal's most common token errors are in the
  suite report that `--with-libpostal` prints. The mapping decisions above (a label with no match counts as wrong; `suburb` and its
  kin read as a place) affect these figures a little and were chosen before the run.
- Speed is not measured here (step 5): libpostal parsed the 19,586 suite strings in 1.3 s on one thread after a model load of about
  4 s, which is a check of the run only.

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
