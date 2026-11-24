#!/usr/bin/env python3
"""Regenerate crates/doorplate-js/test/fixtures.json: the native `doorplate parse` record for a fixed list of
invented addresses. The JavaScript package's parity test compares the wasm output to it (spans aside).

    cargo build --release -p doorplate-cli && python3 tools/js_fixtures.py [path/to/doorplate]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "crates/doorplate-js/test/fixtures.json"
INPUTS = [
    "123 N Main St Apt 4, Springfield IL 62704",
    "1600 Elm Avenue NW, Washington DC 20500-0001",
    "PO Box 12, Reno NV 89501",
    "PSC 123 Box 45, APO AE 09001",
    "Calle 5 Urb Las Flores, San Juan PR 00901",
    "12 Café Ünïcode St, Miami FL 33101",
    "77 Emoji Rd 😀, Austin TX 78701",
    "RR 2 Box 45, Cody WY 82414",
    "500 S Glued Hwy 9 Suite 300 Tampa FL 33602",
    "9 West 5th Street Unit B, New York NY 10001",
    "General Delivery, Nome AK 99762",
    "x" * 3000 + " St, Boise ID 83702",
]
EMPTY = [""]  # native exits with an error; the package returns an `error` record


def main():
    binary = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "target/release/doorplate")
    rows = []
    for text in INPUTS:
        out = subprocess.run([binary, "parse", text], check=True, capture_output=True, text=True).stdout
        rows.append({"input": text, "record": json.loads(out)})
    OUT.write_text(json.dumps({"records": rows, "errors": EMPTY}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} records to {OUT.relative_to(ROOT)}")


main()
