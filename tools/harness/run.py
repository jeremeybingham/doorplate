#!/usr/bin/env python3
"""Parse an address source with doorplate and store artifacts for later analysis.
Offline, resumable, nothing is committed.

    python tools/harness/run.py --input local-data/nc-voter-2026/records_current.parquet
    python tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample

`--input` reads the record format of tools/ingest (any source, one file per source).
`--db` reads the Netsyms SQLite columns directly (the original path, kept to check that
the Netsyms records give the same numbers).

Without `--confirm` it only prints the plan (input, row range, chunks, paths, disk
budget) and exits. With it, it writes a run directory under
`local-data/netsyms-runs/<run-id>/` (see tools/harness/README.md and SCHEMA.md).

The input stays in `local-data/` and is never copied into the repository. See
docs/data-policy.md: only aggregate numbers leave the run directory. This library
formats and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCHEMA_VERSION = 5
REQUIRED = ["zipcode", "number", "street", "street2", "city", "state", "plus4", "country", "source"]
GB = 1 << 30
# The columns of a row as the checks see it (tools/ingest/README.md has their meaning).
COLS = ["record_id", "source", "role", "provider", "line1", "line2", "city", "state", "zip",
        "last_line", "label_number"]
# Columns whose presence in a role decides which consistency checks run on its rows.
PRESENT = ["line2", "city", "state", "zip", "last_line", "label_number", "label_unit"]


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", type=Path, help="a records.parquet from tools/ingest")
    src.add_argument("--db", type=Path, help="the Netsyms SQLite database")
    ap.add_argument("--table", default="addresses", help="with --db: table name (the sample uses 'sample')")
    ap.add_argument("--country", default="US", help="with --db: only rows with this country (default US)")
    ap.add_argument("--out-root", type=Path, default=ROOT / "local-data" / "netsyms-runs")
    ap.add_argument("--run-id", help="resume or name a run (default: UTC time + commit)")
    ap.add_argument("--chunk-rowids", type=int, default=200_000,
                    help="rowids per chunk (rows per chunk with --input)")
    ap.add_argument("--limit-chunks", type=int, help="stop after this many chunks (tests)")
    ap.add_argument("--threads", type=int, help="Rust parse threads per worker (default: cores / workers)")
    ap.add_argument("--workers", type=int, default=max(1, min(6, (os.cpu_count() or 2) // 2)),
                    help="processes working on different chunks (default: half the cores, at most 6)")
    ap.add_argument("--budget-gb", type=float, default=60.0,
                    help="abort when the input's folder (not counting .7z archives) plus all runs exceed this (default 60)")
    ap.add_argument("--min-free-gb", type=float, default=20.0, help="refuse to start below this")
    ap.add_argument("--full-hash", action="store_true", help="SHA-256 the whole input file (slow)")
    ap.add_argument("--confirm", action="store_true", help="actually run (default: print the plan)")
    return ap.parse_args(argv)


def dir_size(path):
    """Bytes under `path`, not counting archives (`.7z`): the budget covers the extracted
    database and the runs."""
    total = 0
    for p, _, files in os.walk(path):
        for f in files:
            if f.endswith(".7z"):
                continue
            try:
                total += os.path.getsize(os.path.join(p, f))
            except OSError:
                pass
    return total


def git(*cmd):
    try:
        return subprocess.run(["git", *cmd], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def fingerprint(path, full):
    """Size, mtime and a SHA-256 of the first and last MiB (or of the whole file)."""
    st = path.stat()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        if full:
            for block in iter(lambda: f.read(1 << 24), b""):
                h.update(block)
        else:
            h.update(f.read(1 << 20))
            f.seek(max(0, st.st_size - (1 << 20)))
            h.update(f.read(1 << 20))
    return {"size": st.st_size, "mtime": int(st.st_mtime),
            "sha256": h.hexdigest(), "scope": "whole file" if full else "first and last MiB"}


def data_hash():
    """Hash of the shipped data tables, so a run names the place data it used."""
    h = hashlib.sha256()
    base = ROOT / "crates" / "doorplate" / "data"
    for p in sorted(base.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(base)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def open_db(path):
    # A file URI, so Windows drive letters and spaces work.
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def input_path(args):
    return args.input or args.db


def inspect(args):
    """The first and last row id and, per role, the columns that have any value (they decide
    which consistency checks run). For `--input` the ids are row offsets."""
    if args.input:
        import duckdb

        try:
            con = duckdb.connect()
            n = con.execute("select count(*) from read_parquet(?)", [str(args.input)]).fetchone()[0]
            cols = [r[0] for r in con.execute("describe select * from read_parquet(?)", [str(args.input)]).fetchall()]
            missing = [c for c in ("record_id", "source", "role", "line1") if c not in cols]
            if missing:
                sys.exit(f"{args.input} lacks columns {missing}; has {cols}")
            have = [c for c in PRESENT if c in cols]
            counts = ", ".join(f"count({c})" for c in have) or "0"
            rows = con.execute(f"select role, {counts} from read_parquet(?) group by role",
                               [str(args.input)]).fetchall()
        except Exception as e:  # DuckDB messages can quote rows (docs/data-policy.md)
            sys.exit(f"could not read {args.input}: {type(e).__name__}")
        present = {r[0] or "": sorted(c for c, k in zip(have, r[1:]) if k) for r in rows}
        return 0, max(n - 1, 0), present
    con = open_db(args.db)
    cols = [r[1] for r in con.execute(f"pragma table_info({args.table})")]
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        sys.exit(f"table {args.table!r} lacks columns {missing}; has {cols}")
    lo, hi = con.execute(f"select min(rowid), max(rowid) from {args.table}").fetchone()
    con.close()
    return lo, hi, {"address": ["city", "label_number", "label_unit", "line2", "state", "zip"]}


def plan(args, lo, hi):
    chunks_all = (hi - lo) // args.chunk_rowids + 1
    chunks = min(chunks_all, args.limit_chunks) if args.limit_chunks else chunks_all
    folder = input_path(args).parent
    used = dir_size(folder) + (dir_size(args.out_root) if args.out_root.exists() else 0)
    free = shutil.disk_usage(args.out_root.parent if args.out_root.parent.exists() else ROOT).free
    return {"chunks": chunks, "chunks_all": chunks_all, "used_gb": used / GB, "free_gb": free / GB}


def norm(s):
    return " ".join((s or "").upper().replace(".", "").split())


def compact(s):
    return "".join(ch for ch in norm(s) if ch.isalnum())


def street_text(a):
    return " ".join(p for p in (a.street_dir_prefix, a.street_name, a.street_suffix,
                                a.street_dir_suffix) if p)


def _load_forms():
    """Every suffix and directional spelling mapped to its standard abbreviation, read from
    the shipped tables (crates/doorplate/data/), so `ST` and `STREET` compare equal."""
    canon = {}
    for name in ("suffixes.toml", "directionals.toml"):
        abbr = None
        for line in (ROOT / "crates" / "doorplate" / "data" / name).read_text().splitlines():
            m = re.match(r'abbr = "([^"]+)"', line)
            if m:
                abbr = m.group(1)
            m = re.match(r"forms = \[(.*)\]", line)
            if m and abbr:
                for form in re.findall(r'"([^"]+)"', m.group(1)):
                    canon.setdefault(form.upper(), abbr)
    return canon


FRACTION = re.compile(r"\d+/\d+")
CANON = _load_forms()
SYNONYMS = {"HWY": "HIGHWAY", "RTE": "ROUTE", "CO": "COUNTY", "CTY": "COUNTY"}


def words(text):
    out = []
    for tok in re.findall(r"[A-Z0-9]+", (text or "").upper()):
        tok = CANON.get(tok, tok)
        out.extend(SYNONYMS.get(tok, tok).split())
    return Counter(out)


# Words that name a PO box, rural route, general delivery or military box (`PO BOX 12`, `RR 2 BOX 5`):
# they are the form, not street words, so they are accounted for when the parse found that form.
FORM_WORDS = words("PO P O POST OFFICE BOX POBOX RR HC HCR RURAL ROUTE HIGHWAY CONTRACT GENERAL DELIVERY GD "
                   "PSC CMR UNIT APO FPO DPO")


def street_ok(line1, line2, number, a):
    """True when every word of the source street (line 1 without the house number) is
    accounted for in the parse (as a street part, unit, building, attention, PO box, rural
    route, military box or unparsed text) and every parsed street word came from the source street, its second line or the number
    (junk in the number field, such as `NULL`, is flagged by the `number` mismatch, not here).
    Spelled-out suffixes and standardized highway names are equal, so only real changes to
    the street remain."""
    num = words(number)
    src = words(line1) - num
    parts = [a.street_dir_prefix, a.street_name, a.street_suffix, a.street_dir_suffix]
    if a.highway:
        parts.append(a.highway["name"])
    parsed = words(" ".join(p for p in parts if p))
    elsewhere = words(" ".join(x for x in (
        a.unit_type, a.unit_number, a.second_unit_type, a.second_unit_number, a.unparsed,
        a.building, a.attention, a.po_box) if x))
    if a.po_box or a.rural_route or a.general_delivery or a.military:
        forms = [str(v) for d in (a.rural_route, a.military) if d for v in d.values()]
        elsewhere = elsewhere + FORM_WORDS + words(" ".join(forms))
    return not (src - (parsed + elsewhere)) and not (parsed - (src + words(line2) + num))


def _load_states():
    """Every state's code, name and aliases as upper-case tokens, from the shipped table.
    Read with regular expressions, like `_load_forms`: the harness runs on Python 3.10."""
    out = {}
    code = None
    for line in (ROOT / "crates" / "doorplate" / "data" / "states.toml").read_text().splitlines():
        m = re.match(r'(code|name) = "([^"]+)"', line)
        if m and m.group(1) == "code":
            code = m.group(2)
            out[code] = set(re.findall(r"[A-Z0-9]+", code.upper()))
        elif m and code:
            out[code] |= set(re.findall(r"[A-Z0-9]+", m.group(2).upper()))
        m = re.match(r"aliases = \[(.*)\]", line)
        if m and code:
            for alias in re.findall(r'"([^"]+)"', m.group(1)):
                out[code] |= set(re.findall(r"[A-Z0-9]+", alias.upper()))
    return out


STATE_FORMS = _load_states()


def crossed_boundary(last_line, a):
    """True when the parsed city, state or ZIP use words that are not in `last_line` (#93,
    option A): the parse took them from the street lines, so joining lost the line boundary.
    The state is compared by any of its spellings."""
    ll = words(last_line)
    if words(a.city) - ll:
        return True
    if a.state and not (STATE_FORMS.get(a.state, {a.state}) & set(ll)):
        return True
    text = (last_line or "")
    return any(z and z not in text for z in (a.zip5, a.zip4))


def plus4_of(zipc):
    z = (zipc or "").strip()
    return z[6:] if len(z) > 6 and z[5] == "-" else ""


def fetch_sqlite(con, args, lo, hi):
    """Rows of the Netsyms table in the record shape (`line1` is number + street, the ZIP
    carries `-plus4`), as tools/ingest/specs/netsyms.toml builds them."""
    cur = con.execute(
        f"select rowid, number, street, street2, city, state, zipcode, plus4, source "
        f"from {args.table} where rowid >= ? and rowid < ? and country = ?",
        (lo, hi, args.country),
    )
    return [(str(r[0]), "netsyms", "address", r[8] or None,
             f"{r[1] or ''} {r[2] or ''}".strip() or None, r[3] or None, r[4] or None,
             r[5] or None, ((r[6] or "") + (f"-{r[7]}" if r[7] else "")) or None, None,
             r[1] or "")
            for r in cur.fetchall()]


def fetch_records(con, args, lo, hi):
    have = {r[0] for r in con.execute("describe select * from read_parquet(?)", [str(args.input)]).fetchall()}
    sel = ", ".join(c if c in have else f"NULL AS {c}" for c in
                    ["record_id", "source", "role", "provider", "line1", "line2", "city", "state",
                     "zip", "last_line", "label_number"])
    cur = con.execute(
        f"select {sel} from read_parquet(?, file_row_number = true) "
        f"where file_row_number >= ? and file_row_number < ?", (str(args.input), lo, hi))
    return cur.fetchall()


def parse_rows(rows, fields_many, parse_many):
    """Parse a chunk: rows with a `last_line` as one joined string (option A), the others
    from their separate fields."""
    out = [None] * len(rows)
    sep = [i for i, r in enumerate(rows) if not r[9]]
    joined = [i for i, r in enumerate(rows) if r[9]]
    if sep:
        res = fields_many(line1=[rows[i][4] for i in sep], line2=[rows[i][5] for i in sep],
                          city=[rows[i][6] for i in sep], state=[rows[i][7] for i in sep],
                          zip=[rows[i][8] for i in sep])
        for i, a in zip(sep, res):
            out[i] = a
    if joined:
        res = parse_many([", ".join(x for x in (rows[i][4], rows[i][5], rows[i][9]) if x)
                          for i in joined])
        for i, a in zip(joined, res):
            out[i] = a
    return out


def process_chunk(rows, present, fields_many, parse_many):
    parsed = parse_rows(rows, fields_many, parse_many)
    by_key = {}
    warns = Counter()
    triples = Counter()
    flagged = []
    for r, a in zip(rows, parsed):
        rid, source, role, provider, line1, line2, rcity, rstate, rzip, last_line, label_number = r
        have = set(present.get(role or "", ()))
        st = norm(rstate) if rstate else (a.state or "" if a is not None and last_line else "")
        ss = by_key.setdefault((st, source or "", role or "", provider or ""), Counter())
        ss["rows"] += 1
        if last_line:
            ss["last_line_rows"] += 1
        mism = []
        codes = []
        if a is None:
            ss["no_result"] += 1
            mism.append("no_result")
        else:
            codes = list(a.warnings)
            if "label_number" in have:
                # A fraction alone in line 2 belongs to the house number (`123` + `1/2`).
                src_number = f"{label_number} {line2}" if FRACTION.fullmatch((line2 or "").strip()) else label_number
                if compact(src_number) != compact(a.street_number):
                    mism.append("number")
            if "state" in have and norm(rstate) != (a.state or ""):
                mism.append("state")
            if "zip" in have:
                if (rzip or "")[:5] != (a.zip5 or ""):
                    mism.append("zip5")
                p4 = plus4_of(rzip)
                if p4 and p4 != (a.zip4 or ""):
                    mism.append("zip4")
            if "city" in have and compact(rcity) != compact(a.city):
                mism.append("city")
            # Only where the source says its line 2 is a unit: elsewhere it holds attention lines,
            # building names and care-of text, and "has a line 2 but no unit" is no mismatch.
            if "label_unit" in have and bool(line2) != bool(a.unit_type or a.unit_number):
                mism.append("unit")
            if not street_ok(line1, line2, label_number if "label_number" in have else a.street_number, a):
                mism.append("street")
            if last_line and crossed_boundary(last_line, a):
                ss["last_line_crossed"] += 1
                mism.append("boundary")
            place = a.place["name"] if a.place else ""
            triples[(st, (rzip or "")[:5] if rzip else (a.zip5 or ""),
                     norm(rcity) if rcity else norm(a.city), source or "", role or "",
                     provider or "", place)] += 1
        if codes:
            ss["with_warnings"] += 1
            for c in codes:
                warns[(st, source or "", role or "", provider or "", c)] += 1
        for m in mism:
            ss["m_" + m] += 1
        if codes or mism:
            ss["flagged"] += 1
            flagged.append((rid, st, source or "", role or "", provider or "", ",".join(codes),
                            ",".join(mism), a))
    return by_key, warns, triples, flagged


def write_parquet(path, table):
    import pyarrow.parquet as pq

    tmp = path.with_suffix(".tmp")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


def write_chunk(run, cid, by_key, warns, triples, flagged):
    import pyarrow as pa

    s = pa.string()
    fields = ["rows", "with_warnings", "no_result", "flagged", "m_number", "m_state", "m_zip5",
              "m_zip4", "m_city", "m_unit", "m_street", "last_line_rows", "last_line_crossed",
              "m_boundary"]
    keys = sorted(by_key)
    names = ["state", "source", "role", "provider"]
    write_parquet(run / "agg_state_source" / f"{cid:06d}.parquet", pa.table(
        {**{n: pa.array([k[i] for k in keys], s) for i, n in enumerate(names)},
         **{f: pa.array([by_key[k][f] for k in keys], pa.int64()) for f in fields}}))
    wk = sorted(warns)
    write_parquet(run / "agg_warnings" / f"{cid:06d}.parquet", pa.table(
        {**{n: pa.array([k[i] for k in wk], s) for i, n in enumerate(names)},
         "code": pa.array([k[4] for k in wk], s), "n": pa.array([warns[k] for k in wk], pa.int64())}))
    tk = sorted(triples)
    write_parquet(run / "agg_triples" / f"{cid:06d}.parquet", pa.table(
        {"state": pa.array([k[0] for k in tk], s), "zip5": pa.array([k[1] for k in tk], s),
         "city": pa.array([k[2] for k in tk], s), "source": pa.array([k[3] for k in tk], s),
         "role": pa.array([k[4] for k in tk], s), "provider": pa.array([k[5] for k in tk], s),
         "place": pa.array([k[6] for k in tk], s), "n": pa.array([triples[k] for k in tk], pa.int64())}))
    cols = {k: [] for k in ["record_id", "state", "source", "role", "provider", "warnings",
                            "mismatches", "address_type", "key", "street_number",
                            "street_dir_prefix", "street_name", "street_suffix",
                            "street_dir_suffix", "unit_type", "unit_number", "city", "zip5",
                            "zip4", "unparsed", "place"]}
    for rid, st, source, role, provider, w, m, a in flagged:
        cols["record_id"].append(rid)
        cols["state"].append(st)
        cols["source"].append(source)
        cols["role"].append(role)
        cols["provider"].append(provider)
        cols["warnings"].append(w)
        cols["mismatches"].append(m)
        for k in ("address_type", "key"):
            cols[k].append(getattr(a, k)() if a is not None else None)
        for k in ("street_number", "street_dir_prefix", "street_name", "street_suffix",
                  "street_dir_suffix", "unit_type", "unit_number", "city", "zip5", "zip4",
                  "unparsed"):
            cols[k].append(getattr(a, k) if a is not None else None)
        cols["place"].append(a.place["name"] if a is not None and a.place else None)
    write_parquet(run / "flagged" / f"{cid:06d}.parquet",
                  pa.table({k: pa.array(v, s) for k, v in cols.items()}))


def run_chunk(run, args, lo, cid, ctx):
    clo = lo + cid * args.chunk_rowids
    chi = clo + args.chunk_rowids
    t0 = time.time()
    try:
        rows = ctx["fetch"](ctx["con"], args, clo, chi)
        by_key, warns, triples, flagged = process_chunk(
            rows, ctx["present"], ctx["fields_many"], ctx["parse_many"])
        write_chunk(run, cid, by_key, warns, triples, flagged)
    except Exception as e:  # DuckDB and SQLite messages can quote rows (docs/data-policy.md)
        raise RuntimeError(f"chunk {cid} failed: {type(e).__name__}") from None
    info = {"chunk": cid, "rowid_lo": clo, "rowid_hi": chi, "rows": len(rows),
            "flagged": len(flagged), "seconds": round(time.time() - t0, 2)}
    (run / "chunk_status" / f"{cid:06d}.json").write_text(json.dumps(info) + "\n")
    return info


def make_ctx(args, present):
    from doorplate import parse_fields_many, parse_many

    if args.input:
        import duckdb

        con, fetch = duckdb.connect(), fetch_records
    else:
        con, fetch = open_db(args.db), fetch_sqlite
    return {"con": con, "fetch": fetch, "present": present,
            "fields_many": parse_fields_many, "parse_many": parse_many}


_STATE = {}


def _worker_init(argv, run, lo, threads):
    os.environ["RAYON_NUM_THREADS"] = str(threads)
    args = parse_args(argv)
    present = json.loads((Path(run) / "manifest.json").read_text())["input"]["fields_present"]
    _STATE.update(args=args, run=Path(run), lo=lo, ctx=make_ctx(args, present))


def _worker_task(cid):
    st = _STATE
    return run_chunk(st["run"], st["args"], st["lo"], cid, st["ctx"])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    threads = args.threads or max(1, (os.cpu_count() or 1) // args.workers)
    os.environ["RAYON_NUM_THREADS"] = str(threads)
    path = input_path(args)
    if not path.exists():
        sys.exit(f"{path} not found (run the extraction or tools/ingest/ingest.py first)")
    lo, hi, present = inspect(args)
    p = plan(args, lo, hi)
    commit = git("rev-parse", "--short", "HEAD") or "nogit"
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + commit
    run = args.out_root / run_id
    print(f"""plan
  input         {path}{'' if args.input else f' (table {args.table}, country {args.country})'}
  {'rows' if args.input else 'rowid'} range   {lo} .. {hi}  ->  {p['chunks']} chunk(s) of {args.chunk_rowids} {'rows' if args.input else 'rowids'}
  roles         {', '.join(f"{r or '(none)'} [{' '.join(c)}]" for r, c in sorted(present.items()))}
  run directory {run}
  disk          {p['used_gb']:.1f} GB used by the input folder and runs; budget {args.budget_gb} GB;
                {p['free_gb']:.0f} GB free (refuses below {args.min_free_gb} GB)
  workers       {args.workers} process(es), {threads} Rust thread(s) each
  commit        {commit}{' (dirty tree)' if git('status', '--porcelain') else ''}""")
    if not args.confirm:
        print("\nDry run. Nothing was written. Re-run with --confirm to start.")
        return 0
    if p["free_gb"] < args.min_free_gb:
        sys.exit("not enough free disk")
    if p["used_gb"] > args.budget_gb:
        sys.exit("already over the disk budget")

    from doorplate import __version__

    for d in ("agg_state_source", "agg_warnings", "agg_triples", "flagged", "chunk_status"):
        (run / d).mkdir(parents=True, exist_ok=True)
    manifest_path = run / "manifest.json"
    if not manifest_path.exists():
        manifest = {
            "schema_version": SCHEMA_VERSION, "run_id": run_id, "started": datetime.now(timezone.utc).isoformat(),
            "git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
            "doorplate_version": __version__, "data_tables_sha256": data_hash(),
            "input": {"kind": "records" if args.input else "netsyms-sqlite", "path": str(path),
                      "table": None if args.input else args.table,
                      "country": None if args.input else args.country,
                      "rowid_min": lo, "rowid_max": hi, "fields_present": present,
                      **fingerprint(path, args.full_hash)},
            "options": {"chunk_rowids": args.chunk_rowids, "threads": args.threads,
                        "limit_chunks": args.limit_chunks, "mode": "parse_fields_many (rows with last_line: parse_many)",
                        "budget_gb": args.budget_gb},
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        shutil.copy(HERE / "SCHEMA.md", run / "SCHEMA.md")
        (run / "README_RUN.md").write_text(readme_run(manifest))
    log = open(run / "progress.log", "a", buffering=1)

    def say(msg):
        line = f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        log.write(line + "\n")

    todo = [cid for cid in range(p["chunks"]) if not (run / "chunk_status" / f"{cid:06d}.json").exists()]
    skipped = p["chunks"] - len(todo)
    done_n = 0
    t_start = time.time()
    n_chunks = p["chunks"]
    folder = path.parent
    stop = {"over_budget": False}

    def finished(info):
        nonlocal done_n
        done_n += 1
        say(f"chunk {info['chunk'] + 1}/{n_chunks} rowids {info['rowid_lo']}-{info['rowid_hi']} "
            f"rows {info['rows']} flagged {info['flagged']} {info['seconds']}s")
        used = dir_size(folder) + dir_size(args.out_root)
        if used / GB > args.budget_gb:
            stop["over_budget"] = True
            say(f"stopping: {used / GB:.1f} GB exceeds the {args.budget_gb} GB budget; "
                f"resume with --run-id {run_id}")

    try:
        if args.workers <= 1 or len(todo) <= 1:
            ctx = make_ctx(args, present)
            for cid in todo:
                finished(run_chunk(run, args, lo, cid, ctx))
                if stop["over_budget"]:
                    return 3
        else:
            import multiprocessing as mp
            from concurrent.futures import ProcessPoolExecutor, as_completed

            ctx = mp.get_context("spawn")
            with ProcessPoolExecutor(args.workers, mp_context=ctx, initializer=_worker_init,
                                     initargs=(argv, str(run), lo, threads)) as pool:
                futures = []
                for cid in todo:
                    futures.append(pool.submit(_worker_task, cid))
                for fut in as_completed(futures):
                    finished(fut.result())
                    if stop["over_budget"]:
                        for f in futures:
                            f.cancel()
                        return 3
    except KeyboardInterrupt:
        say(f"interrupted; resume with --run-id {run_id}")
        return 130
    finished = sorted((run / "chunk_status").glob("*.json"))
    all_info = [json.loads(f.read_text()) for f in finished]
    totals = {"chunks": len(all_info), "rows": sum(i["rows"] for i in all_info),
              "flagged": sum(i["flagged"] for i in all_info),
              "seconds_this_session": round(time.time() - t_start, 1), "skipped_resumed": skipped}
    if len(all_info) == p["chunks_all"]:
        (run / "DONE").write_text(json.dumps(totals, indent=2) + "\n")
        say(f"done: {totals}")
    elif len(all_info) == n_chunks:
        # --limit-chunks: a test slice, never a whole run.
        (run / "LIMITED").write_text(json.dumps(totals, indent=2) + "\n")
        say(f"limited run finished (not the whole database): {totals}")
    else:
        say(f"stopped early after {done_n} chunk(s): {totals}")
    return 0


def readme_run(manifest):
    return f"""# Run {manifest['run_id']}

A doorplate parse of an address source (tools/harness/run.py). **Private: do not commit anything in this folder**
(docs/data-policy.md). Only aggregate numbers leave it.

- `manifest.json`: what was run (commit, doorplate version, data hash, input fingerprint, options).
- `SCHEMA.md`: every artifact's columns and the comparison rules.
- `chunk_status/NNNNNN.json`: one per finished chunk. `DONE` exists only when every chunk of the
  whole database finished (`LIMITED` marks a test slice).
- `agg_state_source/`, `agg_warnings/`, `agg_triples/`, `flagged/`: Parquet, one file per chunk.
- `progress.log`: one line per chunk.

Open with DuckDB (offline):

    import duckdb
    duckdb.sql("select * from read_parquet('agg_state_source/*.parquet') limit 5").show()

Then: `python tools/harness/analyze.py {manifest['run_id']}` from the repository root.
To continue an interrupted run, repeat the original command with `--run-id {manifest['run_id']}`.
"""


if __name__ == "__main__":
    sys.exit(main())
