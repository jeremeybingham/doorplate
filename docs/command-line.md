# Command-line guide

The `doorplate` command parses addresses from a shell, a pipe or a CSV file, with no Python. It wraps the same parser as the
library. This page is the tour; every command, option and exit code is in the [command-line reference](cli.md).
It formats and parses; it does not validate that an address exists or can receive mail.

## Install

```sh
cargo install doorplate-cli        # installs the `doorplate` command
```

Rust 1.80 or later.

## Usage

```sh
doorplate parse "123 N Main St, Miami FL 33101" --pretty     # JSON: components, output, key, warnings, provenance
doorplate --version                                          # the library version, also in the JSON as provenance.library_version (and provenance.state_data_version)
doorplate parse "123 N. Main St #4, miami, fl 33101" --usps  # Pub 28 lines
doorplate parse-file in.csv --column address -o out.csv      # appends addr_* columns
doorplate parse --line1 "412 N HARBOR ST" --line2 "APT 3B" --city Tampa --state FL --zip 33602   # pre-split fields
doorplate parse "281 EVELYN DR DOTHAN" --default-state AL    # state hint
doorplate parse "123 N Main St, Miami FL 33101" --display    # mixed case; --long spells words out (not Pub 28)
doorplate parse "123 N Main St, Miami FL 33101" --tag        # usaddress-style joined labels
doorplate parse -  < addresses.txt                           # one address per line, JSON lines out
doorplate anonymize in.csv --column address -o shareable.csv   # same shape, other digits and names
doorplate parse "123 Oak Trayl, Miami FL 33101" --custom-layer DIR   # your own spellings and places 
doorplate layer check DIR                                    # load a custom layer: every problem, or what it holds
```

```sh
$ doorplate parse "123 N. Main St #4, miami, fl 33101" | jq -r .key
k4:S|123|N|MAIN|ST||FL|33101
```

`doorplate --help` lists every option.

## CSV files

`parse-file` reads a CSV file and writes it back with the parsed columns appended, so it works on the shape your
data already has:

```sh
# a column of whole addresses
doorplate parse-file addresses.csv --column address -o parsed.csv

# street line, unit line, city, state and ZIP in separate columns (any of them may be empty)
doorplate parse-file split.csv --column line1 --line2 line2 --city city --state state --zip zip -o parsed.csv

# a state hint for rows that name no state
doorplate parse-file addresses.csv --column address --default-state FL -o parsed.csv
```

The [demo page](https://jeremeybingham.github.io/doorplate/demo/#csv) does the same in the browser, with no install: pick the file, choose the
address column (or the line 1, line 2, city, state and ZIP columns), tick the columns to add, and download the result. The file is read and parsed
in the tab (WebAssembly in a worker), nothing is uploaded, and the columns and their `addr_` prefix are `parse-file`'s. It holds the whole result
in memory, so for files of several hundred megabytes use `parse-file`.

Every input column is kept, and the new `addr_` columns are the components (`street_number`, `street_name`,
`unit_number`, `city`, `state`, `zip5`, ...), the shapes (`po_box`, `rural_route`, `military`, `general_delivery`),
`place`, the USPS lines, `key`, `key_unit`, `slug`, `warnings` (stable codes joined by commas; [what each tells you](warnings.md)) and `unparsed`. PO
boxes, routes, military addresses and street addresses can share one file. A blank row, or a row with no address
text, is written with empty new columns and counted on standard error instead of stopping the run. Without `-o`
the CSV goes to standard output, so it composes with other tools. On a Florida file with five address columns it
ran at about 30,000 rows per second on one thread, including reading and writing about 30 columns
([benchmarks](benchmarks.md)).

## Next

- Your own spellings and places: `doorplate layer check` and `--custom-layer`, in [Custom layers](custom-layers.md).
- Sharing messy rows: `doorplate anonymize`, in [Anonymizing data](anonymizing.md).
- From a data frame, SQL or a notebook: [pandas, Polars and DuckDB](dataframes.md).
