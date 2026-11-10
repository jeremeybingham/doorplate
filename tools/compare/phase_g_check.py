#!/usr/bin/env python3
"""Phase G of the away run (#567): two determinism checks on a seeded sample of the key-comparison sources.

    python tools/compare/phase_g_check.py wasm-native --wasm FILE.wasm --exe target/release/doorplate [--rows 10000000]
    python tools/compare/phase_g_check.py threads [--rows 10000000] [--workers 13]

`wasm-native`: the rows are parsed by the WebAssembly build (`parse_batch` in Node, fields mode, as the demo page's CSV
section does) and by the native command-line tool (`doorplate parse-file`, which writes the same 30 columns from the same
`json::row`), and the two answers are compared column by column. Expected: 0 rows differ.

`threads`: the rows go through the Python batch call (`parse_fields_many`, parallel with rayon) twice, with
`RAYON_NUM_THREADS=1` and `=WORKERS`, and the key, unit-level key, warnings and unit fields are compared row by row.
Expected: 0 rows differ. Uses the `doorplate` that is installed in the running Python.

The sample is every source of `local-data/keycompare/sources.txt` (or `--sources FILE`), drawn with DuckDB's seeded reservoir sample,
and is processed in chunks of `--chunk` rows, so the disk holds one chunk at a time. Stdout and the exit status carry counts only
(0: no difference, 1: some rows differ, 2: the check could not run); no row text is printed or kept: the chunk files live in a
temporary directory under `local-data/` and are deleted. `--error-log FILE` keeps the full traceback of a failed check in a local file. Needs `duckdb`; `wasm-native` needs `node` (20 or newer).
This library formats and parses; it does not validate that an address exists or can receive mail.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FIELDS = ("line1", "line2", "city", "state", "zip")
COLUMNS = [
    "street_number", "street_dir_prefix", "street_name", "street_suffix", "street_dir_suffix", "unit_type", "unit_number",
    "second_unit_type", "second_unit_number", "city", "state", "zip5", "zip4", "place", "place_source", "highway", "po_box",
    "rural_route", "general_delivery", "military", "military_post_office", "attention", "building", "usps_line1",
    "usps_last_line", "key", "key_unit", "slug", "warnings", "unparsed",
]  # fmt: skip  (json::COLUMNS of the command-line tool; the check reads the wasm answer by position)


def sources(path):
    return [ROOT / p.strip() for p in Path(path).read_text().splitlines() if p.strip() and not p.startswith("#")]


def sample_table(con, srcs, rows, seed):
    """A DuckDB table `s(rn, line1..zip)` of `rows` rows drawn with a seed from all sources (empty text kept as '')."""
    parts = []
    for p in srcs:
        cols = {r[0] for r in con.execute(f"describe select * from '{p}'").fetchall()}
        sel = ", ".join(f"coalesce(cast({c} as varchar), '') as {c}" if c in cols else f"'' as {c}" for c in FIELDS)
        parts.append(f"select {sel} from '{p}'" + (" where last_line is null" if "last_line" in cols else ""))
    con.execute("create table s0 as " + " union all ".join(parts))
    total = con.execute("select count(*) from s0").fetchone()[0]
    take = min(rows, total)
    con.execute(f"create table s as select row_number() over () - 1 as rn, * from "
                f"(select * from s0 using sample reservoir({take} rows) repeatable ({seed}))")
    con.execute("drop table s0")
    return take


def read_native_csv(con, path):
    """Load the native tool's CSV as the table `nat(i, ...)`, all columns text. The dialect is pinned (comma, `"` quote and escape):
    DuckDB's sniffer takes an apostrophe for the quote character in a chunk where it is common (`AVENUE 'O'`) and then reads the
    wrong number of columns (the InvalidInputException that stopped the away run's 10M check, #579)."""
    con.execute(f"create or replace table nat as select row_number() over () - 1 as i, * from "
                f"read_csv('{path}', header=true, all_varchar=true, delim=',', quote='\"', escape='\"', strict_mode=false)")


def compare_wasm_native(args, con, tmp, n):
    cmd_wasm = ["node", str(HERE / "wasm_batch.mjs"), str(args.wasm)]
    differ = collections_counter = {}
    total_diff_rows = 0
    per_col = dict.fromkeys(COLUMNS, 0)
    for lo in range(0, n, args.chunk):
        hi = min(lo + args.chunk, n)
        inp, outp = tmp / "in.csv", tmp / "native.csv"
        rows_json, wasm_out = tmp / "rows.json", tmp / "wasm.jsonl"
        con.execute(f"copy (select {', '.join(FIELDS)} from s where rn >= {lo} and rn < {hi} order by rn) to '{inp}' (header)")
        rows = con.execute(f"select {', '.join(FIELDS)} from s where rn >= {lo} and rn < {hi} order by rn").fetchall()
        rows_json.write_text(json.dumps([list(r) for r in rows]))
        del rows
        r = subprocess.run([str(args.exe), "parse-file", str(inp), "--column", "line1", "--line2", "line2", "--city", "city",
                            "--state", "state", "--zip", "zip", "-o", str(outp)], capture_output=True, text=True)
        if r.returncode != 0:
            print("native tool failed", file=sys.stderr)
            return 2
        r = subprocess.run([*cmd_wasm, str(rows_json), str(wasm_out)], capture_output=True, text=True)
        if r.returncode != 0:
            print("node failed", file=sys.stderr)
            return 2
        # the native file: the five input columns, then COLUMNS; the wasm file: one array (or null) per input row
        read_native_csv(con, outp)
        con.execute(f"create or replace table was as select row_number() over () - 1 as i, c from "
                    f"read_json('{wasm_out}', format='newline_delimited', columns={{c: 'VARCHAR[]'}})")
        nn, nw = (con.execute(f"select count(*) from {t}").fetchone()[0] for t in ("nat", "was"))
        if not (nn == nw == hi - lo):
            print(f"row counts differ: native {nn}, wasm {nw}, expected {hi - lo}", file=sys.stderr)
            return 2
        conds = {c: f"coalesce(nat.\"addr_{c}\", '') is distinct from coalesce(was.c[{k + 1}], '')" for k, c in enumerate(COLUMNS)}
        cols_sql = ", ".join(f"sum(case when {cond} then 1 else 0 end) as \"{c}\"" for c, cond in conds.items())
        any_sql = " or ".join(conds.values())
        res = con.execute(f"select count(*) filter (where {any_sql}), {cols_sql} from nat join was using (i)").fetchone()
        total_diff_rows += res[0]
        for c, v in zip(COLUMNS, res[1:], strict=True):
            per_col[c] += v or 0
        print(f"##progress sub={hi}/{n} label=wasm-native diff_rows={total_diff_rows}", flush=True)
        for f in (inp, outp, rows_json, wasm_out):
            f.unlink(missing_ok=True)
    cols = {c: v for c, v in per_col.items() if v}
    print(f"wasm vs native: {n} rows, {total_diff_rows} differ; columns that differ {cols}")
    return 1 if total_diff_rows else 0


WORKER = r"""
import os, sys, duckdb, pyarrow as pa, pyarrow.parquet as pq, doorplate
inp, out = sys.argv[1:3]
res = duckdb.connect().execute(f"select rn, line1, line2, city, state, zip from '{inp}' order by rn")
t = (res.to_arrow_table() if hasattr(res, "to_arrow_table") else res.fetch_arrow_table()).to_pydict()
n = {}
kw = {k: [v or None for v in t[k]] for k in ("line1", "line2", "city", "state", "zip")}
parsed = doorplate.parse_fields_many(**kw)
def w(p):
    return "|".join(x if isinstance(x, str) else getattr(x, "code", str(x)) for x in p.warnings) if p is not None else None
cols = {"rn": t["rn"], "key": [p.key() if p is not None else None for p in parsed],
        "key_unit": [p.key(unit=True) if p is not None else None for p in parsed],
        "warnings": [w(p) for p in parsed]}
for f in ("unit_type", "unit_number", "second_unit_type", "second_unit_number"):
    cols[f] = [getattr(p, f) if p is not None else None for p in parsed]
pq.write_table(pa.table(cols), out)
"""


def compare_threads(args, con, tmp, n):
    total_diff_rows = 0
    per_col = {}
    for lo in range(0, n, args.chunk):
        hi = min(lo + args.chunk, n)
        inp = tmp / "chunk.parquet"
        con.execute(f"copy (select * from s where rn >= {lo} and rn < {hi}) to '{inp}' (format parquet)")
        outs = []
        for t in (1, args.workers):
            o = tmp / f"out-{t}.parquet"
            env = {**os.environ, "RAYON_NUM_THREADS": str(t)}
            r = subprocess.run([sys.executable, "-I", "-c", WORKER, str(inp), str(o)], env=env, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"worker with {t} threads failed", file=sys.stderr)
                return 2
            outs.append(o)
        cols = ["key", "key_unit", "warnings", "unit_type", "unit_number", "second_unit_type", "second_unit_number"]
        conds = {c: f"a.{c} is distinct from b.{c}" for c in cols}
        sel = ", ".join(f"sum(case when {v} then 1 else 0 end) as {c}" for c, v in conds.items())
        res = con.execute(f"select count(*), count(*) filter (where {' or '.join(conds.values())}), {sel} "
                          f"from '{outs[0]}' a join '{outs[1]}' b using (rn)").fetchone()
        if res[0] != hi - lo:
            print(f"row counts differ: joined {res[0]}, expected {hi - lo}", file=sys.stderr)
            return 2
        total_diff_rows += res[1]
        for c, v in zip(cols, res[2:], strict=True):
            per_col[c] = per_col.get(c, 0) + (v or 0)
        print(f"##progress sub={hi}/{n} label=threads diff_rows={total_diff_rows}", flush=True)
        for f in (inp, *outs):
            f.unlink(missing_ok=True)
    print(f"1 vs {args.workers} threads: {n} rows, {total_diff_rows} differ; columns that differ {({c: v for c, v in per_col.items() if v})}")
    return 1 if total_diff_rows else 0


def main(argv=None):
    import duckdb

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("check", choices=["wasm-native", "threads"])
    ap.add_argument("--wasm", type=Path)
    ap.add_argument("--exe", type=Path)
    ap.add_argument("--rows", type=int, default=10_000_000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--chunk", type=int, default=500_000)
    ap.add_argument("--workers", type=int, default=13)
    ap.add_argument("--sources", type=Path, default=ROOT / "local-data" / "keycompare" / "sources.txt")
    ap.add_argument("--tmp-root", type=Path, default=ROOT / "local-data" / "phase-g")
    ap.add_argument("--error-log", type=Path, help="write the full traceback of a failed check here (DuckDB messages can quote rows: "
                    "keep the file in local-data); the output still names only the exception type")
    args = ap.parse_args(argv)
    if args.check == "wasm-native" and not (args.wasm and args.exe and args.wasm.exists() and args.exe.exists()):
        print("wasm-native needs --wasm and --exe that exist (build: cargo build --release -p doorplate-cli; "
              "cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release)", file=sys.stderr)
        return 2
    args.tmp_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=args.tmp_root))
    t0 = time.time()
    try:
        con = duckdb.connect()
        try:
            n = sample_table(con, sources(args.sources), args.rows, args.seed)
        except Exception as e:  # noqa: BLE001  DuckDB errors can quote rows
            print(f"sampling failed: {type(e).__name__}", file=sys.stderr)
            return 2
        print(f"sample: {n} rows, seed {args.seed}")
        try:
            rc = (compare_wasm_native if args.check == "wasm-native" else compare_threads)(args, con, tmp, n)
        except Exception as e:  # noqa: BLE001
            print(f"check failed: {type(e).__name__}", file=sys.stderr)
            if args.error_log:
                args.error_log.write_text(traceback.format_exc())
            return 2
        print(f"{'OK' if rc == 0 else 'DIFFERENCES' if rc == 1 else 'NOT RUN'} after {time.time() - t0:.0f} s")
        return rc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
