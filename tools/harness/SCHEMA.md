# Run artifacts (schema version 5)

Written by `tools/harness/run.py`, read by `tools/harness/analyze.py` and `compare.py`. The
folder is private (docs/data-policy.md): aggregate numbers may leave it, nothing else.

## How rows are parsed

Rows come from `--input` (the record format of `tools/ingest/`, see its README) or, for the
original Netsyms path, from `--db` (the same rows `tools/ingest/specs/netsyms.toml` builds). A
row has `source`, `role`, `provider`, `line1`, `line2`, `city`, `state`, `zip`, `last_line` and
`label_number`.

| Row | Parsed with |
|---|---|
| no `last_line` | `doorplate.parse_fields_many(line1, line2, city, state, zip)` |
| `last_line` set | `doorplate.parse_many` on `line1, line2, last_line` joined with `, ` (#93, option A: the API has no last-line argument) |

A row whose parse returns no result (no address text) is counted as `no_result`. The
`last_line` rows are counted separately (`last_line_rows`, `last_line_crossed`).

## Comparison rules (the `mismatches` codes)

Schema version 5 runs the `unit` check only for roles that have `label_unit` (a source that says its line 2 is a unit): in sources whose line 2 holds attention lines and building names, `m_unit` of version 4 and earlier counted every line 2 as a missing unit. Schema version 4 changed the `street` rule for PO boxes, rural routes, general delivery and military boxes (below); on those rows `m_street` of version 3 flagged nearly every one. Schema version 3 added `role`, `provider` and the last-line counts, and runs the checks per field:
a check runs for a role only when some row of that role has the field (the manifest's
`input.fields_present`). Schema version 2 changed the `street` rule; runs of version 1 are not
comparable on `m_street`. The counts of version 2 and 3 are the same for the same Netsyms rows.

Normalization `norm`: upper case, periods dropped, whitespace collapsed. `compact`: `norm`
with everything but letters and digits removed.

| Code | Raised when | Runs when the role has |
|---|---|---|
| `no_result` | the parse gave no result for the row | always |
| `number` | `compact(label_number)` differs from `compact(street_number)`; a `line2` that is only a fraction (`1/2`) counts as part of the source number | `label_number` |
| `state` | `norm(state)` differs from the parsed `state` | `state` |
| `zip5` | the first five characters of `zip` differ from the parsed `zip5` | `zip` |
| `zip4` | `zip` carries a plus-4 (`12345-6789`) and it differs from the parsed `zip4` | `zip` |
| `city` | `compact(city)` differs from `compact(parsed city)` (the parser keeps the city as written, upper-cased) | `city` |
| `unit` | the source has a `line2` but the parse has no unit, or the reverse | `label_unit` |
| `street` | a word of `line1` (less the house number) is not accounted for in the parse (a street part, unit, building, attention or unparsed text), or a parsed street word came from none of `line1`, `line2` and the house number. Suffix and directional spellings are compared by their standard abbreviation (`ST` equals `STREET`), and a standardized highway name (`US HWY 377`, `US HIGHWAY 377`) is equal to itself. The house number is `label_number`, or the parsed `street_number` when the role has no label. When the parse found a PO box, rural route, general delivery or military box, the words that name the form (`PO`, `BOX`, `RR`, `HC`, `ROUTE`, ...) and its numbers count as accounted for | always |
| `boundary` | a `last_line` row whose parsed city, state or ZIP use words that are not in `last_line` (the state by any of its spellings): the parse took them from the street lines, so joining lost the line boundary | `last_line` rows |

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

### `agg_state_source/` (counts per state, source, role and provider)

`state`, `source` (the dataset, such as `nc-voter`), `role`, `provider` (the group within it;
for Netsyms, its `source` column), `rows`, `with_warnings`, `no_result`, `flagged`, `m_number`,
`m_state`, `m_zip5`, `m_zip4`, `m_city`, `m_unit`, `m_street`, `last_line_rows`,
`last_line_crossed`, `m_boundary`. All counts are `int64`. `flagged` is the number of rows with
a warning or a mismatch. `state` is the source state, or for a `last_line` row the parsed one.

### `agg_warnings/`

`state`, `source`, `role`, `provider`, `code` (a doorplate warning code), `n`.

### `agg_triples/`

`state`, `zip5`, `city` (`norm` of the source city; the parsed one for a `last_line` row), `source`, `role`, `provider`, `place` (the name of the place
the parse found for the city, empty when it found none), `n`. Sum `n` across chunks. Rows with
`place` empty are the place-list gaps for the analysis.

### `flagged/` (rows with a warning or a mismatch)

`record_id` (string: the source's own id, or the rowid for `--db`), `state`, `source`, `role`, `provider`, `warnings` (comma-joined codes),
`mismatches` (comma-joined codes above), `address_type`, `key`, `street_number`,
`street_dir_prefix`, `street_name`, `street_suffix`, `street_dir_suffix`, `unit_type`,
`unit_number`, `city`, `zip5`, `zip4`, `unparsed`, `place`. The source text is not copied:
join on `record_id` (with `source` and `role`) to the records file or SQLite table named in the manifest (and check the manifest's
fingerprint) to see it.
