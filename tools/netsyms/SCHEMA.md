# Netsyms run artifacts (schema version 2)

Written by `tools/netsyms/run.py`, read by `tools/netsyms/analyze.py`. The folder is
private (docs/data-policy.md): aggregate numbers may leave it, nothing else.

## How rows are parsed

The source stores each address split into columns. Each US row is parsed with
`doorplate.parse_fields_many`:

| Field | Built from |
|---|---|
| `line1` | `number` + space + `street` |
| `line2` | `street2` (the unit), or none |
| `city`, `state` | `city`, `state` |
| `zip` | `zipcode`, plus `-` and `plus4` when there is a `plus4` |

A row whose parse returns no result (no address text) is counted as `no_result`.

## Comparison rules (the `mismatches` codes)

Schema version 2 changes the `street` rule (below); runs of version 1 are not comparable on `m_street`.

Normalization `norm`: upper case, periods dropped, whitespace collapsed. `compact`: `norm`
with everything but letters and digits removed.

| Code | Raised when |
|---|---|
| `no_result` | `parse_fields_many` gave no result for the row |
| `number` | `compact(number)` differs from `compact(street_number)`; a `street2` that is only a fraction (`1/2`) counts as part of the source number |
| `state` | `norm(state)` differs from the parsed `state` |
| `zip5` | the first five characters of `zipcode` differ from the parsed `zip5` |
| `zip4` | the source has a `plus4` and it differs from the parsed `zip4` |
| `city` | `compact(city)` differs from `compact(parsed city)` (the parser keeps the city as written, upper-cased) |
| `unit` | the source has a `street2` but the parse has no unit, or the reverse |
| `street` | a word of the source `street` is not accounted for in the parse (a street part, unit, building, attention or unparsed text), or a parsed street word came from none of the source `street`, `street2` and `number` (junk in `number`, such as `NULL`, is flagged by `number`, not here). Suffix and directional spellings are compared by their standard abbreviation (`ST` equals `STREET`), and a standardized highway name (`US HWY 377`, `US HIGHWAY 377`) is equal to itself. In schema version 1 this was a plain comparison with the abbreviated street and flagged about 96% benign differences. |

A mismatch can be a parser bug or a source error; it is not a verdict on either.
This library formats and parses; it does not validate that an address exists or can
receive mail.

## Files

Every table is Parquet (zstd), one file per chunk, `NNNNNN.parquet`, where `NNNNNN` is the
chunk number (`rowid` range `[min + N*chunk_rowids, min + (N+1)*chunk_rowids)`).

`chunk_status/NNNNNN.json` is written last, after the chunk's Parquet files: `chunk`, `rowid_lo`,
`rowid_hi`, `rows`, `flagged`, `seconds`. `DONE` exists only when every chunk finished and
holds the totals. `manifest.json` holds the run identity (see its keys; `input.sha256` is of
the first and last MiB unless `scope` says `whole file`).

### `agg_state_source/` (counts per state and source)

`state`, `source`, `rows`, `with_warnings`, `no_result`, `flagged`, `m_number`, `m_state`,
`m_zip5`, `m_zip4`, `m_city`, `m_unit`, `m_street`. All counts are `int64`. `flagged` is the
number of rows with a warning or a mismatch.

### `agg_warnings/`

`state`, `source`, `code` (a doorplate warning code), `n`.

### `agg_triples/`

`state`, `zip5`, `city` (`norm` of the source city), `source`, `place` (the name of the place
the parse found for the city, empty when it found none), `n`. Sum `n` across chunks. Rows with
`place` empty are the place-list gaps for the analysis.

### `flagged/` (rows with a warning or a mismatch)

`rowid` (into the source table), `state`, `source`, `warnings` (comma-joined codes),
`mismatches` (comma-joined codes above), `address_type`, `key`, `street_number`,
`street_dir_prefix`, `street_name`, `street_suffix`, `street_dir_suffix`, `unit_type`,
`unit_number`, `city`, `zip5`, `zip4`, `unparsed`, `place`. The source text is not copied:
join on `rowid` to the SQLite table named in the manifest (and check the manifest's
fingerprint) to see it.
