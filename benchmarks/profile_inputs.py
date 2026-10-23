#!/usr/bin/env python3
"""Plain input files for profiling (#90), made from the benchmark suite (public data).

    python benchmarks/profile_inputs.py OUTDIR

Writes one input per line: `mix.txt` (the first input form of every record, a realistic mix),
one file per address type (street, po_box, highway, military, rural, general_delivery), `form1.txt`
to `form3.txt` (the other input forms of each record: no commas, mixed case, ...), and `fields.csv` (pre-split fields,
for the command-line run). Reads `benchmarks/suite/v1/doorplate.jsonl.gz`.
"""
import csv
import gzip
import json
import sys
from pathlib import Path

SUITE = Path(__file__).parent / "suite" / "v1" / "doorplate.jsonl.gz"


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    mix, by, fields = [], {}, []
    with gzip.open(SUITE, "rt") as f:
        for line in f:
            r = json.loads(line)
            if not r.get("inputs"):
                continue
            text = r["inputs"][0]
            mix.append(text)
            by.setdefault(r["type"], []).append(text)
            for i, other in enumerate(r["inputs"][1:4], 1):
                by.setdefault(f"form{i}", []).append(other)
            fl = r["fields"]
            if fl:
                fields.append([fl.get(k) or "" for k in ("line1", "line2", "city", "state", "zip")])
    (out / "mix.txt").write_text("\n".join(mix) + "\n")
    for k, v in by.items():
        (out / f"{k}.txt").write_text("\n".join(v) + "\n")
    with open(out / "fields.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line1", "line2", "city", "state", "zip"])
        w.writerows(fields)
    print(f"mix {len(mix)} lines; {', '.join(f'{k} {len(v)}' for k, v in sorted(by.items()))}; fields {len(fields)} rows")


if __name__ == "__main__":
    main()
