#!/usr/bin/env python3
"""Report rule firing counts (#401): which tagger call sites and tokenizer rules fire, and which never did.

    cargo run --release -p doorplate --features rule-stats --example rule_stats -- INPUTS > run1.tsv
    python tools/rules/rule_stats.py run1.tsv [run2.tsv ...] [--rare N]

Each TSV is the output of the `rule_stats` example (one input per line in INPUTS; counts only).
The report merges the runs and scans `crates/doorplate/src/tagger/` for every `.set(`, `.warn(` and
`.decide(` call, so a call site that never fired in any run is listed by file and line: a candidate
for the deletion check of #401 (disable it alone, then run the corpus and the key diff). It also
lists the sites that fired in at most --rare inputs (default 5). Prints counts and source lines
only; no input text is ever in the files.
"""

import argparse
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "crates" / "doorplate" / "src" / "tagger"
KINDS = {"set": r"\.set\(", "warn": r"\.warn\(", "decide": r"\.decide\("}


def load(paths):
    rows, parses = {}, 0
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.startswith("# parses"):
                parses += int(line.split("\t")[1])
                continue
            kind, site, label, fires, inputs = line.split("\t")
            f, i = rows.get((kind, site, label), (0, 0))
            rows[(kind, site, label)] = (f + int(fires), i + int(inputs))
    return rows, parses


def static_sites():
    out = {k: {} for k in KINDS}
    for fn in sorted(SRC.glob("*.rs")):
        for n, text in enumerate(fn.read_text().splitlines(), 1):
            if re.search(r"\bfn (set|warn|decide)\b|hint_used\.set", text):
                continue
            for kind, pat in KINDS.items():
                if re.search(pat, text):
                    out[kind][f"{fn.name}:{n}"] = text.strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv", nargs="+")
    ap.add_argument("--rare", type=int, default=5)
    args = ap.parse_args()
    rows, parses = load(args.tsv)
    static = static_sites()
    print(f"parses: {parses:,}")
    for kind, sites in static.items():
        fired = {s for (k, s, _) in rows if k == kind}
        never = [s for s in sites if s not in fired]
        print(
            f"\n{kind}: {len(sites)} call sites, {len(fired & set(sites))} fired, {len(never)} never"
        )
        for s in sorted(never, key=lambda x: (x.split(":")[0], int(x.split(":")[1]))):
            print(f"  never  {s}  {sites[s][:90]}")
    print("\ntokenizer rules that fired:")
    for (k, s, _), (f, i) in sorted(rows.items()):
        if k == "tok":
            print(f"  {s}: {f:,} fires in {i:,} inputs")
    print(f"\nsites that fired in at most {args.rare} inputs:")
    rare = sorted(
        (
            (i, f, k, s, lab)
            for (k, s, lab), (f, i) in rows.items()
            if k != "tok" and i <= args.rare
        )
    )
    for i, f, k, s, lab in rare:
        print(f"  {k:6s} {s:16s} {lab:24s} {f:,} fires in {i:,} inputs")


if __name__ == "__main__":
    sys.exit(main())
