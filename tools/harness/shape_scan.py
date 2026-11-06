#!/usr/bin/env python3
"""The leftover-shape scan: parse every row of whole sources and tabulate what the parser leaves behind (#524).

    python tools/harness/shape_scan.py INPUTS.txt [--run-id NAME] [--limit-chunks 1] [--confirm]
    python tools/harness/shape_scan.py --summary local-data/shape-scan/NAME [--top 40]

The probe scan counts shapes somebody thought of. This one needs no idea in advance: it parses all rows (the same inputs file
and chunking as `probe_scan.py`) and counts, for every row that carries one of the failure warnings, the SHAPE of its input and
of what was left over, per source and state. A shape turns each number into `9`, each word that is not a Pub 28 word into `a`
and keeps the words of the lexicon tables (suffixes, unit designators, directionals, special lines), so `816 SLADE ST` over
`3 RIGHT` is `9 a ST | 9 a` and `STAR RT BOX 12` is `STAR RT BOX 9`. A name or a street never appears: only its form.

Warnings counted: unparsed_remainder (with the shape of the leftover), missing_street_number, missing_street_name,
missing_unit_number, possibly_truncated, multiple_addresses, ambiguous_street_number, second_line_in_street. A row with no
warning is counted only in the `__rows__` total. A run directory `local-data/shape-scan/<run-id>/` holds `counts/*.parquet`
(one file per chunk: `source, state, code, input_shape, leftover_shape, n`), `chunk_status/`, `progress.log`, `status.json`,
`summary.json` and `DONE`. Resume with the same `--run-id`. No row text is written; an error prints the exception type only
(docs/data-policy.md). Without `--confirm` it prints the plan. This library formats and parses; it does not validate that an
address exists or can receive mail.
"""

import argparse
import concurrent.futures as cf
import json
import multiprocessing
import os
import re
import signal
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import probe_scan as ps

CODES = (
    "unparsed_remainder",
    "missing_street_number",
    "missing_street_name",
    "missing_unit_number",
    "possibly_truncated",
    "multiple_addresses",
    "ambiguous_street_number",
    "second_line_in_street",
)
ALL_ROWS = "__rows__"
MAX_SHAPE = 56
DATA = ROOT / "crates" / "doorplate" / "data"


def vocabulary():
    """The words of the lexicon tables: the only letters a shape keeps."""
    words = set()
    for name in ("suffixes.toml", "units.toml", "directionals.toml", "special.toml"):
        for m in re.finditer(r'"([A-Z][A-Z0-9 .\'/-]*)"', (DATA / name).read_text()):
            for w in re.split(r"[ ./-]+", m.group(1)):
                if 2 <= len(w) <= 12 and w.isalpha():
                    words.add(w)
    words -= {"AND", "THE", "OF", "OLD", "NEW", "BAY", "KEY", "CAMP", "PARK", "SIDE", "FARM", "LAKE", "RIVER", "CITY"}
    return words


def shape_of(text, vocab):
    if not text:
        return ""
    out = []
    for tok in re.findall(r"[A-Za-z]+|[0-9]+|#|&|/|-|\(|\)|%", text.upper()):
        if tok.isdigit():
            out.append("9")
        elif tok.isalpha():
            out.append(tok if tok in vocab else "a")
        else:
            out.append(tok)
    s = " ".join(out)
    s = re.sub(r"(?:\ba\b ?){2,}", "a ", s)  # a run of unknown words is one `a`
    s = re.sub(r"(?:9 ?){2,}", "9 ", s).strip()
    return s[:MAX_SHAPE]


_STATE = {}


def _worker_init(run, inputs):
    import duckdb
    from doorplate import parse_fields_many, parse_many

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    con = duckdb.connect()
    con.execute("set threads = 1")
    _STATE.update(run=Path(run), inputs=inputs, duck=con, sqlite={}, vocab=vocabulary(),
                  fields_many=parse_fields_many, parse_many=parse_many)


