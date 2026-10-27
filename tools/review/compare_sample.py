#!/usr/bin/env python3
"""Build the comparison queue: rows where doorplate and usaddress read the same string differently (#132).

    python tools/review/compare_sample.py RECORDS.parquet [--rows 200000] [--limit 150] [--seed 7]
                          [--source S] [--role R] [--provider P] [--out local-data/review/queue-compare.jsonl] [--confirm]

The v1 queue (sample.py) holds rows a harness run flagged. This one finds the rows where doorplate
may choose worse than usaddress. There is no ground truth on a real source, so it parses a random
sample of the source's rows (one line each, as run.py joins them) with both parsers, compares them
token by token on coarse labels (the rules of tools/compare/compare_usaddress.py and
docs/usaddress-compat.md: the street parts fold into one, `Subaddress*` is `Occupancy*`, and the labels
doorplate does not model, such as `Recipient` and `LandmarkName`, are not scored), and queues the
disagreements for a person to judge. Three classes, in this order:

- `silent`: doorplate raised no warning and left nothing unplaced, but usaddress reads a part
  differently. The riskiest, since nothing flags it. 70% of the queue by default (`--silent`).
- `giveup`: doorplate warned or left text unplaced, while usaddress produced a full-looking parse
  (a house number or box, a place and a state). 20% (`--giveup`).
- `control`: the rest of the disagreements. 10%.

Within a class the rows are grouped by the pair of labels that differ (doorplate `StreetName`,
usaddress `OccupancyIdentifier`), the biggest groups first, `--per-group` (default 2) rows each, the
first row of every group before the second row of any. A string that repeats one already seen is
skipped, and so is one listed in `--exclude-training FILE` (one lowercase, whitespace-collapsed
string per line: the strings of usaddress's training files, which it has seen).

The queue holds usaddress's parse of each row, so the review page needs no usaddress. It runs
usaddress (about 9,000 rows a second: 200,000 rows take about 25 seconds). Without `--confirm` it
prints the plan and exits. The rows are real addresses: the queue stays in `local-data/`
(docs/data-policy.md). It reads real sources only, never the benchmark suite, the geocode
benchmark or usaddress's own test files (docs/benchmark-suite.md: the suite is not a work list).
Disagreement finds where the parsers differ, not every place doorplate is wrong: a row both read
wrongly in the same way is not queued. This library formats and parses; it does not validate that an
address exists or can receive mail.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "compare"))

import compare_usaddress as cu  # noqa: E402  (byte_spans, overlap_label, coarse, OUT_OF_SCOPE, RAW_SAME)
from sample import BENCHMARK_MARKERS  # noqa: E402
from shape import shape  # noqa: E402

DEFAULT_OUT = ROOT / "local-data" / "review" / "queue-compare.jsonl"
FULL = ({"AddressNumber", "USPSBoxID"}, {"PlaceName"}, {"StateName"})
UNPLACED = "(unplaced)"


def one_line(r):
    """The row as one string, as the harness joins it: street lines, then the last line or city, state, ZIP."""
    if r.get("last_line"):
        parts = [r.get("line1"), r.get("line2"), r.get("last_line")]
    else:
        parts = [r.get("line1"), r.get("line2"), r.get("city"), " ".join(x for x in (r.get("state"), r.get("zip")) if x)]
    return ", ".join(" ".join(p.split()) for p in parts if p and p.strip())


def label_of(spans, predicted):
    """Coarse, comparable label of a token (None when unplaced)."""
    label = cu.overlap_label(spans, predicted)
    label = cu.RAW_SAME.get(label, label)
    return cu.coarse(cu.norm(label))


def spans_of(s, tokens):
    return [(sp[0], sp[1], l) for sp, (_, l) in zip(cu.byte_spans(s, [t for t, _ in tokens]), tokens) if sp]


def compare_string(s, doorplate, usaddress):
    """The disagreement of one string, or None when the parsers agree (or doorplate has no result).

    {"class", "differs": [[ours, theirs, n], ...], "theirs": [[token, label], ...], "warnings": [...]}"""
    try:
        ours = doorplate.parse_tokens(s)
        parsed = doorplate.parse(s)
    except doorplate.ParseError:
        return None
    try:
        theirs = usaddress.parse(s)
    except Exception:  # noqa: BLE001 (usaddress can raise on odd input)
        return None
    our_spans, their_spans = spans_of(s, ours), spans_of(s, theirs)
    diffs = collections.Counter()
    for (tok, gl), sp in zip(theirs, cu.byte_spans(s, [t for t, _ in theirs])):
        if sp is None or not cu.scored(tok) or gl in cu.OUT_OF_SCOPE:
            continue
        g, o = cu.coarse(cu.norm(cu.RAW_SAME.get(gl, gl))), label_of(sp, our_spans)
        if g != o:
            diffs[(o or UNPLACED, g)] += 1
    if not diffs:
        return None
    labels = {l for _, l in theirs}
    full = all(labels & group for group in FULL)
    warned = bool(parsed.warnings) or bool(parsed.unparsed)
    kind = "silent" if not warned else "giveup" if full else "control"
    return {"class": kind, "differs": [[o, g, n] for (o, g), n in diffs.most_common()],
            "theirs": [list(t) for t in theirs], "warnings": list(parsed.warnings)}


def signature(differs, top=3):
    return "; ".join(f"{o} / {g}" for o, g, _ in differs[:top])


def choose(found, limit, per_group, shares):
    """Pick the queue from `found` (dicts with class, sig, rid): quotas by class, biggest groups first,
    the first row of every group before the second row of any. Returns the rows, silent first."""
    quota = {"silent": int(limit * shares[0]), "giveup": int(limit * shares[1])}
    quota["control"] = limit - quota["silent"] - quota["giveup"]
    by_class = {k: collections.defaultdict(list) for k in quota}
    for f in found:
        by_class[f["class"]][f["sig"]].append(f)
    picked = {k: [] for k in quota}

    def take(kind, n):
        groups = sorted(by_class[kind].items(), key=lambda kv: (-len(kv[1]), kv[0]))
        for nth in range(per_group):
            for sig, rows in groups:
                if len(picked[kind]) >= n:
                    return
                if nth < len(rows) and rows[nth] not in picked[kind]:
                    picked[kind].append(rows[nth])

    for kind in quota:
        take(kind, quota[kind])
    spare = limit - sum(len(v) for v in picked.values())  # a class with too few rows gives its quota away
    for kind in ("silent", "giveup", "control"):
        if spare > 0:
            take(kind, len(picked[kind]) + spare)
            spare = limit - sum(len(v) for v in picked.values())
    rows = picked["silent"] + picked["giveup"] + picked["control"]
    for f in rows:
        f["size"] = len(by_class[f["class"]][f["sig"]])
    return rows


def read_rows(path, args):
    import duckdb

    con = duckdb.connect()
    have = {r[0] for r in con.execute("describe select * from read_parquet(?)", [str(path)]).fetchall()}
    cols = ", ".join(c if c in have else f"NULL AS {c}" for c in
                     ("source", "role", "record_id", "provider", "line1", "line2", "city", "state", "zip", "last_line"))
    where, params = [], [str(path)]
    for col, val in (("source", args.source), ("role", args.role), ("provider", args.provider)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    sql = (f"select * from (select {cols} from read_parquet(?)) "
           + (f"where {' and '.join(where)} " if where else "")
           + f"using sample reservoir({int(args.rows)} rows) repeatable ({int(args.seed)})")
    cur = con.execute(sql, params)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def entry(seq, f):
    r = f["row"]
    e = {"seq": seq, "id": f"cmp|{r['source']}|{r['role']}|{r['record_id']}", "source": r["source"], "role": r["role"],
         "record_id": r["record_id"]}
    for k in ("provider", "line1", "line2", "city", "state", "zip", "last_line"):
        if r.get(k):
            e[k] = r[k]
    e["cluster"] = {"shape": f["sig"], "warnings": ",".join(f["result"]["warnings"]), "size": f["size"]}
    e["compare"] = {"class": f["class"], "differs": f["result"]["differs"], "usaddress": f["result"]["theirs"]}
    return e


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("records", type=Path, help="a records.parquet of a real source (tools/ingest/)")
    ap.add_argument("--rows", type=int, default=200_000, help="rows to sample and parse (default 200,000)")
    ap.add_argument("--limit", type=int, default=150, help="rows in the queue (default 150)")
    ap.add_argument("--per-group", type=int, default=2, help="rows kept from each label-pair group (default 2)")
    ap.add_argument("--silent", type=float, default=0.7, help="share of the queue for silent disagreements (default 0.7)")
    ap.add_argument("--giveup", type=float, default=0.2, help="share for give-ups (default 0.2); the rest is control")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--source", help="only this source")
    ap.add_argument("--role", help="only this role")
    ap.add_argument("--provider", help="only this provider (FMCSA's country: US keeps the in-scope rows)")
    ap.add_argument("--exclude-training", type=Path, metavar="FILE",
                    help="strings usaddress was trained on (lowercase, whitespace collapsed, one per line)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--confirm", action="store_true", help="parse and write the queue (without it: the plan only)")
    args = ap.parse_args(argv)

    path = str(args.records).replace("\\", "/").lower()
    if any(m in path for m in BENCHMARK_MARKERS) or "tests/external/usaddress" in path:
        sys.exit(f"{args.records} is a benchmark or usaddress's own test data. The review tool reads real sources only "
                 "(docs/benchmark-suite.md).")
    if not args.records.exists():
        sys.exit(f"{args.records} not found (build it with tools/ingest/ingest.py)")
    if (ROOT / "local-data").resolve() not in args.out.resolve().parents:
        sys.exit(f"--out must be under {ROOT / 'local-data'}: the queue holds real addresses")
    if not 0 <= args.silent + args.giveup <= 1:
        sys.exit("--silent and --giveup are shares of the queue and must add up to at most 1")
    print(f"plan\n  records  {args.records}\n  sample   {args.rows:,} rows (seed {args.seed})"
          f"\n  queue    {args.limit} rows: {args.silent:.0%} silent, {args.giveup:.0%} give-ups, "
          f"{1 - args.silent - args.giveup:.0%} control, up to {args.per_group} per label-pair group\n  out      {args.out}")
    if not args.confirm:
        print("\nplan only; pass --confirm to parse the sample and write the queue")
        return 0
    try:
        import usaddress

        import doorplate
    except ImportError as e:
        sys.exit(f"needs doorplate and usaddress in this environment ({e.name}): uv pip install usaddress")
    skip = set()
    if args.exclude_training:
        skip = {l.rstrip("\n") for l in args.exclude_training.read_text(encoding="utf-8").splitlines() if l.strip()}
    try:
        rows = read_rows(args.records, args)
    except Exception as e:  # DuckDB's messages can quote rows (docs/data-policy.md)
        sys.exit(f"could not read {args.records}: {type(e).__name__}")
    seen, found, n_cmp, dropped = set(), [], 0, collections.Counter()
    for r in rows:
        s = one_line(r)
        key = " ".join(s.lower().split())
        if not key:
            continue
        if key in seen:
            dropped["repeated"] += 1
            continue
        seen.add(key)
        if key in skip:
            dropped["in usaddress's training files"] += 1
            continue
        n_cmp += 1
        res = compare_string(s, doorplate, usaddress)
        if res:
            found.append({"row": r, "result": res, "class": res["class"], "sig": signature(res["differs"])})
    counts = collections.Counter(f["class"] for f in found)
    print(f"compared {n_cmp:,} distinct strings ({', '.join(f'{v:,} {k}' for k, v in dropped.items()) or 'none dropped'}); "
          f"{len(found):,} disagree: " + ", ".join(f"{counts[k]:,} {k}" for k in ("silent", "giveup", "control")))
    picked = choose(found, args.limit, args.per_group, (args.silent, args.giveup))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for i, p in enumerate(picked, 1):
            f.write(json.dumps(entry(i, p), ensure_ascii=False) + "\n")
    groups = {(p["class"], p["sig"]) for p in picked}
    print(f"wrote {len(picked)} row(s) from {len(groups)} label-pair group(s) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
