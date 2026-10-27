# pandas, Polars and DuckDB

How to parse a column, a CSV file or a table. Pick the call that matches how your addresses arrive; all of them give
the same components, keys and warnings. The functions are described in the [Python reference](python-api.md); runnable
versions with data of several shapes are in the [examples](https://github.com/jeremeybingham/doorplate/tree/main/examples).

## Your data, by shape

Pick the call that matches how your addresses arrive; all of them give the same components, keys and warnings.

| Your data | Use |
|---|---|
| A column of whole addresses, in pandas or Polars | `doorplate.pandas.parse_column` / `doorplate.polars.parse_column` |
| The same in DuckDB (a table, or a CSV or Parquet file it reads) | `doorplate_parse(address)` in SQL, or `doorplate.duckdb.parse_column` on a relation |
| Separate columns (street line, unit line, city, state, ZIP), complete or with gaps | `parse_fields_many(line1=[...], ...)`, or `doorplate_parse_fields(...)` in DuckDB |
| A mix of street addresses, PO boxes, rural routes, military, units in line 2, missing ZIPs | one call parses them all; `address_type`, `warnings` and `key` say which is which |
| Any list of strings | `parse_many` (all cores, GIL released) |
| Messy rows you want to share (same shape, other digits and names; obfuscation, not anonymity) | `doorplate.Anonymizer(seed=None).anonymize_many(lines)`, or `doorplate.anonymize(text)` ([how it works](anonymizing.md)) |
| A CSV file with no Python | the `doorplate` command: [the command line](command-line.md): `doorplate parse-file in.csv --column address -o out.csv` |

## Batches and DataFrames

`parse_many(texts)` takes a list or tuple of strings, releases the GIL, parses in
parallel with Rust threads, and returns the results in order. On 100,000 addresses
with 4 CPUs, the benchmark suite's profile (`crates/doorplate-py/benchmarks/bench_batch.py`, run under
`taskset -c 0-3` with `RAYON_NUM_THREADS=4`; more cores make the batch rows faster):

| | Time | Per second | Speed-up |
|---|---|---|---|
| a loop of `parse` | 1.79 s | 56,000 | 1x |
| `parse_many` | 0.62 s | 162,000 | 2.9x |
| `parse_many` and a pandas DataFrame of 7 columns | 0.77 s | 131,000 | 2.3x |
| `parse_many` and a Polars DataFrame of 7 columns | 0.69 s | 144,000 | 2.6x |
| DuckDB, `doorplate_parse(a)` with 7 columns | 0.64 s | 157,000 | 2.8x |
| `pandas.parse_column`, the 15 default columns | 0.83 s | 121,000 | 1.9x |
| `polars.parse_column`, the 15 default columns | 0.70 s | 143,000 | 2.3x |

**Helpers.** Install the extra and parse a column in one call:

```python
from doorplate.polars import parse_column   # or doorplate.pandas

out = df.hstack(parse_column(df["address"]))                    # Polars
out = df.join(parse_column(df["address"], default_state="FL"))  # pandas
```

`parse_column(series, *, columns=None, prefix="addr_", default_state=None)` returns a
DataFrame with one string column per name, in the same order (and, in pandas, the
same index) as the input. A null, blank or non-string row, or one with no address
text, is null in every column. The default columns are `street_number`,
`street_dir_prefix`, `street_name`, `street_suffix`, `street_dir_suffix`,
`unit_type`, `unit_number`, `city`, `state`, `zip5`, `zip4`, `address_type`, `key`,
`slug` and `warnings` (codes joined by commas). `AVAILABLE_COLUMNS` in either module
lists the rest (`key_unit`, `usps_line1`, `usps_line2`, `usps_last_line`, `po_box`,
`attention`, `building`, `unparsed`, ...). They are built over `parse_many`.

**DuckDB.** `pip install "doorplate[duckdb]"`, then register two functions on a connection and use them in SQL:

```python
import duckdb
from doorplate import duckdb as dd

con = duckdb.connect()
dd.register(con, columns=["street_name", "city", "state", "zip5", "key"])
con.sql("SELECT doorplate_parse(address).street_name, doorplate_parse(address).key FROM addresses")
con.sql("SELECT doorplate_parse_fields(line1, line2, city, state, zip).key FROM split")

rel = dd.parse_column(con.table("addresses"), "address", connection=con)   # input columns + addr_* columns, lazy
```

`doorplate_parse` returns a STRUCT of VARCHAR fields (`columns` defaults to the same list as the other helpers; `AVAILABLE_COLUMNS` has the rest) and NULL for a NULL, blank or no-address-text row. Each row is parsed once however many fields you read, in batches of 2,048 rows that Rust parses in parallel with the GIL released. Choose only the columns you need: building every column costs more (about 110,000 addresses/s with all 15 against 157,000 with 7, on 4 CPUs). `parse_column` stays lazy, so it works on tables larger than memory. Pass `connection=` unless the relation came from `duckdb.sql(...)`.

**Polars by hand** (when you want other fields):

```python
import polars as pl
import doorplate as dp

df = pl.read_csv("addresses.csv")
parsed = dp.parse_many(df["address"].fill_null("").to_list())  # None for a blank row

cols = ["street_number", "street_name", "street_suffix", "unit_number", "city", "state", "zip5"]
flat = pl.DataFrame(
    {f"addr_{c}": [getattr(a, c) if a else None for a in parsed] for c in cols}
    | {
        "addr_key": [a.key() if a else None for a in parsed],
        "addr_warnings": [",".join(a.warnings) if a else None for a in parsed],
    },
    schema={f"addr_{c}": pl.String for c in cols}
    | {"addr_key": pl.String, "addr_warnings": pl.String},
)
out = df.hstack(flat)
```

(Give the schema: a column that is `None` in every row would otherwise be typed
`Null`.) For every field, build structs from `to_dict()` and pick fields from them:

```python
full = pl.DataFrame([a.to_dict() if a else None for a in parsed], infer_schema_length=None)
full.select(
    "street_name",
    pl.col("place").struct.field("name").alias("place_name"),
    pl.col("usps").struct.field("line1").alias("usps_line1"),
)
```

**pandas by hand:**

```python
import pandas as pd
import doorplate as dp

df = pd.read_csv("addresses.csv")
parsed = dp.parse_many(df["address"].fillna("").tolist())  # None for a blank row

cols = ["street_number", "street_name", "street_suffix", "unit_number", "city", "state", "zip5"]
flat = pd.DataFrame([{c: getattr(a, c) for c in cols} if a else {} for a in parsed])
flat["key"] = [a.key() if a else None for a in parsed]
flat["warnings"] = [",".join(a.warnings) if a else None for a in parsed]
out = pd.concat([df, flat.add_prefix("addr_")], axis=1)
```

For every field with pandas, use `to_dict()` and
`pd.json_normalize([a.to_dict() if a else {} for a in parsed])`.

Calling `to_dict()` on every row costs about as much as parsing again (a loop with
`to_dict` ran at 26,000 per second), and reading attributes from 100,000 Python
objects was most of the time, so the `parse_column` helpers and `doorplate.duckdb` build their columns in Rust, with no Python
object per row (#24; before it, the 15-column rows above took 1.03 s for pandas and 0.86 s for Polars on 4 CPUs; on 14 CPUs the gain is about 1.4x). Pick columns when you can. Pre-split columns
(`line1`, `city`, ...): call `parse_fields_many(line1=df["line1"].tolist(), city=...)`.
