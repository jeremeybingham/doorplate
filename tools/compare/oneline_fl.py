#!/usr/bin/env python3
"""Render structured Florida records as one line with no commas and score the city.

    python tools/compare/oneline_fl.py [--n 300000] [--binary target/release/doorplate]

Reads `local-data/florida-dbpr/normalized.parquet` (private, see docs/data-policy.md), renders each
record as `<street> <city> FL <zip>`, parses it with the CLI and compares the parsed city with the
true city field. Reports city accuracy overall and for the two risky subsets: a true city that
starts with a compass word (`NORTH MIAMI`) and a line 1 that ends in a spelled-out compass word
(`5TH AVE NORTH`). The geocode benchmark spells postdirectionals abbreviated, so it cannot test
the second: a rule tuned on it alone broke these (#29). Prints counts only, never a record.
This library formats and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import json
import random
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPASS = "NORTH|SOUTH|EAST|WEST|NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n", type=int, default=300_000)
    ap.add_argument("--binary", type=Path, default=ROOT / "target" / "release" / "doorplate")
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()
    import duckdb
    rows = duckdb.connect().execute(f"""select distinct upper(trim(s1)), upper(trim(city)), substr(trim(zip),1,5)
        from '{ROOT}/local-data/florida-dbpr/normalized.parquet'
        where upper(trim(state))='FL' and regexp_matches(trim(zip),'^\\d{{5}}') and trim(city)<>''
        and s1 not ilike '%private%' and regexp_matches(trim(s1),'^\\d')
        and not regexp_matches(upper(trim(s1)),'(^| )(APT|UNIT|STE|SUITE|BLDG|#)')""").fetchall()
    # `select distinct` has no order, so sort first: the same seed then picks the same records on every run
    # and every build can be compared (an unsorted sample moved the scores by 0.1 point on its own).
    rows.sort()
    random.Random(args.seed).shuffle(rows)
    rows = rows[: args.n]
    lines = [f"{s1} {city} FL {z}" for s1, city, z in rows]
    out = subprocess.run([str(args.binary), "parse", "-"], input="\n".join(lines) + "\n",
                         capture_output=True, text=True).stdout.splitlines()
    parsed = [json.loads(x)["components"] if x.startswith("{") else {} for x in out]
    norm = lambda s: re.sub(r"[^A-Z0-9 ]", "", (s or "").upper().replace("ST.", "SAINT")).strip()
    ok = lambda a, truth: norm(a.get("city", "")) == norm(truth).replace("ST ", "SAINT ")
    subsets = (
        ("all", lambda r: True),
        ("true city starts with a compass word", lambda r: bool(re.match(rf"({COMPASS})\b", r[1]))),
        ("line 1 ends in a spelled-out compass word", lambda r: bool(re.search(rf" ({COMPASS})$", r[0]))),
    )
    print(f"{len(rows):,} Florida records, one line, no commas ({args.binary.name})")
    for label, sel in subsets:
        idx = [i for i, r in enumerate(rows) if sel(r)]
        k = sum(ok(parsed[i], rows[i][1]) for i in idx)
        print(f"  {label:44s} {len(idx):>8,} records, city right {100 * k / max(len(idx), 1):5.1f}%")


if __name__ == "__main__":
    main()
