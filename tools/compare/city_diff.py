#!/usr/bin/env python3
"""Which cities does a build get right or wrong that another build does not?

    python tools/compare/city_diff.py BASE_CLI NEW_CLI [SPLIT]     # SPLIT: train80 (default), train20_heldout, dev, test

Parses every address of a geocode benchmark split (`local-data/geocode-benchmark/<SPLIT>_usaddress.xml`)
as one line with each CLI binary (`doorplate parse -`), compares the parsed city with the labeled place
name, and prints how many cities NEW gets right that BASE does not (gains) and the reverse (regressions),
with the first words of the gained and lost cities. Counts and first words only. Use it with
`tools/compare/oneline_fl.py` (the benchmark spells postdirectionals abbreviated; the Florida records do
not). This library formats and parses; it does not validate that an address exists or can receive mail.
"""
import collections
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def norm(s):
    s = re.sub(r"[’'.]", "", s.upper())
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join({"ST": "SAINT", "FT": "FORT", "MT": "MOUNT"}.get(w, w) for w in s.split())


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    base, new = sys.argv[1], sys.argv[2]
    split = sys.argv[3] if len(sys.argv) > 3 else "train80"
    root = ET.parse(ROOT / "local-data" / "geocode-benchmark" / f"{split}_usaddress.xml").getroot()
    texts, labels = [], []
    for addr in root:
        city = " ".join((e.text or "").strip() for e in addr if e.tag == "PlaceName")
        if city:
            texts.append(" ".join((e.text or "").strip() for e in addr))
            labels.append(norm(city))

    def run(binary):
        out = subprocess.run([binary, "parse", "-"], input="\n".join(texts) + "\n", capture_output=True, text=True).stdout
        return [norm(json.loads(x)["components"].get("city", "")) if x.startswith("{") else "" for x in out.splitlines()]

    b, n = run(base), run(new)
    gain, lost = collections.Counter(), collections.Counter()
    for lab, x, y in zip(labels, b, n):
        if y == lab and x != lab:
            gain[lab.split()[0]] += 1
        if x == lab and y != lab:
            lost[lab.split()[0]] += 1
    print(f"{split}: {len(texts):,} addresses with a city | gains {sum(gain.values())} | regressions {sum(lost.values())}")
    print(" gained, first word of the city:", gain.most_common(10))
    print(" lost, first word of the city:  ", lost.most_common(10))


if __name__ == "__main__":
    main()