def scan_chunk(rows, vocab, fields_many, parse_many):
    counts = Counter()
    parsed = ps.parse_matches(rows, fields_many, parse_many)
    for r, a in zip(rows, parsed):
        source, state = r[1] or "", (r[6] or "").upper().strip()
        counts[(source, state, ALL_ROWS, "", "")] += 1
        if a is None:
            continue
        codes = [c for c in CODES if c in a.warnings]
        if not codes:
            continue
        ish = shape_of(r[3], vocab) + (" | " + shape_of(r[4], vocab) if r[4] else "")
        for c in codes:
            left = shape_of(a.unparsed, vocab) if c == "unparsed_remainder" else ""
            counts[(source, state, c, ish, left)] += 1
    return counts


def _worker_task(task):
    i, cid, lo, hi = task
    st = _STATE
    inp = st["inputs"][i]
    tag = f"{i:02d}-{cid:05d}"
    t0 = time.time()
    try:
        if inp["kind"] == "netsyms":
            con = st["sqlite"].get(i) or st["sqlite"].setdefault(
                i, sqlite3.connect(Path(inp["path"]).resolve().as_uri() + "?mode=ro", uri=True))
        else:
            con = st["duck"]
        rows = ps.fetch(con, inp, lo, hi)
        counts = scan_chunk(rows, st["vocab"], st["fields_many"], st["parse_many"])
        ck = sorted(counts.items())
        ps.write_parquet(st["run"] / "counts" / f"{tag}.parquet",
                         [[k[0][j] for k in ck] for j in range(5)] + [[k[1] for k in ck]],
                         ["source", "state", "code", "input_shape", "leftover_shape", "n"])
        status = {"input": i, "chunk": cid, "lo": lo, "hi": hi, "rows": len(rows), "keys": len(ck),
                  "seconds": round(time.time() - t0, 2), "error": None}
    except Exception as e:  # noqa: BLE001  (the type only: a reader error can quote a row)
        status = {"input": i, "chunk": cid, "lo": lo, "hi": hi, "rows": 0, "keys": 0,
                  "seconds": round(time.time() - t0, 2), "error": type(e).__name__}
    if status["error"] is None:
        (st["run"] / "chunk_status" / f"{tag}.json").write_text(json.dumps(status))
    return status


def summarize(run, top=40):
    import duckdb

    con = duckdb.connect()
    files = str(Path(run) / "counts" / "*.parquet")
    total = con.execute(f"select sum(n) from read_parquet('{files}') where code = '{ALL_ROWS}'").fetchone()[0] or 0
    by_code = con.execute(
        f"select code, sum(n) from read_parquet('{files}') where code <> '{ALL_ROWS}' group by 1 order by 2 desc").fetchall()
    shapes = {}
    for code in [c for c, _ in by_code]:
        rows = con.execute(
            f"select input_shape, leftover_shape, sum(n) n, "
            f"string_agg(source || ':' || n, ' ' order by n desc) from "
            f"(select input_shape, leftover_shape, source, sum(n) n from read_parquet('{files}') where code = ? "
            f"group by all) group by input_shape, leftover_shape order by n desc limit {top}", [code]).fetchall()
        shapes[code] = [{"input": r[0], "leftover": r[1], "n": int(r[2]), "sources": r[3][:140]} for r in rows]
    out = {"total_rows": int(total), "codes": {c: int(n) for c, n in by_code}, "top": shapes}
    (Path(run) / "summary.json").write_text(json.dumps(out, indent=1))
    return out


