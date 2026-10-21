#!/usr/bin/env python3
"""Compare two runs of tools/harness/run.py: how the class counts changed.

    python tools/harness/compare.py BEFORE AFTER [--top 15] [--partial]

BEFORE and AFTER are run ids (under local-data/netsyms-runs/) or paths. Reads the
aggregates only (see SCHEMA.md), offline, with DuckDB, and prints a Markdown report
(totals, warning codes, states) that it also writes into AFTER's directory as
`compare-<before>-vs-<after>.md`. Counts only, so the report may be quoted under
docs/data-policy.md. Use it after a rule change: rerun the harness, then compare with the
previous run on the same rows.

It refuses runs without a DONE marker unless `--partial`, and warns when the runs used
different input rows, commits' schema versions, or chunk settings (the numbers are then not
like for like). This library formats and parses; it does not validate that an address exists
or can receive mail.
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = ROOT / "local-data" / "netsyms-runs"
FIELDS = ["rows", "with_warnings", "no_result", "flagged", "m_number", "m_state", "m_zip5",
          "m_zip4", "m_city", "m_unit", "m_street", "last_line_rows", "last_line_crossed", "m_boundary"]


def open_run(arg, partial):
    run = Path(arg)
    if not run.is_dir():
        run = DEFAULT_ROOT / arg
    if not (run / "manifest.json").exists():
        sys.exit(f"{run} is not a run directory")
    if not (run / "DONE").exists() and not partial:
        sys.exit(f"{run} has no DONE marker (incomplete); pass --partial to compare anyway")
    return run, json.loads((run / "manifest.json").read_text())


def pct(v, n):
    return f"{100 * v / n:.2f}%" if n else "-"


def delta(a, b):
    d = b - a
    return f"{d:+,}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--partial", action="store_true")
    args = ap.parse_args(argv)
    ra, ma = open_run(args.before, args.partial)
    rb, mb = open_run(args.after, args.partial)
    notes = []
    if ma.get("schema_version") != mb.get("schema_version"):
        notes.append(f"schema versions differ ({ma.get('schema_version')} vs {mb.get('schema_version')}):"
                     " columns whose rule changed (see SCHEMA.md) are not comparable")
    ia, ib = ma["input"], mb["input"]
    if ia.get("kind", "netsyms-sqlite") != ib.get("kind", "netsyms-sqlite"):
        notes.append("the runs read different kinds of input (SQLite and records): they are like for like"
                     " only when the row totals are equal")
    elif (ia["size"], ia["rowid_min"], ia["rowid_max"], ia["country"]) != \
            (ib["size"], ib["rowid_min"], ib["rowid_max"], ib["country"]):
        notes.append("the runs read different input (size, row range or country)")
    if ma["options"]["chunk_rowids"] != mb["options"]["chunk_rowids"]:
        notes.append("chunk sizes differ (the totals are still comparable)")
    con = duckdb.connect()
    for name, run in (("a", ra), ("b", rb)):
        for t in ("agg_state_source", "agg_warnings"):
            con.execute(f"create view {name}_{t} as select * from read_parquet('{run / t}/*.parquet')")
    cols = [{r[0] for r in con.sql(f"describe {n}_agg_state_source").fetchall()} for n in "ab"]
    fields = [f for f in FIELDS if f in cols[0] or f in cols[1]]

    def totals(name, have):
        return con.sql("select " + ", ".join(f"coalesce(sum({f}),0)" if f in have else "0" for f in fields)
                       + f" from {name}_agg_state_source").fetchall()[0]

    ta, tb = totals("a", cols[0]), totals("b", cols[1])
    out = [f"# Compare {ma['run_id']} -> {mb['run_id']}", "",
           f"- before: commit `{ma['git_commit'][:10]}`, doorplate {ma['doorplate_version']}, data `{ma['data_tables_sha256'][:10]}`",
           f"- after:  commit `{mb['git_commit'][:10]}`, doorplate {mb['doorplate_version']}, data `{mb['data_tables_sha256'][:10]}`"]
    out += [f"- **Note:** {n}" for n in notes]
    out += ["", "## Totals", "", "| | before | after | change | after, share of rows |", "|---|---|---|---|---|"]
    for f, a, b in zip(fields, ta, tb):
        out.append(f"| {f.replace('m_', 'mismatch ') if f.startswith('m_') else f} | {a:,} | {b:,} | {delta(a, b)} | "
                   f"{pct(b, tb[0]) if f != 'rows' else ''} |")
    rows = con.sql("""select code, coalesce(a.n,0) a, coalesce(b.n,0) b from
        (select code, sum(n) n from a_agg_warnings group by 1) a
        full outer join (select code, sum(n) n from b_agg_warnings group by 1) b using (code)
        order by abs(coalesce(b.n,0) - coalesce(a.n,0)) desc, 3 desc""").fetchall()
    out += ["", "## Warning codes (largest changes first)", "", "| code | before | after | change |", "|---|---|---|---|"]
    out += [f"| {c} | {a:,} | {b:,} | {delta(a, b)} |" for c, a, b in rows[:max(args.top, 1)]]
    rows = con.sql("""select state, coalesce(a.f,0) a, coalesce(b.f,0) b from
        (select state, sum(flagged) f from a_agg_state_source group by 1) a
        full outer join (select state, sum(flagged) f from b_agg_state_source group by 1) b using (state)
        order by abs(coalesce(b.f,0) - coalesce(a.f,0)) desc limit ?""", params=[args.top]).fetchall()
    out += ["", "## States by change in flagged rows", "", "| state | before | after | change |", "|---|---|---|---|"]
    out += [f"| {s} | {a:,} | {b:,} | {delta(a, b)} |" for s, a, b in rows]
    text = "\n".join(out) + "\n"
    (rb / f"compare-{ma['run_id']}-vs-{mb['run_id']}.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
