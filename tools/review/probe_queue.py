#!/usr/bin/env python3
"""Build one comparison queue per probe from the matches an unsampled probe scan kept (#465, the precision step).

    python tools/review/probe_queue.py SCAN_DIR INPUTS.txt --probe NAME [--probe NAME ...] [--n 50] [--seed 1]
                          [--max-source-share 0.4] [--exclude-answers 'local-data/review/answers*.jsonl']
                          [--out-dir local-data/review/probe-queues] [--confirm]

`SCAN_DIR` is a run of `tools/harness/probe_scan.py` and `INPUTS.txt` the list file that run used (the chunk files are
numbered by the position of the input in that list). The scan keeps the identity of each match, not its text; this tool
reads the text back from the input by `record_id` (a records file, the raw NAD file by file row number, the Netsyms
SQLite database by rowid) and builds the cards of `compare_sample.py`, so the queue opens in `tools/review/server.py`.

For each probe it takes the matches in the order of the scan's seeded hash `rk` (a random order, so the sample is a
random draw of the matches), in turns across the sources (the same number of turns for each, whatever its size), with no source above `--max-source-share` of the queue: a
large source such as Netsyms or NAD otherwise fills a queue and says nothing of the others. Each card names its
source, so a precision can be weighted back. A row is skipped when its string repeats one already taken, when a
previous review already holds its id (`--exclude-answers`), and when it looks like Puerto Rico (the Puerto Rico epic,
#332, has its own queue). The class of a card (silent, give-up, control) is the one of `compare_sample.py`; rows where
usaddress agrees are kept, since a precision needs them.

The queues are real addresses: they stay under `local-data/` (docs/data-policy.md). Counts only on stdout; an error
prints its type only. Without `--confirm` it prints the plan (matches per probe and source) and exits. This library
formats and parses; it does not validate that an address exists or can receive mail.
"""

import argparse
import collections
import glob
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "compare"))
sys.path.insert(0, str(ROOT / "tools" / "harness"))

import compare_sample as cs
import probe_scan
import probes


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("scan_dir", type=Path)
    ap.add_argument("inputs", type=Path, help="the list file the scan was run with")
    ap.add_argument("--probe", action="append", required=True, help="a probe key (repeat for several)")
    ap.add_argument("--n", type=int, default=50, help="cards per queue")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-source-share", type=float, default=0.4)
    ap.add_argument("--exclude-answers", default="local-data/review/answers*.jsonl")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "local-data" / "review" / "probe-queues")
    ap.add_argument("--confirm", action="store_true")
    return ap.parse_args(argv)


def answered_ids(pattern):
    ids = set()
    for fn in glob.glob(str(ROOT / pattern) if not Path(pattern).is_absolute() else pattern):
        for line in Path(fn).read_text(encoding="utf-8").splitlines():
            try:
                ids.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                pass
    return ids


def candidates(con, scan_dir, probe, take):
    """The `take` matches of a probe with the lowest rk in each source: (input index, source, role, record_id, rk, flagged)."""
    sql = (
        "select * from (select cast(regexp_extract(filename, '/([0-9]+)-[0-9]+[.]parquet$', 1) as integer) as i, source, role, "
        "record_id, rk, flagged, row_number() over (partition by source order by rk) as r "
        "from read_parquet(?, filename = true) where probe = ?) where r <= ? order by rk"
    )
    return [row[:6] for row in con.execute(sql, [str(scan_dir / "hits" / "*.parquet"), probe, take]).fetchall()]


def totals(con, scan_dir, probe):
    sql = "select source, sum(n) from read_parquet(?) where probe = ? and kind = 'rows' group by source"
    return dict(con.execute(sql, [str(scan_dir / "counts" / "*.parquet"), probe]).fetchall())


