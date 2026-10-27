# Command-line reference

The `doorplate` command (`cargo install doorplate-cli`, Rust 1.80 or later). It formats and parses; it does not
validate that an address exists or can receive mail. `doorplate --help` prints the same list of options as the
"Usage text" section below, and `doorplate --version` prints the library version (also in each JSON record as
`provenance.library_version`). The tour with examples is in the [command-line README](../crates/doorplate-cli/README.md);
the library is in the [Python reference](python-api.md) and on [docs.rs](https://docs.rs/doorplate).

## Commands

| Command | What it does |
|---|---|
| `doorplate parse` | Parse one address given as an argument or as fields, or one address per line from standard input |
| `doorplate parse-file` | Parse the address columns of a CSV file and write the file back with `addr_` columns appended |
| `doorplate layer check DIR` | Load a custom layer: list every problem, or what it holds |
| `doorplate anonymize` | Rewrite address-like text so it can be shared: same shape, other digits and words |
| `doorplate corpus test` | Run a golden corpus of expected parses |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | A usage error: an unknown command or option, or a missing argument. The message and the usage text go to standard error |
| 2 | The run failed: a custom layer that cannot be loaded, a file that cannot be read, or, from `parse -`, a line with no address text (every other line is still written) |
| 3 | `corpus test` found a regression, or a baseline that is stale |

## `doorplate parse`

```sh
doorplate parse "123 N Main St Apt 4, Miami FL 33101" --pretty
doorplate parse --line1 "412 N HARBOR ST" --line2 "APT 3B" --city Tampa --state FL --zip 33602
doorplate parse - < addresses.txt
```

One JSON object per address, on one line (`--pretty` indents it). With no `-`, a quoted address; with `-` or no
argument, one address per line from standard input, and a blank line is reported on standard error and skipped.

| Option | Meaning |
|---|---|
| `--line1 X`, `--line2 X`, `--city X`, `--state X`, `--zip X` | Parse pre-split fields instead of a one-line address. Any may be omitted |
| `--default-state ST` | A lookup hint for input with no state (a USPS code or a state name). It never fills `state` |
| `--custom-layer DIR` | Use a [custom layer](custom-layers.md) on top of the shipped tables. Every record reports it in `provenance.custom_layer`; a layer can change a key |
| `--pretty` | Indent the JSON |
| `--usps` | Print only the Publication 28 lines, as text |
| `--display` | Print mixed case with Pub 28 abbreviations (`123 N Main St Apt 4`), for people. Not a Pub 28 form |
| `--long` | Print directionals, suffixes and units spelled out (`123 North Main Street Apartment 4`). Not a Pub 28 form |
| `--usaddress` | Print the input's tokens with [usaddress](usaddress-compat.md)'s labels: `{"input", "tags": [[token, label, start, end], ...]}` |
| `--tag` | Print the joined labels, like `usaddress.tag()`, with the address type and the repeated labels |

`--usps`, `--display`, `--long`, `--usaddress` and `--tag` choose one output form and replace the JSON record. The
default record has `input`, `components`, `warnings`, `unparsed`, `key`, `key_unit`, `slug`, `usps`, `reso`, the
shape fields that apply (`po_box`, `rural_route`, `military`, ...), `place` and `provenance`. The warning codes are on
the [Warnings](warnings.md) page and the key is in [The match key](key-format.md).

## `doorplate parse-file`

```sh
doorplate parse-file addresses.csv --column address -o parsed.csv
doorplate parse-file split.csv --column line1 --line2 line2 --city city --state state --zip zip -o parsed.csv
```

Reads a CSV file and writes it back with every input column kept and the `addr_` columns appended: the components,
the shapes, `place`, the USPS lines, `key`, `key_unit`, `slug`, `warnings` (codes joined by commas) and `unparsed`.
A blank row, or a row with no address text, gets empty new columns and is counted on standard error. Without `-o`
the CSV goes to standard output.

| Option | Meaning |
|---|---|
| `--column NAME` | Required. The column holding the whole address, or line 1 when other columns are given |
| `--line2 NAME`, `--city NAME`, `--state NAME`, `--zip NAME` | Columns holding the other fields. Any may be omitted |
| `-o OUT.csv` | Where to write the CSV (default: standard output) |
| `--default-state ST` | A state hint, as for `parse` |
| `--custom-layer DIR` | A custom layer, as for `parse` |

## `doorplate layer check`

```sh
doorplate layer check county-extras
```

Loads the layer folder the way `--custom-layer` does. On success it prints the layer's name, version and content
fingerprint and what it holds, and exits 0. Otherwise it prints every problem, each naming its file and entry, and
exits 2. See [Custom layers](custom-layers.md).

## `doorplate anonymize`

```sh
doorplate anonymize in.csv --column address --column line2 -o shareable.csv
doorplate anonymize - < lines.txt
```

| Option | Meaning |
|---|---|
| `--column NAME` | The CSV column to rewrite; repeat for several. Other columns are copied. Without a CSV file (`-`), each line of standard input is one value |
| `-o OUT.csv` | Where to write the CSV (default: standard output) |
| `--seed N` | Repeat a run. A seed you publish lets anyone check a guess; leave it out for a random one |

This is obfuscation that keeps the shape, not anonymity: read the output before you share it. See
[Anonymizing data](anonymizing.md).

## `doorplate corpus test`

```sh
doorplate corpus test --dir my-corpus --custom-layer my-layer
```

Runs a golden corpus (the record format is in the [corpus page](tests/corpus.md)) and compares it
with the baseline, `passing.txt`. Exit 3 on a regression.

| Option | Meaning |
|---|---|
| `--dir DIR` | The corpus folder (default: `tests/corpus`) |
| `--verbose` | List every case |
| `--update-baseline` | Rewrite `passing.txt` from this run |
| `--custom-layer DIR` | Run the corpus against a custom layer |

## Usage text

```text
usage:
  doorplate parse "<address>" [--pretty] [--usps | --display | --long | --usaddress | --tag]
                  [--default-state ST] [--custom-layer DIR]
  doorplate parse --line1 X [--line2 X] [--city X] [--state X] [--zip X] [--pretty]
                  [--usps | --display | --long] [--default-state ST] [--custom-layer DIR]
  doorplate parse [-]                 read one address per line from stdin
                                 (--display: mixed case, `123 N Main St`; --long: spelled out,
                                 `123 North Main Street`; neither is a Pub 28 form.
                                 --usaddress: tokens with usaddress labels;
                                 --tag: joined by label, like usaddress.tag())
  doorplate parse-file IN.csv --column NAME [--line2 NAME] [--city NAME] [--state NAME]
                  [--zip NAME] [-o OUT.csv] [--default-state ST] [--custom-layer DIR]
                                 --default-state: look cities up in ST when the
                                 input names no state (a hint, never a fill)
                                 --custom-layer DIR: your own spellings, words, places and ZIPs
                                 on top of the shipped tables (docs/custom-layers.md); every
                                 JSON record reports it in provenance.custom_layer. A layer can
                                 change a key: keep its fingerprint with stored keys
  doorplate layer check DIR      load a custom layer: list every problem, or what it holds
  doorplate anonymize [-] [--seed N]
                                 read one line per stdin line and write it back with the
                                 digits and unknown words replaced (same shape; obfuscation,
                                 not proof of anonymity: read the output before you share it)
  doorplate anonymize IN.csv --column NAME [--column NAME ...] [-o OUT.csv] [--seed N]
                                 the same for the named CSV columns; other columns are copied.
                                 --seed N repeats the output (a published seed lets anyone check
                                 a guess; leave it out for a random one)
  doorplate corpus test [--dir DIR] [--verbose] [--update-baseline] [--custom-layer DIR]
                                 run the golden corpus (default dir: tests/corpus)
  doorplate --version | -V       print the version (the library's, as recorded in the JSON)
  doorplate --help | -h          print this text
```
