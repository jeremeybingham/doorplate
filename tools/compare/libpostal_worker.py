#!/usr/bin/env python3
"""Parse strings with libpostal and print the labelled pieces (issue 215).

    libpostal-venv/bin/python libpostal_worker.py < strings.json > parsed.json

Reads a JSON list of strings on stdin and writes one JSON object: `load_seconds` (importing `postal.parser`, which loads the model, and a first call),
`parse_seconds` (all the strings, one thread), and `results` (per string, the `[value, label]` pieces of
`postal.parser.parse_address`; an input libpostal raises on gives `[]`). It runs in the libpostal virtualenv
(`tools/compare/compare_usaddress.py` starts it with `LD_LIBRARY_PATH` set), so doorplate's own environment does not need the
C library. Nothing is printed but the JSON.
"""

import json
import sys
import time


def rss_mb():
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def bench(request):
    """Speed mode (benchmarks/_libpostal.py): load, say READY, wait for GO, then time `reps` passes over the strings.

    Prints READY, then after a line `GO` one JSON line: `load_seconds`, `best_seconds` (the fastest pass, one thread),
    `rss_after_load_mb` and `rss_peak_mb` (the peak resident size of this process)."""
    t = time.time()
    # importing loads the model: that is the load time
    from postal.parser import parse_address

    parse_address("1 main st")
    load = time.time() - t
    after_load = rss_mb()
    print("READY", flush=True)
    sys.stdin.readline()
    strings = request["strings"]
    best = None
    for _ in range(request["bench"]):
        t = time.perf_counter()
        for s in strings:
            parse_address(s)
        took = time.perf_counter() - t
        best = took if best is None else min(best, took)
    print(json.dumps({"load_seconds": load, "best_seconds": best, "rss_after_load_mb": after_load, "rss_peak_mb": rss_mb()}), flush=True)


def main():
    request = json.loads(sys.stdin.readline())
    if isinstance(request, dict) and "bench" in request:
        return bench(request)
    strings = request
    t = time.time()
    # importing loads the model: that is the load time
    from postal.parser import parse_address

    parse_address("1 main st")
    load = time.time() - t
    t = time.time()
    results = []
    for s in strings:
        try:
            results.append([[v, label] for v, label in parse_address(s)])
        except Exception:  # noqa: BLE001  (an input libpostal rejects scores as wrong, not as a crash)
            results.append([])
    json.dump({"load_seconds": load, "parse_seconds": time.time() - t, "results": results}, sys.stdout)


if __name__ == "__main__":
    main()
