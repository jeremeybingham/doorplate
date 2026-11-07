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


def main():
    strings = json.load(sys.stdin)
    t = time.time()
    from postal.parser import (
        parse_address,  # importing loads the model: that is the load time
    )

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