def print_summary(s, top=15):
    print(f"{s['total_rows']:,} rows")
    for c, n in s["codes"].items():
        print(f"  {c:<26}{n:>12,}  ({100 * n / max(1, s['total_rows']):.3f}%)")
    for c, rows in s["top"].items():
        print(f"\n{c}: top shapes (input | leftover, rows, biggest sources)")
        for r in rows[:top]:
            print(f"  {r['n']:>10,}  {r['input'] or '-'}  ||  {r['leftover'] or '-'}   [{r['sources'][:70]}]")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inputs", nargs="?", type=Path)
    ap.add_argument("--summary", type=Path)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--out-root", type=Path, default=ROOT / "local-data" / "shape-scan")
    ap.add_argument("--run-id")
    ap.add_argument("--chunk-rows", type=int, default=250_000)
    ap.add_argument("--limit-chunks", type=int)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--min-free-gb", type=float, default=30.0)
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if args.summary:
        print_summary(summarize(args.summary, args.top))
        return 0
    if not args.inputs:
        sys.exit("give the list file of inputs (or --summary RUN)")
    inputs = ps.read_inputs(args.inputs)
    for inp in inputs:
        if not Path(inp["path"]).exists():
            sys.exit(f"{Path(inp['path']).name} not found")
        inp["kind"] = ps.kind_of(inp)
        inp["range"] = ps.count_rows(inp)
    tasks = ps.chunks_of(inputs, args.chunk_rows, args.limit_chunks)
    commit = ps.git("rev-parse", "--short", "HEAD") or "nogit"
    run_id = args.run_id or ps.now().strftime("%Y%m%dT%H%M%SZ") + "-" + commit
    run = args.out_root / run_id
    args.out_root.mkdir(parents=True, exist_ok=True)
    total = sum(hi - lo for _, _, lo, hi in tasks)
    print("plan")
    for i, inp in enumerate(inputs):
        n = sum(1 for t in tasks if t[0] == i)
        print(f"  input {i:02d}  {Path(inp['path']).name}  [{inp['kind']}]  {inp['range'][1] - inp['range'][0]:,} rows, {n} chunk(s)")
    print(f"  {len(tasks)} chunk(s) of {args.chunk_rows:,}, {total:,} rows; workers {args.workers}; run directory {run}")
    print(f"  disk {ps.free_gb(args.out_root):.0f} GB free; the counts are small (tens of MB)")
    if not args.confirm:
        print("\nDry run. Nothing was written.")
        return 0
    if ps.free_gb(args.out_root) < args.min_free_gb:
        sys.exit("not enough free disk")
    for d in ("counts", "chunk_status"):
        (run / d).mkdir(parents=True, exist_ok=True)
    (run / "manifest.json").write_text(json.dumps(
        {"run_id": run_id, "started": ps.now().isoformat(), "git_commit": ps.git("rev-parse", "HEAD"),
         "inputs": [Path(i["path"]).name for i in inputs], "chunk_rows": args.chunk_rows}, indent=1))
    done = {p.stem for p in (run / "chunk_status").glob("*.json")}
    todo = [t for t in tasks if f"{t[0]:02d}-{t[1]:05d}" not in done]
    log = open(run / "progress.log", "a")  # noqa: SIM115

    def say(msg):
        line = f"{ps.now().strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    stop = {"now": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(now=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
    say(f"start {len(todo)} chunk(s) to do, {len(tasks) - len(todo)} done already")
    t0 = time.time()
    errors = Counter()
    finished = rows_done = 0
    pending = iter(todo)
    with cf.ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("spawn"),
                                initializer=_worker_init, initargs=(str(run), inputs)) as pool:
        live = set()

        def top_up():
            while not stop["now"] and len(live) < args.workers * 2:
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
                eta = (len(todo) - finished) * (el / finished)
                pct = 100 * finished / len(todo)
                say(f"input {st['input']:02d} chunk {st['chunk']} {st['rows']:,} rows {st['seconds']}s"
                    f"{' ERROR ' + st['error'] if st['error'] else ''} | {finished}/{len(todo)} ({pct:.1f}%) "
                    f"{rows_done / el:,.0f} rows/s elapsed {ps.clock(el)} ETA {ps.clock(eta)}")
                print(f"##progress pct={pct:.1f} msg=\"{finished}/{len(todo)} chunks\"", flush=True)
                (run / "status.json").write_text(json.dumps(
                    {"chunks_done": finished, "chunks_todo": len(todo), "rows": rows_done, "elapsed_s": int(el),
                     "eta_s": int(eta), "errors": dict(errors)}))
            top_up()
    if stop["now"] or errors:
        say(f"stopped or errors {dict(errors)}; start again with the same --run-id to continue")
        return ps.EXIT_STOPPED
    summary = summarize(run, args.top)
    (run / "DONE").write_text(ps.now().isoformat())
    say(f"done: {summary['total_rows']:,} rows")
    print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
