#!/usr/bin/env python3
"""Write fuzz seed inputs from the golden corpus.

Usage: seed.py OUT_DIR

Writes OUT_DIR/parse/ and OUT_DIR/parse_fields/, one file per corpus case, in
the byte layout each target in fuzz/fuzz_targets/ reads: for `parse`, a first
byte that picks the default_state hint followed by the text; for
`parse_fields`, line1, line2, city, state and ZIP joined by U+0001.
"""

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
# Index into HINTS in fuzz/fuzz_targets/parse.rs.
HINTS = {None: 0, "FL": 1, "AL": 2, "NY": 3}
FIELDS = ["line1", "line2", "city", "state", "zip"]


def write(directory, data):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / hashlib.sha1(data).hexdigest()).write_bytes(data)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = pathlib.Path(sys.argv[1])
    count = 0
    for path in sorted((ROOT / "tests" / "corpus").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            hint = bytes([HINTS.get(case.get("default_state"), 0)])
            if "input" in case:
                text = case["input"]
                write(out / "parse", hint + text.encode())
                write(out / "parse_fields", text.encode())
            elif "lines" in case:
                lines = case["lines"]
                write(out / "parse", hint + ", ".join(lines).encode())
                write(out / "parse_fields", "\x01".join(lines[:2]).encode())
            elif "fields" in case:
                fields = case["fields"]
                joined = "\x01".join(fields.get(f) or "" for f in FIELDS)
                write(out / "parse_fields", joined.encode())
                text = ", ".join(fields[f] for f in FIELDS if fields.get(f))
                write(out / "parse", hint + text.encode())
            else:
                continue
            count += 1
    print(f"seeded {count} corpus cases into {out}")


if __name__ == "__main__":
    main()
