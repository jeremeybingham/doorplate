#!/usr/bin/env python3
"""The row-by-row key comparison between two doorplate builds (docs/backlog.md, "The comparison").

Run `dump` once per build, each in the environment that has that build installed, then `diff`:

    python tools/compare/key_diff.py dump local-data/irs-eo-bmf-2026/records.parquet --out local-data/keycompare/v031
    python tools/compare/key_diff.py diff local-data/keycompare/v031 local-data/keycompare/dev

`dump` parses the records file with `parse_fields_many` and writes `<out>/<source>.parquet` with one row per
record (row number, source, role, record id, key, warning codes) and `<out>/<source>.json` with the doorplate
version. Rows with a `last_line` are left out (the harness joins those into one string; none of the key sources
use it). `diff` compares two such directories row by row and prints counts only, by source and role: the rows
with a different key, with different warnings, and the shapes of the keys that changed. It never prints
names or street text; the files stay in the git-ignored `local-data/`.
"""

import argparse
import json
import sys
from pathlib import Path

CHUNK = 250_000
FIELDS = ("line1", "line2", "city", "state", "zip")


def dump(args):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    import doorplate

    src = Path(args.records)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        cols = {r[0] for r in con.execute(f"describe select * from '{src}'").fetchall()}
        use = [c for c in FIELDS if c in cols]
        has_last = "last_line" in cols
        name = con.execute(f"select any_value(source) from '{src}'").fetchone()[0]
        total = con.execute(f"select count(*) from '{src}'").fetchone()[0]
    except Exception as e:  # DuckDB errors can quote rows
        sys.exit(f"failed: {type(e).__name__}")
    name = args.name or name
    sel = ", ".join(use)
    skip = "last_line is null" if has_last else "true"
    schema = pa.schema([("rn", pa.int64()), ("role", pa.string()), ("record_id", pa.string()),
                        ("key", pa.string()), ("warnings", pa.string())])
    writer = pq.ParquetWriter(out / f"{name}.parquet", schema)
    done = skipped = 0
    try:
        for lo in range(0, total, CHUNK):
            q = (f"select rn, role, record_id, {sel}, {skip} as keep from "
                 f"(select row_number() over () - 1 as rn, * from '{src}') "
                 f"where rn >= {lo} and rn < {lo + CHUNK}")
            res = con.execute(q)
            rows = (res.to_arrow_table() if hasattr(res, "to_arrow_table") else res.fetch_arrow_table()).to_pydict()
            keep = rows["keep"]
            idx = [i for i, k in enumerate(keep) if k]
            skipped += len(keep) - len(idx)
            kw = {c: [rows[c][i] for i in idx] for c in use}
            parsed = doorplate.parse_fields_many(**kw)
            keys = [p.key() if p is not None else None for p in parsed]
            warns = ["|".join(w if isinstance(w, str) else getattr(w, "code", str(w))
                              for w in p.warnings) if p is not None else None for p in parsed]
            writer.write_table(pa.table({
                "rn": [rows["rn"][i] for i in idx], "role": [rows["role"][i] for i in idx],
                "record_id": [rows["record_id"][i] for i in idx], "key": keys, "warnings": warns},
                schema=schema))
            done += len(idx)
            print(f"{name}: {done} rows", file=sys.stderr)
    finally:
        writer.close()
    (out / f"{name}.json").write_text(json.dumps(
        {"source": name, "records": str(src), "doorplate": doorplate.__version__,
         "rows": done, "skipped_last_line": skipped}, indent=2) + "\n")
    print(f"{name}: {done} rows parsed with doorplate {doorplate.__version__} ({skipped} with last_line left out)")


def diff(args):
    import duckdb

    a, b = Path(args.a), Path(args.b)
    names = sorted(p.stem for p in a.glob("*.parquet") if (b / p.name).exists())
    if not names:
        sys.exit("no source in both directories")
    con = duckdb.connect()
    # The key with letters as a and digits as 9, so counts can be given without street text. A SQL macro,
    # not a Python function: DuckDB 2.0 needs numpy for those.
    con.execute("create macro shape(k) as regexp_replace(regexp_replace(k, '\\p{L}', 'a', 'g'), '\\p{Nd}', '9', 'g')")
    total_changed = 0
    for n in names:
        va = json.loads((a / f"{n}.json").read_text())
        vb = json.loads((b / f"{n}.json").read_text())
        try:
            con.execute(f"create or replace view x as select * from '{a / (n + '.parquet')}'")
            con.execute(f"create or replace view y as select * from '{b / (n + '.parquet')}'")
            print(f"\n== {n}: {va['doorplate']} -> {vb['doorplate']}, rows {va['rows']} / {vb['rows']}")
            res = con.execute("""
                select x.role, count(*) n,
                  sum(case when x.key is distinct from y.key then 1 else 0 end) key_changed,
                  sum(case when x.warnings is distinct from y.warnings then 1 else 0 end) warn_changed
                from x join y using (rn) group by 1 order by 1""").fetchall()
            for role, rows, kc, wc in res:
                print(f"  {role or '(none)':<14} rows {rows:>9}  key changed {kc:>8}  warnings changed {wc:>8}")
                total_changed += kc
            if sum(r[2] for r in res):
                print("  shapes of changed keys (top 5, before):")
                for s, c in con.execute("""
                    select shape(x.key), count(*) c from x join y using (rn)
                    where x.key is distinct from y.key group by 1 order by c desc limit 5""").fetchall():
                    print(f"    {c:>8}  {s}")
        except Exception as e:
            # a parser error quotes only our SQL; anything else may quote rows
            sys.exit(f"failed: {type(e).__name__}" + (f": {e}" if isinstance(e, duckdb.ParserException) else ""))
    print(f"\ntotal rows with a changed key: {total_changed}")
    return 1 if total_changed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump", help="parse a records file and write the keys")
    d.add_argument("records")
    d.add_argument("--out", required=True)
    d.add_argument("--name", help="file name for the source (default: the records' source column)")
    f = sub.add_parser("diff", help="compare two dump directories")
    f.add_argument("a")
    f.add_argument("b")
    args = ap.parse_args()
    if args.cmd == "dump":
        dump(args)
    else:
        sys.exit(diff(args))


if __name__ == "__main__":
    main()
