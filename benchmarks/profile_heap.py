#!/usr/bin/env python3
"""Attribute allocations to the doorplate function that made them (#149).

    CARGO_PROFILE_RELEASE_STRIP=false CARGO_PROFILE_RELEASE_DEBUG=1 RUSTFLAGS="-C force-frame-pointers=yes" \\
        cargo build --release -p doorplate --example profile_loop --target-dir target/prof
    heaptrack -o ht target/prof/release/examples/profile_loop INPUT.txt 1
    heaptrack_print ht.zst -F ht.folded --flamegraph-cost-type allocations > /dev/null
    python benchmarks/profile_heap.py ht.folded PARSES [--top 25]

PARSES is the number of parses the run made (lines x 5 passes x REPS of `profile_loop`). Each allocation is
counted against the innermost `doorplate::` frame of its stack; closures are kept apart because that is where
inlined iterator code lands. Prints the share by module and by function, and allocations per parse.
"""
import argparse
import re
from collections import Counter


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folded")
    ap.add_argument("parses", type=int)
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    total, by_fn, by_mod = 0, Counter(), Counter()
    for line in open(a.folded):
        stack, _, n = line.rpartition(" ")
        n = int(n)
        total += n
        frames = [f for f in stack.split(";") if f.startswith("doorplate::")]
        inner = re.sub(r"::h[0-9a-f]{16}$", "", frames[-1]) if frames else "(no doorplate frame)"
        by_fn[inner] += n
        by_mod[inner.split("::")[1] if inner.startswith("doorplate::") else inner] += n
    print(f"{total} allocations, {total / a.parses:.1f} per parse")
    print("\nBy module")
    for k, v in by_mod.most_common(12):
        print(f"{100 * v / total:5.1f}%  {v / a.parses:6.1f}/parse  {k}")
    print("\nBy innermost doorplate function")
    for k, v in by_fn.most_common(a.top):
        print(f"{100 * v / total:5.1f}%  {v / a.parses:6.1f}/parse  {k}")


if __name__ == "__main__":
    main()
