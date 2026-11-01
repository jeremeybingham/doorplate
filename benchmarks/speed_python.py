#!/usr/bin/env python3
"""Python speed: doorplate against usaddress on the same strings.

    python benchmarks/speed_python.py [N] [--cache-usaddress]

Build the extension with `maturin develop --release` first (a debug build is
much slower). The inputs are the golden corpus's one-line addresses (committed,
invented) and, when `local-data/` has it, the geocode benchmark's addresses
(30,622 one-line strings; only timings are printed). Each is repeated up to N
(default 100,000). Every figure is the best of five runs. Prints Markdown.

usaddress is a CRF tagger (python-crfsuite); one call is `usaddress.parse` (the
token labels) or `usaddress.tag` (the joined dict). doorplate's `parse` also
does what `tag` does and more (components, key, slug are computed on demand), so
the closest like-for-like rows are `parse` / `tag` and `parse_tokens` /
`usaddress.parse`.

`--cache-usaddress` reuses the usaddress timings stored by an earlier run (`local-data/benchmarks/usaddress-cache.json`)
when the usaddress version, the inputs, N and the machine are the same, and stores them when they are not: usaddress
is most of the run and does not change. The output says which rows came from the cache and when they were made.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    best,
    cache_get,
    cache_put,
    corpus_inputs,
    geocode_inputs,
    inputs_id,
    machine,
    usable_cpus,
)

import doorplate as dp  # noqa: E402

try:
    import usaddress
except ImportError:
    usaddress = None


def rate(n, seconds):
    return f"{n / seconds:,.0f}"


def table(name, texts):
    n = len(texts)
    rows = [
        ("doorplate `parse`", lambda: [dp.parse(t) for t in texts]),
        ("doorplate `parse` and `key`, `to_usps`", lambda: [(a.key(), a.to_usps()) for a in map(dp.parse, texts)]),
        ("doorplate `tag`", lambda: [dp.tag(t) for t in texts]),
        ("doorplate `parse_tokens`", lambda: [dp.parse_tokens(t) for t in texts]),
        ("doorplate `parse_many`", lambda: dp.parse_many(texts)),
    ]
    if usaddress is not None:
        rows += [
            ("usaddress `parse`", lambda: [usaddress.parse(t) for t in texts]),
            ("usaddress `tag`", lambda: [_tag(t) for t in texts]),
        ]
    results = []
    cached_from = set()
    for label, fn in rows:
        if CACHE and label.startswith("usaddress"):
            key = f"speed_python|{label}|{inputs_id(texts)}"
            hit = cache_get(key, timing=True)
            if hit:
                results.append((label, hit[0]))
                cached_from.add(hit[1])
                continue
            secs = best(fn)
            cache_put(key, secs, timing=True)
            results.append((label, secs))
            continue
        results.append((label, best(fn)))
    base = dict(results)
    print(f"### {name} ({n:,} addresses)\n")
    print("| | Time | Addresses per second | Microseconds each |\n|---|---|---|---|")
    for label, secs in results:
        print(f"| {label} | {secs:.3f} s | {rate(n, secs)} | {secs / n * 1e6:,.1f} |")
    if cached_from:
        print(f"\nThe usaddress rows are from the cache (made {', '.join(sorted(cached_from))} on this machine, same usaddress version and inputs); the doorplate rows were measured now.")
    if usaddress is not None:
        ours = base["doorplate `parse_tokens`"]
        theirs = base["usaddress `parse`"]
        print(f"\nOne thread, call by call: `parse_tokens` is {theirs / ours:.1f}x `usaddress.parse`. "
              f"`parse_many` parses on all {usable_cpus()} threads with the GIL released, "
              f"{theirs / base['doorplate `parse_many`']:.1f}x `usaddress.parse` (which is single-threaded).\n")
    else:
        print()


def _tag(t):
    try:
        return usaddress.tag(t)
    except usaddress.RepeatedLabelError:
        return None


CACHE = False


def main():
    global CACHE
    args = [a for a in sys.argv[1:] if a != "--cache-usaddress"]
    CACHE = len(args) != len(sys.argv) - 1
    n = int(args[0]) if args else 100_000
    print(f"# Python speed\n\nMachine: {machine()}")
    print(f"doorplate {dp.__version__}" + (f"; usaddress {_usaddress_version()}" if usaddress else "; usaddress not installed") + "\n")
    base = corpus_inputs()
    table("Golden corpus inputs", (base * (n // len(base) + 1))[:n])
    geo = geocode_inputs()
    if geo:
        table("Geocode benchmark addresses", (geo * (n // len(geo) + 1))[:n])


def _usaddress_version():
    from importlib.metadata import version

    return version("usaddress")


if __name__ == "__main__":
    main()
