#!/usr/bin/env python3
"""Fold a `perf record -g` profile into tables by function and by pipeline stage (#90).

    perf record -e cpu-clock -F 2000 -g --call-graph fp -o perf.data BINARY ARGS
    python benchmarks/profile_fold.py perf.data BINARY [--top 25]

WSL2's perf cannot resolve symbols, so this takes the raw addresses from `perf script`, maps them
with `nm` and the program headers of BINARY (built with `CARGO_PROFILE_RELEASE_STRIP=false`
`RUSTFLAGS="-C force-frame-pointers=yes"`), and counts samples: exclusive (the leaf frame) and
inclusive (anywhere in the stack). Frames in libc and other libraries are reported as `[libc]` etc.
Stages are the doorplate modules (clean, tokenize, tagger, classify, assemble, lexicon, emit, parser).
"""
import argparse
import bisect
import re
import subprocess
from collections import Counter

STAGES = ("clean", "tokenize", "tagger", "classify", "assemble", "lexicon", "emit", "parser", "input", "types")


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def symbols(binary):
    syms = []
    for line in sh("nm", "-n", "-S", "-C", "--defined-only", binary).splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[2] in "tTwW":
            name = re.sub(r"::h[0-9a-f]{16}$", "", parts[3])
            syms.append((int(parts[0], 16), int(parts[1], 16), name))
    return syms


def segment_delta(binary):
    """vaddr - file offset for each LOAD segment: [(offset, filesz, delta)]."""
    out = []
    for line in sh("readelf", "-lW", binary).splitlines():
        p = line.split()
        if p and p[0] == "LOAD":
            off, vaddr, filesz = int(p[1], 16), int(p[2], 16), int(p[4], 16)
            out.append((off, filesz, vaddr - off))
    return out


def stage(name):
    m = re.match(r"(?:<)?doorplate::(\w+)", name)
    if m:
        return m.group(1) if m.group(1) in STAGES else "doorplate (other)"
    if name.startswith(("alloc::", "<alloc::", "core::", "<core::", "std::", "<std::", "hashbrown::")):
        return "std/alloc/core"
    if "malloc" in name or name.startswith(("free", "cfree")):
        return "malloc"
    return name if name.startswith("[") else "other"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perf_data")
    ap.add_argument("binary")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    syms = symbols(a.binary)
    addrs = [s[0] for s in syms]
    segs = segment_delta(a.binary)
    mm = re.search(r"\[(0x[0-9a-f]+)\((0x[0-9a-f]+)\) @ (0x[0-9a-f]+) .*\]: r-xp \S*" + re.escape(a.binary.split("/")[-1]) + r"\s*$",
                   sh("perf", "script", "-i", a.perf_data, "--show-mmap-events"), re.M)
    if not mm:
        raise SystemExit("no executable mapping of the binary in the profile")
    start, _, pgoff = (int(g, 16) for g in mm.groups())

    def resolve(ip):
        if not start <= ip < start + int(mm.group(2), 16):
            return "[libc/other]"
        off = ip - start + pgoff
        delta = next((d for o, sz, d in segs if o <= off < o + sz), 0)
        v = off + delta
        i = bisect.bisect_right(addrs, v) - 1
        return syms[i][2] if i >= 0 and v < syms[i][0] + max(syms[i][1], 1) else "[unknown]"

    excl, incl, stage_excl, stage_incl, total = Counter(), Counter(), Counter(), Counter(), 0
    libc_callers = Counter()
    stacks = sh("perf", "script", "-i", a.perf_data, "-F", "ip").split("\n\n")
    for s in stacks:
        ips = [int(x, 16) for x in s.split()]
        if not ips:
            continue
        names = [resolve(ip) for ip in ips]
        total += 1
        excl[names[0]] += 1
        if names[0] == "[libc/other]":
            libc_callers[next((n for n in names if not n.startswith("[")), "[unknown]")] += 1
        stage_excl[stage(names[0])] += 1
        for n in set(names):
            incl[n] += 1
        for st in {stage(n) for n in names}:
            stage_incl[st] += 1

    def table(title, counter):
        print(f"\n{title}\n{'share':>7}  name")
        for name, c in counter.most_common(a.top):
            print(f"{100 * c / total:6.1f}%  {name[:110]}")

    print(f"{total} samples")
    table("By stage, exclusive (the leaf frame)", stage_excl)
    table("By stage, inclusive (anywhere in the stack)", stage_incl)
    table("Functions, exclusive", excl)
    table("Functions, inclusive", incl)
    table("Caller (first doorplate or std frame) of samples whose leaf is in libc", libc_callers)


if __name__ == "__main__":
    main()
