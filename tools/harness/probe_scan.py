#!/usr/bin/env python3
"""The probe scan: count every backlog probe over whole sources, unsampled, and keep the identity of each match (#465).

    python tools/harness/probe_scan.py INPUTS.txt [--run-id NAME] [--limit-chunks 1] [--confirm]
    python tools/harness/probe_scan.py --summary local-data/probe-scan/NAME

`INPUTS.txt` has one input per line (blank lines and `#` comments are skipped), a path and optional `key=value` words:

    local-data/nc-voter-2026/records_current.parquet          # a records file (tools/ingest)
    local-data/nad-2026/nad_r24.parquet                       # the raw NAD file (StNam_Full, ...), mapped as in specs/nad.toml
    local-data/netsyms-2026/2026-05-dbfull.sqlite table=addresses country=US     # the Netsyms SQLite database

It does only the cheap part of a harness run: the regexes of `probes.py` over every row, plus one parser call for the rows that
match some probe, to say whether the parse is flagged. The parse of all rows is not needed to count shapes. A run directory
`local-data/probe-scan/<run-id>/` holds:

- `manifest.json`: the commit, the hash of `probes.py` (so the file says which patterns made the counts), the doorplate version,
  the inputs (size, mtime, rows), the options and the times;
- `counts/*.parquet`, one file per chunk: `source, role, state, probe, kind, n`, with `kind` in `rows`, `flagged`, `partial_key`;
  the probe `__rows__` counts all the rows of the chunk, so a share needs no second pass. Sum `n` across chunks;
- `hits/*.parquet`, one file per chunk: `source, role, record_id, state, probe, flagged, text_hash, rk`. No address text: the
  text is read back from the input by `record_id` when a review queue is built. Per probe and chunk at most `--hit-cap` matches
  are kept, the ones with the lowest `rk` (a seeded hash in [0, 1)), so a capped probe is still a random sample; the exact count
  stays in `counts/`;
- `chunk_status/*.json`, `progress.log`, `status.json` (rewritten after each chunk), `summary.json` and `DONE` on success.

Resume with the same `--run-id`: chunks with a status file are skipped. SIGINT or SIGTERM stops after the chunks in progress.
No row text is printed or written to a log; an error prints the exception type only (docs/data-policy.md).

Without `--confirm` it prints the plan (rows per input, chunks, disk, probe coverage) and exits. This library formats and
parses; it does not validate that an address exists or can receive mail.
"""

import argparse
import concurrent.futures as cf
import hashlib
import json
import multiprocessing
import os
import resource
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probes

GB = 1 << 30
ROW_COLS = ["record_id", "source", "role", "line1", "line2", "city", "state", "zip", "last_line"]
RARE = 20
ALL_ROWS = "__rows__"
EXIT_STOPPED = 3  # stopped by a signal or the disk floor, or some chunks failed: start again with the same --run-id


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inputs", nargs="?", type=Path, help="the list file, one input per line")
    ap.add_argument("--summary", type=Path, help="rebuild summary.json of this run directory and print it")
    ap.add_argument("--out-root", type=Path, default=ROOT / "local-data" / "probe-scan")
    ap.add_argument("--run-id", help="resume or name a run (default: UTC time + commit)")
    ap.add_argument("--chunk-rows", type=int, default=1_000_000, help="rows (rowids for SQLite) per chunk")
    ap.add_argument("--limit-chunks", type=int, help="stop after this many chunks per input (the smoke test)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--hit-cap", type=int, default=1000, help="matches kept per probe and chunk (0: counts only)")
    ap.add_argument("--seed", type=int, default=1, help="seed of the match order (rk)")
    ap.add_argument("--min-free-gb", type=float, default=50.0, help="refuse to start (and stop) below this")
    ap.add_argument("--skip-coverage", action="store_true", help="do not require probes.py --coverage to pass (tests)")
    ap.add_argument("--confirm", action="store_true", help="actually run (default: print the plan)")
    return ap.parse_args(argv)


