#!/usr/bin/env python3
"""Summarize a Netsyms run directory.

    python tools/netsyms/analyze.py RUN_ID_OR_PATH [--top 20]

Reads `manifest.json`, the aggregates and the flagged rows (see SCHEMA.md) with
DuckDB, offline, and writes into the run directory:

- `summary.md`: aggregate counts only (safe to quote under docs/data-policy.md).
- `place_gaps.parquet`: (state, zip5, city) triples with rows and distinct sources where
  the parse found no place. Contains city names: private, stays in the run directory.

It refuses an incomplete run unless `--partial`. This library formats and parses; it does
not validate that an address exists or can receive mail.
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = ROOT / "local-data" / "netsyms-runs"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run", help="run id (under local-data/netsyms-runs/) or a path")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--partial", action="store_true", help="allow a run without a DONE marker")
    args = ap.parse_args(argv)
    run = Path(args.run)
    if not run.is_dir():
        run = DEFAULT_ROOT / args.run
    if not (run / "manifest.json").exists():
        sys.exit(f"{run} is not a run directory")
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        sys.exit(f"unsupported schema_version {manifest.get('schema_version')}")
    complete = (run / "DONE").exists()
    if not complete and not args.partial:
        sys.exit("the run has no DONE marker (incomplete); resume it, or pass --partial")
    nchunks = len(list((run / "chunk_status").glob("*.json")))
    con = duckdb.connect()
    for t in ("agg_state_source", "agg_warnings", "agg_triples", "flagged"):
        con.execute(f"create view {t} as select * from read_parquet('{run / t}/*.parquet')")

    tot = con.sql("""select sum(rows), sum(with_warnings), sum(no_result), sum(flagged),
        sum(m_number), sum(m_state), sum(m_zip5), sum(m_zip4), sum(m_city), sum(m_unit), sum(m_street)
        from agg_state_source""").fetchone()
    names = ["rows", "with warnings", "no result", "flagged", "number", "state", "zip5", "zip4",
             "city", "unit", "street"]
    out = [f"# Run {manifest['run_id']}: summary", "",
           f"- commit `{manifest['git_commit'][:10]}`{' (dirty tree)' if manifest['git_dirty'] else ''},"
           f" doorplate {manifest['doorplate_version']}, data tables `{manifest['data_tables_sha256'][:12]}`",
           f"- input `{Path(manifest['input']['path']).name}` table `{manifest['input']['table']}`,"
           f" country {manifest['input']['country']}, {nchunks} chunk(s),"
           f" {'complete' if complete else '**incomplete**'}", "",
           "Aggregate counts only. Mismatch codes are in SCHEMA.md; a mismatch can be a parser bug"
           " or a source error.", "", "## Totals", "", "| | rows | share of rows |", "|---|---|---|"]
    n = tot[0] or 1
    for name, v in zip(names, tot):
        out.append(f"| {name} | {v:,} | {100 * v / n:.2f}% |" if name != "rows" else f"| rows | {v:,} | |")

    def table(title, sql, header):
        rows = con.sql(sql).fetchall()
        out.extend(["", f"## {title}", "", "| " + " | ".join(header) + " |",
                    "|" + "---|" * len(header)])
        for r in rows:
            out.append("| " + " | ".join(f"{c:,}" if isinstance(c, int) else
                                          f"{c:.2f}%" if isinstance(c, float) else str(c) for c in r) + " |")

    table("Warning codes", f"select code, sum(n) n, 100.0*sum(n)/{n} pct from agg_warnings "
          f"group by 1 order by 2 desc limit {args.top}", ["code", "rows", "share of rows"])
    table("States by flagged share", f"select state, sum(rows) n_rows, 100.0*sum(flagged)/sum(rows) pct "
          f"from agg_state_source group by 1 having sum(rows) > 1000 order by 3 desc limit {args.top}",
          ["state", "rows", "flagged"])
    table("Sources by flagged share", f"select source, sum(rows) n_rows, 100.0*sum(flagged)/sum(rows) pct "
          f"from agg_state_source group by 1 having sum(rows) > 1000 order by 3 desc limit {args.top}",
          ["source", "rows", "flagged"])
    gaps = con.sql("""select state, zip5, city, sum(n) n_rows, count(distinct source) sources
        from agg_triples where place = '' and city <> '' group by 1,2,3""")
    gaps.write_parquet(str(run / "place_gaps.parquet"))
    g = con.sql("select count(*), coalesce(sum(n_rows),0) from (select sum(n) n_rows from agg_triples "
                "where place = '' and city <> '' group by state, zip5, city)").fetchone()
    out.extend(["", "## Place gaps", "",
                f"{g[0]:,} distinct (state, zip5, city) triples, {g[1]:,} rows, have no place found "
                "(`place_gaps.parquet` in the run directory, private)."])
    (run / "summary.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