def read_back(con, inp, ids):
    """The rows of one input by record_id, as dicts with the keys of `probe_scan.ROW_COLS`."""
    if not ids:
        return []
    cols = probe_scan.ROW_COLS
    if inp["kind"] == "netsyms":
        db = sqlite3.connect(Path(inp["path"]).resolve().as_uri() + "?mode=ro", uri=True)
        rows = [r for rid in ids for r in probe_scan.fetch(db, inp, int(rid), int(rid) + 1)]
        db.close()
    elif inp["kind"] == "nad":
        rows = []
        want = sorted({int(i) for i in ids})
        for k in range(0, len(want), 200):
            where = "(" + ",".join(str(i) for i in want[k : k + 200]) + ")"
            sql = (
                "select cast(file_row_number as varchar), 'nad-raw', 'address', "
                "nullif(concat_ws(' ', nullif(trim(AddNo_Full), ''), nullif(trim(StNam_Full), '')), ''), "
                "SubAddress, Post_City, State, Zip_Code, NULL "
                f"from read_parquet(?, file_row_number = true) where file_row_number in {where}"
            )
            rows += con.execute(sql, [inp["path"]]).fetchall()
    else:
        have = {r[0] for r in con.execute("describe select * from read_parquet(?)", [inp["path"]]).fetchall()}
        sel = ", ".join(c if c in have else f"NULL AS {c}" for c in cols)
        quoted = ",".join("'" + str(i).replace("'", "''") + "'" for i in ids)
        rows = con.execute(
            f"select {sel} from read_parquet(?) where cast(record_id as varchar) in ({quoted})", [inp["path"]]
        ).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def pick(cands, n, share):
    """Order the candidates (already by rk) in turns across the sources, none above `share` of n; what the cap leaves out
    follows in rk order, so a queue with few sources still fills."""
    cap = max(1, int(n * share))
    queues = collections.defaultdict(list)
    for c in cands:
        queues[c[1]].append(c)
    order, used = [], collections.Counter()
    live = dict(queues)
    while live:
        for src in sorted(live, key=lambda s: (used[s], s)):
            if used[src] >= cap or not live[src]:
                live.pop(src)
                continue
            order.append(live[src].pop(0))
            used[src] += 1
    taken = {id(c) for c in order}
    return order + [c for c in cands if id(c) not in taken]


def main(argv=None):
    args = parse_args(argv)
    import duckdb

    inputs = probe_scan.read_inputs(args.inputs)
    for inp in inputs:
        inp["kind"] = probe_scan.kind_of(inp)
    known = {p[0] for p in probes.PROBES}
    bad = [p for p in args.probe if p not in known]
    if bad:
        sys.exit(f"unknown probe(s): {', '.join(bad)}")
    con = duckdb.connect()
    skip = answered_ids(args.exclude_answers)
    plan = []
    for probe in args.probe:
        tot = totals(con, args.scan_dir, probe)
        plan.append((probe, tot))
        print(f"{probe:<28} matches {sum(tot.values()):>10,}  " + " ".join(f"{k}:{int(v):,}" for k, v in sorted(tot.items())))
    if not args.confirm:
        print("\nDry run. Nothing was written. Re-run with --confirm to build the queues.")
        return 0
    import doorplate
    import usaddress

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for probe, tot in plan:
        total = int(sum(tot.values()))
        cands = candidates(con, args.scan_dir, probe, max(args.n * 3, 100))
        by_input = collections.defaultdict(list)
        for c in cands:
            by_input[c[0]].append(c[3])
        rows = {}
        for idx, ids in by_input.items():
            try:
                for r in read_back(con, inputs[idx], ids):
                    rows[(inputs[idx]["kind"], idx, str(r["record_id"]))] = r
            except Exception as e:  # noqa: BLE001  (the type only: a reader error can quote a row)
                sys.exit(f"{probe}: reading input {idx} failed: {type(e).__name__}")
        queue, seen = [], set()
        for c in pick(cands, args.n, args.max_source_share):
            if len(queue) >= args.n:
                break
            r = rows.get((inputs[c[0]]["kind"], c[0], str(c[3])))
            if r is None or probes.is_puerto_rico(r):
                continue
            s = cs.one_line(r)
            key = " ".join(s.lower().split())
            if not key or key in seen or f"cmp|{r['source']}|{r['role']}|{r['record_id']}" in skip:
                continue
            seen.add(key)
            res = cs.compare_string(s, doorplate, usaddress)
            if res is None:
                res = {"class": "control", "differs": [], "theirs": [list(t) for t in usaddress.parse(s)],
                       "warnings": list(doorplate.parse(s).warnings)}
            queue.append(cs.entry(len(queue) + 1, {"row": r, "result": res, "class": res["class"],
                                                  "sig": f"probe {probe}", "size": total}))
        by_src = collections.Counter(q["source"] for q in queue)
        by_cls = collections.Counter(q["compare"]["class"] for q in queue)
        agree = sum(1 for q in queue if not q["compare"]["differs"])
        out = args.out_dir / f"queue-{probe}.jsonl"
        out.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in queue) + ("\n" if queue else ""), encoding="utf-8")
        print(f"{probe:<28} {len(queue):>3} cards  {dict(by_cls)}  agree {agree}  sources {dict(by_src)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
