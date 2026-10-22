#!/usr/bin/env python3
"""Build the review queue: hard addresses from a harness run, one or two per failure shape (#122).

    python tools/review/sample.py RUN_ID_OR_PATH [--limit 150] [--per-shape 2] [--seed 7]
                                  [--source S] [--role R] [--out local-data/review/queue.jsonl] [--confirm]

Takes the rows a run flagged with a warning or an `unparsed` remainder, groups them by their
failure shape (the shape of the input lines and the warning codes, as tools/harness/shapes_report.py
does), and keeps `--per-shape` random rows from each of the biggest groups, so a review of
a hundred rows covers the biggest shapes instead of the same one many times. The first row of
every group comes before the second row of any. The seed makes the sample repeatable.

The rows are real addresses: the queue stays in `local-data/` (docs/data-policy.md). Without
`--confirm` it prints the plan (counts only) and exits.

It reads the harness runs of real sources only. It refuses the benchmark suite and the geocode
benchmark: docs/benchmark-suite.md says the suite is not a work list, and the geocode splits were
read while rules were written, so review answers on them would tune the parser to the score.
This library formats and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "harness"))

import shapes_report as sr  # noqa: E402  (open_run, connect, the shape macro)

DEFAULT_OUT = ROOT / "local-data" / "review" / "queue.jsonl"
# A run over any of these is a benchmark, not a source; see the docstring.
BENCHMARK_MARKERS = ("benchmarks/suite", "benchsuite", "geocode-benchmark", "geocode_benchmark")


def refuse_benchmarks(manifest):
    path = str(manifest["input"].get("path", "")).replace("\\", "/").lower()
    if any(m in path for m in BENCHMARK_MARKERS):
        sys.exit(f"{path} is a benchmark input. The review tool reads real sources only: the "
                 "benchmark suite is not a work list (docs/benchmark-suite.md).")


def build(con, args):
    """The sample as a list of dicts, biggest groups first."""
    where = ["(coalesce(f.warnings, '') <> '' or coalesce(f.unparsed, '') <> '')"]
    params = []
    if args.source:
        where.append("f.source = ?")
        params.append(args.source)
    if args.role:
        where.append("f.role = ?")
        params.append(args.role)
    sql = f"""
    with joined as (
      select f.source, f.role, f.provider, f.record_id, coalesce(f.warnings, '') as warnings,
             r.line1, r.line2, r.last_line, {sr.INPUT_SHAPE} as input_shape
      from flagged f join recs r
        on f.source = r.source and f.role = r.role and f.record_id = r.record_id
      where {' and '.join(where)}
      qualify row_number() over (partition by f.source, f.role, f.record_id order by r.line1) = 1
    ), ranked as (
      select *, count(*) over (partition by source, role, input_shape, warnings) as size,
             row_number() over (partition by source, role, input_shape, warnings
                                order by hash(record_id || '|' || ?)) as nth
      from joined
    )
    select source, role, provider, record_id, warnings, line1, line2, last_line, input_shape, size, nth
    from ranked where nth <= ? and size >= ?
    order by nth, size desc, input_shape, hash(record_id || '|' || ?)
    limit ?"""
    seed = str(args.seed)
    rows = con.execute(sql, params + [seed, args.per_shape, args.min_cluster, seed, args.limit]).fetchall()
    cols = ["source", "role", "provider", "record_id", "warnings", "line1", "line2", "last_line",
            "input_shape", "size", "nth"]
    return [dict(zip(cols, r)) for r in rows]


def entry(seq, r):
    """One queue line. Empty fields are left out; `id` names the record across runs."""
    e = {"seq": seq, "id": f"{r['source']}|{r['role']}|{r['record_id']}",
         "source": r["source"], "role": r["role"], "record_id": r["record_id"]}
    for k in ("provider", "line1", "line2", "last_line"):
        if r[k]:
            e[k] = r[k]
    e["cluster"] = {"shape": sr.clip(r["input_shape"]), "warnings": r["warnings"], "size": r["size"]}
    return e


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="run id (under local-data/netsyms-runs/) or a path")
    ap.add_argument("--limit", type=int, default=150, help="rows in the queue (default 150)")
    ap.add_argument("--per-shape", type=int, default=2, help="rows kept from each shape group (default 2)")
    ap.add_argument("--min-cluster", type=int, default=1, help="skip groups smaller than this (default 1)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--source", help="only this source")
    ap.add_argument("--role", help="only this role")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--confirm", action="store_true", help="write the queue (without it: the plan only)")
    args = ap.parse_args(argv)

    run, manifest = sr.open_run(args.run, partial=False)
    refuse_benchmarks(manifest)
    con, has_text = sr.connect(run, manifest)
    if not has_text:
        sys.exit("this run has no records file to join (a --db run); the review needs the input text. "
                 "Rerun it with `run.py --input records.parquet`.")
    try:
        rows = build(con, args)
    except Exception as e:  # DuckDB's messages can quote rows (docs/data-policy.md)
        sys.exit(f"failed: {type(e).__name__}")
    groups = {(r["source"], r["role"], r["input_shape"], r["warnings"]) for r in rows}
    print(f"run {run.name}: {len(rows)} row(s) from {len(groups)} shape group(s), "
          f"up to {args.per_shape} per group, seed {args.seed}")
    print(f"queue: {args.out}")
    if not args.confirm:
        print("plan only; pass --confirm to write it")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            f.write(json.dumps(entry(i, r), ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
