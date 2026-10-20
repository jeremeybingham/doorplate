# Ingest: one record format for every address source

Step 1 of issue #93. Every source we test the parser on comes down to the same few
fields: line 1, line 2, city, state, ZIP, sometimes a combined city/state/ZIP line, and
sometimes labeled parts. `ingest.py` turns a source into those fields, the **record
format**, so the harness and the scorers (steps 2 to 4) need no code per source. Read
`docs/data-policy.md` first: records built from private data stay in `local-data/`.

```sh
python tools/ingest/ingest.py tools/ingest/specs/nad.toml                # the plan
python tools/ingest/ingest.py tools/ingest/specs/nad.toml --confirm      # write the records
python tools/ingest/ingest.py SPEC --limit 1000 --output local-data/tmp/x.parquet --confirm
pytest tools/ingest                                                      # tests (invented rows)
```

It needs Python 3.11 or later (`tomllib`), DuckDB and PyArrow. Without `--confirm` it
prints the plan (inputs and their sizes, roles, output) and exits.

## The record format (version 1)

One Parquet file per source, `records.parquet`, every column a string or null. Values
are trimmed at the ends (inner spacing is kept, since that is part of what we test), NUL bytes
(fixed-width padding) are dropped, and an empty value becomes null. A spec that joins fields
with `concat_ws` or filters on `IS NOT NULL` sees the raw values, so it should clean them itself
(`nullif(trim(replace(x, chr(0), '')), '')`); a pad of NULs once made 16.9 million empty mailing
addresses look present.

| Column | Meaning |
|---|---|
| `source` | The spec's `source` (set by the script) |
| `record_id` | The source's own id, so a record can be joined back to its row. **Required** |
| `role` | Which address of the row this is (`residential`, `mailing`, `physical`, ...). Set by the script from the spec |
| `line1` | The street line as the source has it, or as composed from its fields. **Required** (may be null in a row) |
| `pair_id` | An id shared with another source or role that holds the same address in another form (step 3 scores one against the other) |
| `provider` | A group within the source worth breaking results down by (the original provider in an aggregate, a license type) |
| `line2` | Second line: unit, building, care-of |
| `city`, `state`, `zip` | The last line in separate fields; `zip` may carry `-plus4` |
| `last_line` | City, state and ZIP in one field, for sources that store them that way. `tools/harness/run.py` joins it to the street lines and parses the whole string, and counts parses whose city, state or ZIP use words from outside `last_line` (#93, option A) |
| `label_number_prefix`, `label_number`, `label_number_suffix` | The house number and its prefix and suffix (a half, a letter) as the source labels them |
| `label_predir`, `label_pretype`, `label_name`, `label_type`, `label_postdir`, `label_postmod` | The street parts as labeled: predirectional, pre-type (`US HIGHWAY`), name, type (suffix), postdirectional, post-modifier (`EXT`) |
| `label_unit_type`, `label_unit`, `label_building` | Unit designator and number, building |

A source's labels are its providers' choices, not ground truth: a disagreement is a
question, not a bug count. Beside the records, `records.json` holds the counts (rows, the
share of each column present per role, repeated `(role, record_id)` pairs), the spec's
hash, a fingerprint of each input (size, time, hash of the first and last MiB) and the
commit.

## Specs

A spec is a TOML file: the source name, the output, the inputs, and one SQL query per
role. The queries select the source's columns under the record column names; the script
adds `source` and `role`, fills the columns a role does not map with nulls, and rejects
any other column name. Paths are relative to the repository root.

```toml
source = "example"
output = "local-data/example/records.parquet"

[inputs.s]                         # a view named `s` for the role queries
files = ["local-data/example/data.csv"]          # fingerprinted in records.json
sql = "SELECT * FROM read_csv('local-data/example/data.csv', all_varchar = true)"

[[roles]]
role = "site"
sql = """
SELECT id AS record_id, concat_ws(' ', number, street) AS line1, unit AS line2,
       city, state, zip
FROM s
"""
```

An input can instead be a SQLite table: `sqlite = "path"` and `query = "SELECT ..."`
(copied to a temporary Parquet file first, since DuckDB's SQLite extension is not
available offline).

Specs here (`specs/`) cover the sources the documentation already names: `nad.toml` (the
same inputs as `tools/harness/nad_score.py`) and `netsyms.toml` (the same as
`tools/harness/run.py`). **A spec for any other private source lives with its data in
`local-data/<source>/`**, not in the repository, together with its `NOTICE.md` and
`INVENTORY.md` (`local-data/README.md`).

## Privacy

Only counts are printed and stored. An error from the SQL itself (a misspelled column) is
shown; any other error is reported by its type only, because DuckDB's messages quote the
source rows they failed on, and those can hold names (`docs/data-policy.md`). When writing
a spec, look at column names and counts (`DESCRIBE`, `count(*)`), never at rows.

## What is in `local-data/`

`python tools/ingest/inventory.py` reads the `records.json` beside every records file and the
manifest and `DONE` of every harness run, and writes `local-data/INVENTORY.md` (private, counts
only): the record files with their rows by role, the runs with their flagged shares, and the
rows examined (the latest complete run per input file; `--exclude TEXT` leaves out runs whose
input path contains TEXT, such as a sample inside a full database). `local-data/README.md` and each
folder's `NOTICE.md` and `INVENTORY.md` hold what each source is, where it came from and its terms.
