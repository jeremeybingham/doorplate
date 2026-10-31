#!/usr/bin/env python3
"""The row-by-row key comparison between two doorplate builds (docs/backlog.md, "The comparison").

Run `dump` once per build (or `dump-all --out DIR [--unit]` for every file in `local-data/keycompare/sources.txt`), each in the environment that has that build installed, then `diff`:

    python tools/compare/key_diff.py dump local-data/irs-eo-bmf-2026/records.parquet --out local-data/keycompare/v031
    python tools/compare/key_diff.py diff local-data/keycompare/v031 local-data/keycompare/dev

`dump` parses the records file with `parse_fields_many` and writes `<out>/<source>.parquet` with one row per
record (row number, source, role, record id, key, warning codes) and `<out>/<source>.json` with the doorplate
version, the checkout's commit (marked `+dirty` when the tree has uncommitted changes) and whether the installed
extension is older than the newest file under `crates/doorplate/src`, since the version string alone names a build
only between releases (on `main`, after 0.4.1, it still says 0.4.1). Rows with a `last_line` are left out (the harness joins those into one string; none of the key sources
use it). `diff` compares two such directories row by row and prints counts only, by source and role: the rows
with a different key, with different warnings, and the shapes of the keys that changed. It never prints
names or street text; the files stay in the git-ignored `local-data/`.

`dump --unit` also writes the unit-level key (`key(unit=True)`) and the four unit fields (`unit_type`, `unit_number`,
`second_unit_type`, `second_unit_number`). The property-level key has no unit, so a rule that only moves a unit value
(from the second slot to the first, say) changes no property key and `diff` shows 0 without them. When both dumps have the
columns, `diff` also counts, by source and role, the rows with a different unit-level key and with different unit fields,
and prints the shapes of the changed unit-level keys; a changed unit-level key makes the exit status non-zero like a
changed key.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CHUNK = 250_000
FIELDS = ("line1", "line2", "city", "state", "zip")


def build_info():
    """(commit, stale): the checkout's short commit, with +dirty for uncommitted changes (None outside git), and whether
    the installed extension is older than the newest Rust source file (rebuild with `maturin develop --release`)."""
    import doorplate

    try:
        git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
        commit = git("rev-parse", "--short", "HEAD") + ("+dirty" if git("status", "--porcelain", "--untracked-files=no") else "")
    except (OSError, subprocess.CalledProcessError):
        commit = None
    ext = [p for p in Path(doorplate.__file__).parent.glob("*.so")] + [p for p in Path(doorplate.__file__).parent.glob("*.pyd")]
    src = [p.stat().st_mtime for p in (ROOT / "crates" / "doorplate" / "src").rglob("*.rs")]
    stale = bool(ext and src and max(p.stat().st_mtime for p in ext) < max(src))
    return commit, stale


def dump(args):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    import doorplate

    commit, stale = build_info()
    if stale:
        print("warning: the installed extension is older than crates/doorplate/src: rebuild it (maturin develop --release) "
              "or this dump is not of the checkout", file=sys.stderr)
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
    fields = [("rn", pa.int64()), ("role", pa.string()), ("record_id", pa.string()),
              ("key", pa.string()), ("warnings", pa.string())]
    if args.unit:
        fields += [("key_unit", pa.string()), ("unit_type", pa.string()), ("unit_number", pa.string()),
                   ("second_unit_type", pa.string()), ("second_unit_number", pa.string())]
    schema = pa.schema(fields)
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
            cols_out = {
                "rn": [rows["rn"][i] for i in idx], "role": [rows["role"][i] for i in idx],
                "record_id": [rows["record_id"][i] for i in idx], "key": keys, "warnings": warns}
            if args.unit:
                cols_out["key_unit"] = [p.key(unit=True) if p is not None else None for p in parsed]
                for f in ("unit_type", "unit_number", "second_unit_type", "second_unit_number"):
                    cols_out[f] = [getattr(p, f) if p is not None else None for p in parsed]
            writer.write_table(pa.table(cols_out, schema=schema))
            done += len(idx)
            print(f"{name}: {done} rows", file=sys.stderr)
    finally:
        writer.close()
    (out / f"{name}.json").write_text(json.dumps(
        {"source": name, "records": str(src), "doorplate": doorplate.__version__,
         "commit": commit, "extension_older_than_source": stale, "rows": done, "skipped_last_line": skipped,
         "unit": bool(args.unit)}, indent=2) + "\n")
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
    # The version prefix (`k2`, `k3`, `k4`) is left out of the comparison, so the keys of the cut compare row by row with
    # the frozen keys of the version before it: a changed key is a changed layout or value, not the new prefix.
    con.execute("create macro body(k) as regexp_replace(k, '^k[0-9]+', 'k')")
    total_changed = 0
    for n in names:
        va = json.loads((a / f"{n}.json").read_text())
        vb = json.loads((b / f"{n}.json").read_text())
        try:
            con.execute(f"create or replace view x as select * from '{a / (n + '.parquet')}'")
            con.execute(f"create or replace view y as select * from '{b / (n + '.parquet')}'")
            label = lambda v: f"{v['doorplate']} ({v.get('commit') or 'commit unknown'})"  # noqa: E731
            print(f"\n== {n}: {label(va)} -> {label(vb)}, rows {va['rows']} / {vb['rows']}")
            res = con.execute("""
                select x.role, count(*) n,
                  sum(case when body(x.key) is distinct from body(y.key) then 1 else 0 end) key_changed,
                  sum(case when x.warnings is distinct from y.warnings then 1 else 0 end) warn_changed
                from x join y using (rn) group by 1 order by 1""").fetchall()
            for role, rows, kc, wc in res:
                print(f"  {role or '(none)':<14} rows {rows:>9}  key changed {kc:>8}  warnings changed {wc:>8}")
                total_changed += kc
            ucols = {c for c in ("key_unit", "unit_type", "unit_number", "second_unit_type", "second_unit_number")}
            have_unit = all(ucols <= {r[0] for r in con.execute(f"describe select * from {v}").fetchall()} for v in ("x", "y"))
            if have_unit:
                ures = con.execute("""
                    select x.role, count(*) n,
                      sum(case when body(x.key_unit) is distinct from body(y.key_unit) then 1 else 0 end) ukey,
                      sum(case when x.unit_type is distinct from y.unit_type or x.unit_number is distinct from y.unit_number then 1 else 0 end) first_unit,
                      sum(case when x.second_unit_type is distinct from y.second_unit_type
                                 or x.second_unit_number is distinct from y.second_unit_number then 1 else 0 end) second_unit
                    from x join y using (rn) group by 1 order by 1""").fetchall()
                print("  unit level (dump --unit):")
                for role, rows, uk, fu, su in ures:
                    print(f"  {role or '(none)':<14} rows {rows:>9}  unit key changed {uk:>8}  first unit changed {fu:>8}  second unit changed {su:>8}")
                    total_changed += uk
                if sum(r[2] for r in ures):
                    print("  shapes of changed unit-level keys (top 5, before):")
                    for s_, c in con.execute("""
                        select shape(x.key_unit), count(*) c from x join y using (rn)
                        where body(x.key_unit) is distinct from body(y.key_unit) group by 1 order by c desc limit 5""").fetchall():
                        print(f"    {c:>8}  {s_}")
            if sum(r[2] for r in res):
                print("  shapes of changed keys (top 5, before):")
                for s, c in con.execute("""
                    select shape(x.key), count(*) c from x join y using (rn)
                    where body(x.key) is distinct from body(y.key) group by 1 order by c desc limit 5""").fetchall():
                    print(f"    {c:>8}  {s}")
        except Exception as e:
            # a parser error quotes only our SQL; anything else may quote rows
            sys.exit(f"failed: {type(e).__name__}" + (f": {e}" if isinstance(e, duckdb.ParserException) else ""))
    print(f"\ntotal rows with a changed key: {total_changed}")
    return 1 if total_changed else 0


def dump_all(args):
    """`dump` for every records file listed in the sources file, one after the other (about 7 minutes for the seven)."""
    paths = [l.strip() for l in Path(args.sources).read_text().splitlines() if l.strip() and not l.startswith("#")]
    for path in paths:
        print(f"start {path} {time.strftime('%H:%M:%S')}", flush=True)
        dump(argparse.Namespace(records=path, out=args.out, name=None, unit=args.unit))
    print(f"all done {time.strftime('%H:%M:%S')}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump", help="parse a records file and write the keys")
    d.add_argument("records")
    d.add_argument("--out", required=True)
    d.add_argument("--name", help="file name for the source (default: the records' source column)")
    d.add_argument("--unit", action="store_true",
                   help="also write the unit-level key and the unit fields (for a rule that moves or reads a unit)")
    a = sub.add_parser("dump-all", help="dump every records file in the sources file")
    a.add_argument("--out", required=True)
    a.add_argument("--sources", default=str(ROOT / "local-data/keycompare/sources.txt"))
    a.add_argument("--unit", action="store_true", help="as for dump")
    f = sub.add_parser("diff", help="compare two dump directories")
    f.add_argument("a")
    f.add_argument("b")
    args = ap.parse_args()
    if args.cmd == "dump":
        dump(args)
    elif args.cmd == "dump-all":
        dump_all(args)
    else:
        sys.exit(diff(args))


if __name__ == "__main__":
    main()
