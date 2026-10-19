#!/usr/bin/env python3
"""Parse the US rows of the Netsyms address database with doorplate and store
artifacts for later analysis. Offline, resumable, nothing is committed.

    python tools/netsyms/run.py --db local-data/netsyms-2026/sample.sqlite --table sample
    python tools/netsyms/run.py --db ... --table addresses --confirm

Without `--confirm` it only prints the plan (input, rowid range, chunks, paths,
disk budget) and exits. With it, it writes a run directory under
`local-data/netsyms-runs/<run-id>/` (see tools/netsyms/README.md and SCHEMA.md).

The database stays in `local-data/` and is never copied into the repository. See
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
SCHEMA_VERSION = 2
REQUIRED = ["zipcode", "number", "street", "street2", "city", "state", "plus4", "country", "source"]
GB = 1 << 30


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", required=True, type=Path, help="the SQLite database")
    ap.add_argument("--table", default="addresses", help="table name (the sample uses 'sample')")
    ap.add_argument("--country", default="US", help="only rows with this country (default US)")
    ap.add_argument("--out-root", type=Path, default=ROOT / "local-data" / "netsyms-runs")
    ap.add_argument("--run-id", help="resume or name a run (default: UTC time + commit)")
    ap.add_argument("--chunk-rowids", type=int, default=200_000, help="rowids per chunk")
    ap.add_argument("--limit-chunks", type=int, help="stop after this many chunks (tests)")
    ap.add_argument("--threads", type=int, help="Rust parse threads per worker (default: cores / workers)")
    ap.add_argument("--workers", type=int, default=max(1, min(6, (os.cpu_count() or 2) // 2)),
                    help="processes working on different chunks (default: half the cores, at most 6)")
    ap.add_argument("--budget-gb", type=float, default=60.0,
                    help="abort when the database's folder (not counting .7z archives) plus all runs exceed this (default 60)")
    ap.add_argument("--min-free-gb", type=float, default=20.0, help="refuse to start below this")
    ap.add_argument("--full-hash", action="store_true", help="SHA-256 the whole database (slow)")
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


def inspect(args):
    con = open_db(args.db)
    cols = [r[1] for r in con.execute(f"pragma table_info({args.table})")]
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        sys.exit(f"table {args.table!r} lacks columns {missing}; has {cols}")
    lo, hi = con.execute(f"select min(rowid), max(rowid) from {args.table}").fetchone()
    con.close()
    return lo, hi


def plan(args, lo, hi):
    chunks_all = (hi - lo) // args.chunk_rowids + 1
    chunks = min(chunks_all, args.limit_chunks) if args.limit_chunks else chunks_all
    folder = args.db.parent
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


def street_ok(street, street2, number, a):
    """True when every word of the source street is accounted for in the parse (as a street
    part, unit, building, attention or unparsed text) and every parsed street word came from
    the source street, its second line or the number field (junk in the number field, such as
    `NULL`, is flagged by the `number` mismatch, not here). Spelled-out suffixes and standardized highway
    names are equal, so only real changes to the street remain."""
    src = words(street)
    parts = [a.street_dir_prefix, a.street_name, a.street_suffix, a.street_dir_suffix]
    if a.highway:
        parts.append(a.highway["name"])
    parsed = words(" ".join(p for p in parts if p))
    elsewhere = words(" ".join(x for x in (
        a.unit_type, a.unit_number, a.second_unit_type, a.second_unit_number, a.unparsed,
        a.building, a.attention, a.po_box) if x))
    return not (src - (parsed + elsewhere)) and not (parsed - (src + words(street2) + words(number)))


def process_chunk(con, args, lo, hi, fields_many):
    cur = con.execute(
        f"select rowid, number, street, street2, city, state, zipcode, plus4, source "
        f"from {args.table} where rowid >= ? and rowid < ? and country = ?",
        (lo, hi, args.country),
    )
    rows = cur.fetchall()
    line1 = [f"{r[1] or ''} {r[2] or ''}".strip() or None for r in rows]
    line2 = [(r[3] or None) for r in rows]
    city = [(r[4] or None) for r in rows]
    state = [(r[5] or None) for r in rows]
    zipc = [((r[6] or "") + (f"-{r[7]}" if r[7] else "")) or None for r in rows]
    parsed = fields_many(line1=line1, line2=line2, city=city, state=state, zip=zipc)

    by_ss = {}
    warns = Counter()
    triples = Counter()
    flagged = []
    for r, a in zip(rows, parsed):
        rowid, number, street, street2, rcity, rstate, rzip, rplus4, source = r
        st = rstate or ""
        ss = by_ss.setdefault((st, source or ""), Counter())
        ss["rows"] += 1
        mism = []
        codes = []
        if a is None:
            ss["no_result"] += 1
            mism.append("no_result")
        else:
            codes = list(a.warnings)
            # A fraction alone in street2 belongs to the house number (`123` + `1/2`).
            src_number = f"{number} {street2}" if FRACTION.fullmatch((street2 or "").strip()) else number
            if compact(src_number) != compact(a.street_number):
                mism.append("number")
            if norm(rstate) != (a.state or ""):
                mism.append("state")
            if (rzip or "")[:5] != (a.zip5 or ""):
                mism.append("zip5")
            if rplus4 and rplus4 != (a.zip4 or ""):
                mism.append("zip4")
            if compact(rcity) != compact(a.city):
                mism.append("city")
            if bool(street2) != bool(a.unit_type or a.unit_number):
                mism.append("unit")
            if not street_ok(street, street2, number, a):
                mism.append("street")
            place = a.place["name"] if a.place else ""
            triples[(st, (rzip or "")[:5], norm(rcity), source or "", place)] += 1
        if codes:
            ss["with_warnings"] += 1
            for c in codes:
                warns[(st, source or "", c)] += 1
        for m in mism:
            ss["m_" + m] += 1
        if codes or mism:
            ss["flagged"] += 1
            flagged.append((rowid, st, source or "", ",".join(codes), ",".join(mism), a))
    return rows, by_ss, warns, triples, flagged


def write_parquet(path, table):
    import pyarrow.parquet as pq

    tmp = path.with_suffix(".tmp")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


def write_chunk(run, cid, by_ss, warns, triples, flagged):
    import pyarrow as pa

    s = pa.string()
    fields = ["rows", "with_warnings", "no_result", "flagged", "m_number", "m_state", "m_zip5",
              "m_zip4", "m_city", "m_unit", "m_street"]
    keys = sorted(by_ss)
    write_parquet(run / "agg_state_source" / f"{cid:06d}.parquet", pa.table(
        {"state": pa.array([k[0] for k in keys], s), "source": pa.array([k[1] for k in keys], s),
         **{f: pa.array([by_ss[k][f] for k in keys], pa.int64()) for f in fields}}))
    wk = sorted(warns)
    write_parquet(run / "agg_warnings" / f"{cid:06d}.parquet", pa.table(
        {"state": pa.array([k[0] for k in wk], s), "source": pa.array([k[1] for k in wk], s),
         "code": pa.array([k[2] for k in wk], s), "n": pa.array([warns[k] for k in wk], pa.int64())}))
    tk = sorted(triples)
    write_parquet(run / "agg_triples" / f"{cid:06d}.parquet", pa.table(
        {"state": pa.array([k[0] for k in tk], s), "zip5": pa.array([k[1] for k in tk], s),
         "city": pa.array([k[2] for k in tk], s), "source": pa.array([k[3] for k in tk], s),
         "place": pa.array([k[4] for k in tk], s), "n": pa.array([triples[k] for k in tk], pa.int64())}))
    cols = {k: [] for k in ["rowid", "state", "source", "warnings", "mismatches", "address_type",
                            "key", "street_number", "street_dir_prefix", "street_name",
                            "street_suffix", "street_dir_suffix", "unit_type", "unit_number",
                            "city", "zip5", "zip4", "unparsed", "place"]}
    for rowid, st, source, w, m, a in flagged:
        cols["rowid"].append(rowid)
        cols["state"].append(st)
        cols["source"].append(source)
        cols["warnings"].append(w)
        cols["mismatches"].append(m)
        for k in ("address_type", "key"):
            cols[k].append(getattr(a, k)() if a is not None else None)
        for k in ("street_number", "street_dir_prefix", "street_name", "street_suffix",
                  "street_dir_suffix", "unit_type", "unit_number", "city", "zip5", "zip4",
                  "unparsed"):
            cols[k].append(getattr(a, k) if a is not None else None)
        cols["place"].append(a.place["name"] if a is not None and a.place else None)
    arrays = {k: pa.array(v, pa.int64() if k == "rowid" else s) for k, v in cols.items()}
    write_parquet(run / "flagged" / f"{cid:06d}.parquet", pa.table(arrays))


def run_chunk(run, args, lo, cid, con, fields_many):
    clo = lo + cid * args.chunk_rowids
    chi = clo + args.chunk_rowids
    t0 = time.time()
    rows, by_ss, warns, triples, flagged = process_chunk(con, args, clo, chi, fields_many)
    write_chunk(run, cid, by_ss, warns, triples, flagged)
    info = {"chunk": cid, "rowid_lo": clo, "rowid_hi": chi, "rows": len(rows),
            "flagged": len(flagged), "seconds": round(time.time() - t0, 2)}
    (run / "chunk_status" / f"{cid:06d}.json").write_text(json.dumps(info) + "\n")
    return info


_STATE = {}


def _worker_init(argv, run, lo, threads):
    os.environ["RAYON_NUM_THREADS"] = str(threads)
    from doorplate import parse_fields_many

    args = parse_args(argv)
    _STATE.update(args=args, run=Path(run), lo=lo, fields_many=parse_fields_many,
                  con=open_db(args.db))


def _worker_task(cid):
    st = _STATE
    return run_chunk(st["run"], st["args"], st["lo"], cid, st["con"], st["fields_many"])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    threads = args.threads or max(1, (os.cpu_count() or 1) // args.workers)
    os.environ["RAYON_NUM_THREADS"] = str(threads)
    if not args.db.exists():
        sys.exit(f"{args.db} not found (run the extraction first)")
    lo, hi = inspect(args)
    p = plan(args, lo, hi)
    commit = git("rev-parse", "--short", "HEAD") or "nogit"
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + commit
    run = args.out_root / run_id
    print(f"""plan
  database      {args.db} (table {args.table}, country {args.country})
  rowid range   {lo} .. {hi}  ->  {p['chunks']} chunk(s) of {args.chunk_rowids} rowids
  run directory {run}
  disk          {p['used_gb']:.1f} GB used by the database folder and runs; budget {args.budget_gb} GB;
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

    from doorplate import __version__, parse_fields_many

    for d in ("agg_state_source", "agg_warnings", "agg_triples", "flagged", "chunk_status"):
        (run / d).mkdir(parents=True, exist_ok=True)
    manifest_path = run / "manifest.json"
    if not manifest_path.exists():
        manifest = {
            "schema_version": SCHEMA_VERSION, "run_id": run_id, "started": datetime.now(timezone.utc).isoformat(),
            "git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
            "doorplate_version": __version__, "data_tables_sha256": data_hash(),
            "input": {"path": str(args.db), "table": args.table, "country": args.country,
                      "rowid_min": lo, "rowid_max": hi, **fingerprint(args.db, args.full_hash)},
            "options": {"chunk_rowids": args.chunk_rowids, "threads": args.threads,
                        "limit_chunks": args.limit_chunks, "mode": "parse_fields_many",
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
    folder = args.db.parent
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
            con = open_db(args.db)
            for cid in todo:
                finished(run_chunk(run, args, lo, cid, con, parse_fields_many))
                if stop["over_budget"]:
                    return 3
            con.close()
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

A doorplate parse of Netsyms rows. **Private: do not commit anything in this folder**
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

Then: `python tools/netsyms/analyze.py {manifest['run_id']}` from the repository root.
To continue an interrupted run, repeat the original command with `--run-id {manifest['run_id']}`.
"""


if __name__ == "__main__":
    sys.exit(main())
