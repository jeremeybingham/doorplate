"""Anonymize a messy address file before sharing it (every address here is invented).

    python examples/anonymize_example.py

`doorplate.Anonymizer` replaces digits and unknown words with others of the same length and
case, and keeps what decides how the parser reads a line: suffixes, directionals, unit
designators, states, the city and the first three ZIP digits. It works on lines that do not
parse. This is obfuscation, not anonymity: read the output before you share it. This library
formats and parses; it does not validate that an address exists or can receive mail.
"""
from pathlib import Path

import doorplate

DATA = Path(__file__).resolve().parent / "data" / "addresses_messy.txt"


def main():
    lines = [ln for ln in DATA.read_text().splitlines() if ln.strip()]
    anon = doorplate.Anonymizer(seed=7)  # a fixed seed repeats the output; leave it out for a random one
    results = anon.anonymize_many(lines)
    for before, after in list(zip(lines, results))[:5]:
        print(f"{before!r:55} -> {after.text!r}")
    same = sum(r.faithful for r in results)
    print(f"{same} of {len(results)} lines parse the same way as before")
    return results


if __name__ == "__main__":
    main()