def git(*cmd):
    try:
        return subprocess.run(["git", *cmd], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return ""


def now():
    return datetime.now(UTC)


def read_inputs(list_file):
    """[{path, kind, table, country}] from the list file; kind is decided by the file."""
    out = []
    for raw in Path(list_file).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        opts = dict(w.split("=", 1) for w in words[1:] if "=" in w)
        path = Path(words[0])
        if not path.is_absolute():
            path = ROOT / path
        out.append({"path": str(path), "table": opts.get("table", "addresses"), "country": opts.get("country", "US")})
    return out


def kind_of(inp):
    p = inp["path"]
    if p.endswith((".sqlite", ".db", ".sqlite3")):
        return "netsyms"
    import duckdb

    cols = {r[0] for r in duckdb.connect().execute("describe select * from read_parquet(?)", [p]).fetchall()}
    return "nad" if "StNam_Full" in cols else "records"


def count_rows(inp):
    """(first, one past the last) of the chunking range: file rows for a parquet file, rowids for SQLite."""
    if inp["kind"] == "netsyms":
        con = sqlite3.connect(Path(inp["path"]).resolve().as_uri() + "?mode=ro", uri=True)
        lo, hi = con.execute(f"select min(rowid), max(rowid) + 1 from {inp['table']}").fetchone()
        con.close()
        return lo or 0, hi or 0
    import duckdb

    n = duckdb.connect().execute("select count(*) from read_parquet(?)", [inp["path"]]).fetchone()[0]
    return 0, n


def chunks_of(inputs, size, limit):
    """[(input index, chunk id, lo, hi)] in file order; `limit` caps the chunks of each input."""
    out = []
    for i, inp in enumerate(inputs):
        lo, hi = inp["range"]
        starts = list(range(lo, hi, size))
        if limit:
            starts = starts[:limit]
        out += [(i, n, s, min(s + size, hi)) for n, s in enumerate(starts)]
    return out


def fetch(con, inp, lo, hi):
    """Rows of one chunk in the ROW_COLS shape."""
    if inp["kind"] == "netsyms":
        cur = con.execute(
            f"select rowid, number, street, street2, city, state, zipcode, plus4 from {inp['table']} "
            f"where rowid >= ? and rowid < ? and country = ?",
            (lo, hi, inp["country"]),
        )
        return [
            (
                str(r[0]), "netsyms", "address", f"{r[1] or ''} {r[2] or ''}".strip() or None, r[3] or None, r[4] or None,
                r[5] or None, ((r[6] or "") + (f"-{r[7]}" if r[7] else "")) or None, None,
            )
            for r in cur.fetchall()
        ]
    if inp["kind"] == "nad":
        # The mapping of tools/ingest/specs/nad.toml.
        sql = (
            "select cast(file_row_number as varchar), 'nad-raw', 'address', "
            "nullif(concat_ws(' ', nullif(trim(AddNo_Full), ''), nullif(trim(StNam_Full), '')), ''), "
            "SubAddress, Post_City, State, Zip_Code, NULL "
            "from read_parquet(?, file_row_number = true) where file_row_number >= ? and file_row_number < ?"
        )
        return con.execute(sql, [inp["path"], lo, hi]).fetchall()
    have = {r[0] for r in con.execute("describe select * from read_parquet(?)", [inp["path"]]).fetchall()}
    sel = ", ".join(c if c in have else f"NULL AS {c}" for c in ROW_COLS)
    return con.execute(
        f"select {sel} from read_parquet(?, file_row_number = true) where file_row_number >= ? and file_row_number < ?",
        [inp["path"], lo, hi],
    ).fetchall()


def rk_of(seed, source, rid, probe):
    """A seeded hash of a match in [0, 1): the order in which capped matches are kept."""
    h = hashlib.blake2b(f"{seed}|{source}|{rid}|{probe}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big") / 2**64


def text_hash(line1, line2):
    return hashlib.blake2b(probes.text_of(line1, line2).encode(), digest_size=8).hexdigest()


def parse_matches(rows, fields_many, parse_many):
    """Parse the matched rows: those with a last line as one joined string (as run.py does), the others from their fields."""
    out = [None] * len(rows)
    sep = [i for i, r in enumerate(rows) if not r[8]]
    joined = [i for i, r in enumerate(rows) if r[8]]
    if sep:
        res = fields_many(
            line1=[rows[i][3] for i in sep], line2=[rows[i][4] for i in sep], city=[rows[i][5] for i in sep],
            state=[rows[i][6] for i in sep], zip=[rows[i][7] for i in sep],
        )
        for i, a in zip(sep, res):
            out[i] = a
    if joined:
        res = parse_many([", ".join(x for x in (rows[i][3], rows[i][4], rows[i][8]) if x) for i in joined])
        for i, a in zip(joined, res):
            out[i] = a
    return out


def scan_rows(rows, fields_many, parse_many, hit_cap, seed):
    """(counts, hits) for a chunk of rows. counts: Counter of (source, role, state, probe, kind) -> n;
    hits: list of (source, role, record_id, state, probe, flagged, text_hash, rk), at most `hit_cap` per probe."""
    counts = Counter()
    matched = []  # (row index, [probe keys])
    for i, r in enumerate(rows):
        rid, source, role, line1, line2, city, state, zip_code, _last = r
        st = (state or "").upper().strip()
        counts[(source or "", role or "", st, ALL_ROWS, "rows")] += 1
        ks = probes.hits(line1, line2, zip_code, city, state)
        if ks:
            matched.append((i, ks))
    parsed = parse_matches([rows[i] for i, _ in matched], fields_many, parse_many)
    per_probe = {}
    for (i, ks), a in zip(matched, parsed):
        rid, source, role, line1, line2, _city, state, _zip, _last = rows[i]
        st = (state or "").upper().strip()
        flagged = a is None or probes.is_flagged(a.warnings, a.key())
        partial = a is not None and probes.is_partial_key(a.key())
        for k in ks:
            counts[(source or "", role or "", st, k, "rows")] += 1
            if flagged:
                counts[(source or "", role or "", st, k, "flagged")] += 1
            if partial:
                counts[(source or "", role or "", st, k, "partial_key")] += 1
            if hit_cap:
                per_probe.setdefault(k, []).append(
                    (source or "", role or "", str(rid), st, k, bool(flagged), text_hash(line1, line2),
                     rk_of(seed, source, rid, k))
                )
    hits = []
    for k in sorted(per_probe):
        kept = sorted(per_probe[k], key=lambda h: h[7])[:hit_cap]
        hits += kept
    return counts, hits


def write_parquet(path, columns, names):
    import pyarrow as pa
    import pyarrow.parquet as pq

    tmp = path.with_suffix(".tmp")
    table = pa.table({n: c for n, c in zip(names, columns)})
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


def write_chunk(run, tag, counts, hits):
    ck = sorted(counts.items())
    write_parquet(
        run / "counts" / f"{tag}.parquet",
        [[k[0][i] for k in ck] for i in range(5)] + [[k[1] for k in ck]],
        ["source", "role", "state", "probe", "kind", "n"],
    )
    names = ["source", "role", "record_id", "state", "probe", "flagged", "text_hash", "rk"]
    write_parquet(run / "hits" / f"{tag}.parquet", [[h[i] for h in hits] for i in range(8)], names)


_STATE = {}


def _worker_init(run, inputs, hit_cap, seed):
    import duckdb
    from doorplate import parse_fields_many, parse_many

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    con = duckdb.connect()
    con.execute("set threads = 1")
    _STATE.update(run=Path(run), inputs=inputs, cap=hit_cap, seed=seed, duck=con, sqlite={},
                  fields_many=parse_fields_many, parse_many=parse_many)


def _worker_task(task):
    i, cid, lo, hi = task
    st = _STATE
    inp = st["inputs"][i]
    tag = f"{i:02d}-{cid:05d}"
    t0 = time.time()
    try:
        if inp["kind"] == "netsyms":
            con = st["sqlite"].get(i) or st["sqlite"].setdefault(
                i, sqlite3.connect(Path(inp["path"]).resolve().as_uri() + "?mode=ro", uri=True)
            )
        else:
            con = st["duck"]
        rows = fetch(con, inp, lo, hi)
        counts, hits = scan_rows(rows, st["fields_many"], st["parse_many"], st["cap"], st["seed"])
        write_chunk(st["run"], tag, counts, hits)
        status = {"input": i, "chunk": cid, "lo": lo, "hi": hi, "rows": len(rows), "hits": len(hits),
                  "seconds": round(time.time() - t0, 2), "error": None}
    except Exception as e:  # noqa: BLE001  (the type only, not the message: a reader error can quote a row)
        status = {"input": i, "chunk": cid, "lo": lo, "hi": hi, "rows": 0, "hits": 0,
                  "seconds": round(time.time() - t0, 2), "error": type(e).__name__}
    if status["error"] is None:
        (st["run"] / "chunk_status" / f"{tag}.json").write_text(json.dumps(status))
    return status


def registry_hash():
    return hashlib.sha256((HERE / "probes.py").read_bytes()).hexdigest()


def rss_gb():
    return resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / (1 << 20)


def free_gb(path):
    return shutil.disk_usage(path).free / GB


def clock(sec):
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def summarize(run):
    """summary.json: totals per probe and source, and the rare probes. Counts only."""
    import duckdb

    con = duckdb.connect()
    files = str(Path(run) / "counts" / "*.parquet")
    rows = con.execute(
        f"select probe, source, kind, sum(n) from read_parquet('{files}') group by all order by probe, source, kind"
    ).fetchall()
    totals = {}
    for probe, source, kind, n in rows:
        totals.setdefault(probe, {}).setdefault(source, {})[kind] = int(n)
    allrows = {s: v.get("rows", 0) for s, v in totals.get(ALL_ROWS, {}).items()}
    per_probe = {p: sum(v.get("rows", 0) for v in d.values()) for p, d in totals.items() if p != ALL_ROWS}
    summary = {
        "sampled": False,
        "rows_by_source": allrows,
        "total_rows": sum(allrows.values()),
        "probes": {p: d for p, d in totals.items() if p != ALL_ROWS},
        "probe_rows": per_probe,
        "rare": sorted(k for k in (p[0] for p in probes.PROBES) if per_probe.get(k, 0) < RARE),
    }
    (Path(run) / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    return summary


def print_summary(summary):
    print(f"rows {summary['total_rows']:,}")
    for p, n in sorted(summary["probe_rows"].items(), key=lambda kv: -kv[1]):
        print(f"  {n:>12,}  {p}")
    if summary["rare"]:
        print(f"below {RARE} rows: {', '.join(summary['rare'])}")


def coverage_ok():
    out = subprocess.run(
        [sys.executable, "-I", str(HERE / "probes.py"), "--coverage"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return out.returncode == 0, (out.stdout.splitlines() or [""])[0]


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.summary:
        print_summary(summarize(args.summary))
        return 0
    if not args.inputs:
        sys.exit("give the list file of inputs (or --summary RUN)")
    inputs = read_inputs(args.inputs)
    for inp in inputs:
        if not Path(inp["path"]).exists():
            sys.exit(f"{Path(inp['path']).name} not found")
        inp["kind"] = kind_of(inp)
        inp["range"] = count_rows(inp)
    tasks = chunks_of(inputs, args.chunk_rows, args.limit_chunks)
    commit = git("rev-parse", "--short", "HEAD") or "nogit"
    run_id = args.run_id or now().strftime("%Y%m%dT%H%M%SZ") + "-" + commit
    run = args.out_root / run_id
    args.out_root.mkdir(parents=True, exist_ok=True)
    free = free_gb(args.out_root)
    ok, cov = (True, "skipped") if args.skip_coverage else coverage_ok()
    total_rows = sum(hi - lo for _, _, lo, hi in tasks)
    print("plan")
    for i, inp in enumerate(inputs):
        n = sum(1 for t in tasks if t[0] == i)
        print(f"  input {i:02d}  {Path(inp['path']).name}  [{inp['kind']}]  {inp['range'][1] - inp['range'][0]:,} rows, {n} chunk(s)")
    print(f"  chunk size    {args.chunk_rows:,}; {len(tasks)} chunk(s), {total_rows:,} rows (ids for SQLite) in this run")
    print(f"  run directory {run}")
    print(f"  workers       {args.workers}; hit cap {args.hit_cap} per probe and chunk; seed {args.seed}")
    print(f"  disk          {free:.0f} GB free (refuses below {args.min_free_gb:g} GB); hits/ is the large part, under 2 GB expected")
    print(f"  probes        {len(probes.PROBES)} in the registry (sha256 {registry_hash()[:12]}); coverage: {'ok' if ok else 'FAILS'} ({cov})")
    print(f"  commit        {commit}{' (dirty tree)' if git('status', '--porcelain') else ''}")
    if not args.confirm:
        print("\nDry run. Nothing was written. Run a smoke test (--limit-chunks 1 --confirm) for an ETA, then the full run.")
        return 0
    if not ok:
        sys.exit("probes.py --coverage fails: every open rule issue needs a probe or a reason before the scan")
    if free < args.min_free_gb:
        sys.exit("not enough free disk")

    from doorplate import __version__

    for d in ("counts", "hits", "chunk_status"):
        (run / d).mkdir(parents=True, exist_ok=True)
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if manifest and manifest.get("probes_sha256") != registry_hash():
        sys.exit("probes.py changed since this run started: start a new run id (the counts must come from one set of patterns)")
    manifest = manifest or {
        "run_id": run_id, "started": now().isoformat(), "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")), "doorplate_version": __version__, "probes_sha256": registry_hash(),
        "probes": [p[0] for p in probes.PROBES],
        "inputs": [
            {"name": Path(i["path"]).name, "kind": i["kind"], "bytes": Path(i["path"]).stat().st_size,
             "mtime": int(Path(i["path"]).stat().st_mtime), "range": list(i["range"])}
            for i in inputs
        ],
        "options": {"chunk_rows": args.chunk_rows, "limit_chunks": args.limit_chunks, "hit_cap": args.hit_cap, "seed": args.seed},
    }
    manifest_path.write_text(json.dumps(manifest, indent=1))
    done = {p.stem for p in (run / "chunk_status").glob("*.json")}
    todo = [t for t in tasks if f"{t[0]:02d}-{t[1]:05d}" not in done]
    log = open(run / "progress.log", "a")  # noqa: SIM115  (open for the whole run)

    def say(msg):
        line = f"{now().strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    stop = {"now": False}

    def on_signal(signum, _frame):
        stop["now"] = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    say(f"start {len(todo)} chunk(s) to do, {len(tasks) - len(todo)} done already")
    t0 = time.time()
    rows_done = sum(json.loads((run / "chunk_status" / f"{t}.json").read_text())["rows"] for t in done) if done else 0
    errors = Counter()
    finished = 0
    pending = iter(todo)
    window = args.workers * 2
    # spawn, not fork: the parent has used DuckDB, whose threads do not survive a fork.
    with cf.ProcessPoolExecutor(
        max_workers=args.workers, mp_context=multiprocessing.get_context("spawn"), initializer=_worker_init, initargs=(str(run), inputs, args.hit_cap, args.seed)
    ) as pool:
        live = set()
        last_beat = time.time()

        def top_up():
            while not stop["now"] and len(live) < window:
                t = next(pending, None)
                if t is None:
                    return
                live.add(pool.submit(_worker_task, t))

        top_up()
        while live:
            ready, live = cf.wait(live, timeout=60, return_when=cf.FIRST_COMPLETED)
            for fut in ready:
                st = fut.result()
                finished += 1
                rows_done += st["rows"]
                if st["error"]:
                    errors[st["error"]] += 1
                el = time.time() - t0
                rate = rows_done / el if el else 0
                pct = 100 * finished / len(todo)
                eta = (len(todo) - finished) * (el / finished)
                say(f"input {st['input']:02d} chunk {st['chunk']} {st['rows']:,} rows {st['seconds']}s"
                    f"{' ERROR ' + st['error'] if st['error'] else ''} | {finished}/{len(todo)} ({pct:.1f}%) "
                    f"{rate:,.0f} rows/s elapsed {clock(el)} ETA {clock(eta)}")
                (run / "status.json").write_text(json.dumps({
                    "chunks_done": finished, "chunks_todo": len(todo), "rows": rows_done, "elapsed_s": int(el),
                    "eta_s": int(eta), "errors": dict(errors), "updated": now().isoformat()}))
            if time.time() - last_beat >= 60:
                last_beat = time.time()
                say(f"heartbeat {finished}/{len(todo)} chunks, free disk {free_gb(args.out_root):.0f} GB, "
                    f"worker RSS max {rss_gb():.1f} GB")
                if free_gb(args.out_root) < args.min_free_gb:
                    stop["now"] = True
                    say("free disk below the floor: stopping after the chunks in progress")
            top_up()
    if stop["now"]:
        say("stopped; start again with the same --run-id to continue")
        return EXIT_STOPPED
    if errors:
        say(f"finished with errors {dict(errors)}; run again with the same --run-id to retry those chunks")
        return EXIT_STOPPED
    summary = summarize(run)
    manifest["finished"] = now().isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=1))
    (run / "DONE").write_text(now().isoformat())
    say(f"done: {summary['total_rows']:,} rows")
    print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
