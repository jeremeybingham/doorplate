#!/usr/bin/env python3
"""Hard-stratum quotas from the step 2 inventory (#75): writes tools/benchsuite/hard_classes.json.

    python tools/benchsuite/allocate.py [--inventory local-data/benchsuite/inventory.json]

Every class above 1 in 10,000 records (the two libraries' counts added) gets a floor of 50; the rest of the
3,000 is shared in proportion to the classes above the floor, working again until none falls under it.
Building-name classes are left out (docs/benchmark-suite.md, decision 2). Prints the table of the spec.
"""
import argparse
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, default=ROOT / "local-data" / "benchsuite" / "inventory.json")
    ap.add_argument("--total", type=int, default=3000)
    ap.add_argument("--floor", type=int, default=50)
    args = ap.parse_args()
    r = json.loads(args.inventory.read_text())
    n = r["records"]
    w = collections.defaultdict(lambda: {"doorplate": 0, "usaddress": 0})
    for lib, d in r["libraries"].items():
        for c, v in d["classes"].items():
            if v["per_10k"] >= 1 and not c.startswith("BuildingName"):
                w[c][lib] += v["records"]
    rows = sorted(((c, x["doorplate"], x["usaddress"], sum(x.values())) for c, x in w.items()), key=lambda t: -t[3])
    fixed = set()
    while True:
        big = [t for t in rows if t[0] not in fixed]
        rest = args.total - args.floor * len(fixed)
        tot = sum(t[3] for t in big)
        new = {t[0] for t in big if rest * t[3] / tot < args.floor}
        if not new:
            break
        fixed |= new
    out = [{"class": t[0], "quota": args.floor if t[0] in fixed else round(rest * t[3] / tot),
            "doorplate_per_10k": round(t[1] / n * 1e4, 2), "usaddress_per_10k": round(t[2] / n * 1e4, 2)} for t in rows]
    out[0]["quota"] += args.total - sum(o["quota"] for o in out)
    (HERE / "hard_classes.json").write_text(json.dumps(
        {"about": "Hard-stratum classes and quotas from the step 2 inventory (docs/benchmark-suite.md, Step 2 results); "
                  "building names excluded", "records": n, "classes": out}, indent=1))
    for o in out:
        if o["quota"] > args.floor:
            print(f"| {o['class']} | {o['doorplate_per_10k']} | {o['usaddress_per_10k']} | {o['quota']} |")
    print(f"{len(out)} classes, {len(fixed)} at the floor ({len(fixed) * args.floor} records)")


if __name__ == "__main__":
    main()
