#!/usr/bin/env python3
"""The deletion check for tagger call sites (#401): switch each one off alone and see what changes.

    cargo build --release -p doorplate --features rule-stats,corpus --example rule_disable
    python tools/rules/disable_check.py INPUTS [--sites rules.rs:179,rules.rs:2041 | all]

For each site (default `all`: every `.set(`, `.warn(` and `.decide(` call of the tagger) it runs the
`rule_disable` example with `DOORPLATE_DISABLE` naming the site, and compares with a run that
disables nothing: the golden-corpus cases of `passing.txt` that now fail, and the INPUTS whose key,
warnings or unparsed text change. A site with no regression and no change on public inputs is a
candidate for removal (then check it against the real rows: `rule_stats.py` says how often it fires
there). INPUTS is one input per line, a one-line address or five tab-separated fields; use public
inputs (the suite's, the corpus's). Prints counts and corpus case ids.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXE = ROOT / "target/release/examples/rule_disable"


def run(inputs, sites):
    env = dict(os.environ)
    if sites:
        env["DOORPLATE_DISABLE"] = sites
    out = subprocess.run(
        [str(EXE), inputs], capture_output=True, text=True, env=env, check=True
    ).stdout.splitlines()
    head = out[0].split("\t")
    regressed = head[2].split() if len(head) > 2 else []
    return regressed, out[1:]


def all_sites():
    sys.path.insert(0, str(Path(__file__).parent))
    import rule_stats

    return {
        f"{kind}\t{site}": text
        for kind, sites in rule_stats.static_sites().items()
        for site, text in sites.items()
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs")
    ap.add_argument("--sites", default="all")
    args = ap.parse_args()
    if not EXE.exists():
        sys.exit("build the rule_disable example first (see the docstring)")
    base_reg, base = run(args.inputs, "")
    print(f"baseline: {len(base_reg)} regressed corpus cases, {len(base)} inputs")
    if args.sites == "all":
        sites = list(all_sites())
    else:
        sites = [f"?\t{s}" for s in args.sites.split(",")]
    for entry in sites:
        kind, site = entry.split("\t")
        reg, out = run(args.inputs, site)
        changed = sum(1 for a, b in zip(base, out, strict=True) if a != b)
        new_reg = sorted(set(reg) - set(base_reg))
        verdict = "no change" if not new_reg and not changed else ""
        print(
            f"{kind:6s} {site:16s} corpus +{len(new_reg):<3d} inputs changed {changed:<5d} {verdict}"
            + (f" {' '.join(new_reg[:6])}" if new_reg else "")
        )


if __name__ == "__main__":
    main()
