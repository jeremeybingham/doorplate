#!/usr/bin/env python3
"""Turn one address source into the common record format (tools/ingest/README.md).

    python tools/ingest/ingest.py SPEC.toml              # print the plan
    python tools/ingest/ingest.py SPEC.toml --confirm    # write the records
    python tools/ingest/ingest.py SPEC.toml --limit 1000 --confirm

A spec names the source, its inputs and one SQL query per role (for example
`residential` and `mailing`); the queries map the source's columns to the record
columns. This script runs them with DuckDB, trims every value (empty becomes
null), checks the columns, and writes `records.parquet` and `records.json`
beside each other. Paths in a spec are relative to the repository root.

Specs for private sources live with their data in `local-data/`; the ones in
`tools/ingest/specs/` are for sources the documentation already names. Errors are
printed without their message unless they come from the SQL itself (a misspelled
column), because DuckDB quotes source rows, which can hold names
(docs/data-policy.md). This library formats and parses; it does not validate that
an address exists or can receive mail.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORMAT_VERSION = 1

# The record columns, in order. Every value is a string or null.
REQUIRED = ["record_id", "role", "line1"]
ADDRESS = ["line2", "city", "state", "zip", "last_line"]
LABELS = ["label_number_prefix", "label_number", "label_number_suffix", "label_predir",
          "label_pretype", "label_name", "label_type", "label_postdir", "label_postmod",
          "label_unit_type", "label_unit", "label_building"]
COLUMNS = ["source"] + REQUIRED + ["pair_id", "provider"] + ADDRESS + LABELS
SQL_ERRORS = ("BinderException", "ParserException", "CatalogException")
MB = 1 << 20


class SpecError(Exception):
    pass


def load_spec(path):
    with open(path, "rb") as f:
        spec = tomllib.load(f)
    for key in ("source", "output", "inputs", "roles"):
        if key not in spec:
            raise SpecError(f"{path}: missing `{key}`")
    if not spec["roles"]:
        raise SpecError(f"{path}: no roles")
    for r in spec["roles"]:
        if "role" not in r or "sql" not in r:
            raise SpecError(f"{path}: every [[roles]] entry needs `role` and `sql`")
    names = [r["role"] for r in spec["roles"]]
    if len(names) != len(set(names)):
        raise SpecError(f"{path}: a role is listed twice")
    return spec


def fingerprint(path):
    """Size, mtime and the SHA-256 of the first and last MiB: enough to tell inputs apart."""
    p = Path(path)
    st = p.stat()
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read(MB))
        if st.st_size > 2 * MB:
            f.seek(-MB, os.SEEK_END)
            h.update(f.read(MB))
    return {"path": str(path), "bytes": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "head_tail_sha256": h.hexdigest()}


def input_files(spec):
    """The files each input reads: `path` for SQLite inputs, `files` (optional) for the rest."""
    out = {}
    for name, inp in spec["inputs"].items():
        if isinstance(inp, str):
            raise SpecError(f"input `{name}`: use a table with `sql` (and `files`), not a bare string")
        if "sqlite" in inp:
            out[name] = [inp["sqlite"]]
        else:
            out[name] = list(inp.get("files", []))
    return out


def rel(path):
    p = Path(path).resolve()
    return p.relative_to(ROOT) if p.is_relative_to(ROOT) else p


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def sqlite_to_parquet(name, inp, tmp_dir):
    """Copy a SQLite table (or query) to a temporary Parquet file in batches and return its path.
    DuckDB's SQLite extension is not installed offline, so this goes through Python's sqlite3."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    src = sqlite3.connect(Path(inp["sqlite"]).resolve().as_uri() + "?mode=ro", uri=True)
    cur = src.execute(inp["query"])
    cols = [d[0] for d in cur.description]
    schema = pa.schema([(c, pa.string()) for c in cols])
    out = tmp_dir / f".ingest_tmp_{name}.parquet"
    with pq.ParquetWriter(out, schema, compression="zstd") as w:
        while True:
            rows = cur.fetchmany(200_000)
            if not rows:
                break
            data = [[None if r[i] is None else str(r[i]) for r in rows] for i in range(len(cols))]
            w.write_table(pa.table(data, schema=schema))
    src.close()
    return out


def check_role_columns(con, role, sql):
    """The role's columns: only record columns, `record_id` and `line1` present, no `role`."""
    got = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM ({sql})").fetchall()]
    unknown = [c for c in got if c not in COLUMNS[1:] or c == "role"]
    missing = [c for c in REQUIRED if c != "role" and c not in got]
    if unknown:
        raise SpecError(f"role `{role}`: columns not in the record format (the script adds "
                        f"`source` and `role`): {unknown}")
    if missing:
        raise SpecError(f"role `{role}`: missing required columns: {missing}")
    return got


def role_query(role, sql, got, limit):
    """Every record column, in order, trimmed, empty as null; absent columns are null."""
    cols = []
    for c in COLUMNS[1:]:
        if c == "role":
            cols.append(f"'{role}' AS role")
        elif c in got:
            cols.append(f"nullif(trim(CAST(\"{c}\" AS VARCHAR)), '') AS {c}")
        else:
            cols.append(f"CAST(NULL AS VARCHAR) AS {c}")
    lim = f" LIMIT {int(limit)}" if limit else ""
    return f"SELECT {', '.join(cols)} FROM (SELECT * FROM ({sql}){lim})"


