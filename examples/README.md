# Examples

Runnable examples of the Python package and the `doorplate` CLI. Every address in
`data/` is invented. This library formats and parses; it does not validate
that an address exists or can receive mail.

| File | Shows |
|---|---|
| [`quickstart.ipynb`](quickstart.ipynb) | A tour: `parse`, the USPS and RESO forms, the display and long forms (`to_display`, `to_long`; not Pub 28), keys and slugs, messy lines and warnings, `default_state`, `parse_fields`, `parse_many`, `parse_fields_many`, a pandas frame, the CLI on a file (`--usps`, `--display`, `--long`) |
| [`crates/doorplate/examples/quickstart.rs`](../crates/doorplate/examples/quickstart.rs) | The same in Rust: the output forms, `parse_fields_many` and `parse_many`. Run with `cargo run -p doorplate --example quickstart` |
| [`polars_pipeline.py`](polars_pipeline.py) | Polars: `parse_column` on a CSV, picking columns, finding rows with warnings, duplicates by key, pre-split columns with `parse_fields_many`, a display column |
| [`pandas_pipeline.py`](pandas_pipeline.py) | The same with pandas |
| [`duckdb_pipeline.py`](duckdb_pipeline.py) | DuckDB: `doorplate_parse` and `doorplate_parse_fields` in SQL, and `parse_column` on a relation (needs `pip install "doorplate[duckdb]"`) |
| [`data/addresses_oneline.csv`](data/addresses_oneline.csv) | One address per row in a single column (street, PO box, rural route, general delivery, a unit, a blank row) |
| [`data/addresses_split.csv`](data/addresses_split.csv) | Line 1, line 2, city, state and ZIP in separate columns, with gaps |
| [`data/addresses_messy.txt`](data/addresses_messy.txt) | One line per address as people type them: lowercase, `c/o`, a country, an intersection, no state |

## Run them

From the repository root, with the package built (`maturin develop` in
`crates/doorplate-py`) and the extras you need:

```sh
pip install pandas polars jupyter
python examples/polars_pipeline.py
python examples/pandas_pipeline.py --out /tmp/parsed.csv
python examples/duckdb_pipeline.py                       # needs duckdb and pyarrow
jupyter lab examples/quickstart.ipynb
```

The CLI on a file (build it with `cargo build --release -p doorplate-cli`):

```sh
target/release/doorplate parse-file examples/data/addresses_oneline.csv --column address -o /tmp/parsed.csv
target/release/doorplate parse-file examples/data/addresses_split.csv --column line1 --line2 line2 --city city --state state --zip zip
target/release/doorplate parse - < examples/data/addresses_messy.txt
target/release/doorplate parse "123 north main street apt 4, miami fl 33101" --display   # or --long, --usps
```

The tests in `crates/doorplate-py/tests/test_examples.py` run both scripts and the
notebook, so the examples stay current.