def build(spec, spec_path, limit, out_override=None):
    import duckdb
    out = ROOT / (out_override or spec["output"])
    out.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")
    tmp_out = out.with_suffix(".parquet.part")
    tmp = [tmp_out]
    try:
        for name, inp in spec["inputs"].items():
            if "sqlite" in inp:
                p = sqlite_to_parquet(name, inp, out.parent)
                tmp.append(p)
                con.execute(f"CREATE VIEW \"{name}\" AS SELECT * FROM read_parquet('{p}')")
            else:
                con.execute(f"CREATE VIEW \"{name}\" AS {inp['sql']}")
        parts = []
        for r in spec["roles"]:
            role = r["role"].replace("'", "")
            got = check_role_columns(con, role, r["sql"])
            parts.append(role_query(role, r["sql"], got, limit))
        source = spec["source"].replace("'", "")
        union = " UNION ALL ".join(f"SELECT '{source}' AS source, * FROM ({q})" for q in parts)
        con.execute(f"COPY ({union}) TO '{tmp_out}' (FORMAT parquet, COMPRESSION zstd)")
        os.replace(tmp_out, out)
        stats = summarize(con, out)
    finally:
        for p in tmp:
            p.unlink(missing_ok=True)
    meta = {
        "format_version": FORMAT_VERSION,
        "source": spec["source"],
        "spec": str(rel(spec_path)),
        "spec_sha256": hashlib.sha256(Path(spec_path).read_bytes()).hexdigest(),
        "inputs": {n: [{**fingerprint(ROOT / f), "path": str(f)} for f in fs]
                   for n, fs in input_files(spec).items()},
        "limit": limit,
        "commit": git_commit(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **stats,
    }
    out.with_name(out.stem + ".json").write_text(json.dumps(meta, indent=2) + "\n")
    return out, meta


def summarize(con, out):
    """Counts only: rows and non-null share of each column per role, and duplicate ids."""
    roles = {}
    nonnull = ", ".join(f"count({c})" for c in COLUMNS[1:])
    for row in con.execute(f"SELECT role, count(*), {nonnull} FROM '{out}' GROUP BY role ORDER BY role").fetchall():
        role, n, *counts = row
        roles[role] = {"rows": n,
                       "present": {c: round(k / n, 4) for c, k in zip(COLUMNS[1:], counts) if k}}
    dup = con.execute(f"SELECT count(*) FROM (SELECT role, record_id FROM '{out}' "
                      "GROUP BY ALL HAVING count(*) > 1)").fetchone()[0]
    return {"rows": sum(r["rows"] for r in roles.values()), "roles": roles, "duplicate_ids": dup}


def plan(spec, spec_path, limit, output=None):
    lines = [f"plan for {spec_path}", f"  source  {spec['source']}"]
    for name, files in input_files(spec).items():
        for f in files:
            p = ROOT / f
            size = f"{p.stat().st_size / (1 << 30):.2f} GB" if p.exists() else "MISSING"
            lines.append(f"  input   {name}: {f} ({size})")
        if not files:
            lines.append(f"  input   {name}: (no `files` listed; not fingerprinted)")
    lines.append(f"  roles   {', '.join(r['role'] for r in spec['roles'])}")
    output = output or spec["output"]
    lines.append(f"  write   {output} and {Path(output).stem}.json"
                 + (f" (first {limit:,} rows of each role)" if limit else ""))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", type=Path)
    ap.add_argument("--confirm", action="store_true", help="write the records (default: print the plan)")
    ap.add_argument("--limit", type=int, help="only the first N rows of each role (a quick check)")
    ap.add_argument("--output", help="write here instead of the spec's `output` (relative to the root)")
    args = ap.parse_args(argv)
    os.chdir(ROOT)
    try:
        spec = load_spec(args.spec)
        print(plan(spec, args.spec, args.limit, args.output))
        missing = [f for fs in input_files(spec).values() for f in fs if not (ROOT / f).exists()]
        if missing:
            return f"inputs not found: {missing}"
        if not args.confirm:
            return "Dry run. Re-run with --confirm to write."
        out, meta = build(spec, args.spec, args.limit, args.output)
    except SpecError as e:
        return f"spec error: {e}"
    except Exception as e:  # noqa: BLE001 - never echo source rows
        name = type(e).__name__
        if name in SQL_ERRORS:
            return f"SQL error in the spec: {name}: {str(e).splitlines()[0]}"
        return f"failed: {name} (message suppressed: it can quote source rows)"
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"wrote {shown}: {meta['rows']:,} rows")
    for role, r in meta["roles"].items():
        print(f"  {role:12s} {r['rows']:>11,} rows")
    if meta["duplicate_ids"]:
        print(f"  note: {meta['duplicate_ids']:,} (role, record_id) pairs occur more than once")
    return 0


if __name__ == "__main__":
    sys.exit(main())
