"""Convert the geocoding address-parsing benchmark's IOB splits
(test.txt, dev.txt, train.txt) to usaddress's training XML format
(test_usaddress.xml, ...), so tools/compare/compare_usaddress.py can score both
parsers on them with its `gold` mode.

    python benchmarks/convert_geocode_benchmark.py [test] [dev] [train]

Source: https://github.com/zhengcongyin/geocoding-address-parsing-benchmark
(`benchmark_dataset/`). The benchmark states no license, so it is not
in this repository: download the splits into `local-data/geocode-benchmark/`
(git-ignored) and run this script there. Its output is written beside it.
"""
import collections
import os
import sys
from xml.sax.saxutils import escape

HERE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local-data", "geocode-benchmark"
)

# Benchmark label -> usaddress label.
LABELS = {
    "HOUSENUM": "AddressNumber",
    "PREDIRECTIONAL": "StreetNamePreDirectional",
    "STREET": "StreetName",
    "ROADTYPE": "StreetNamePostType",
    "POSTDIRECTIONAL": "StreetNamePostDirectional",
    "CITY": "PlaceName",
    "STATE": "StateName",
    "POSTAL": "ZipCode",
}


def records(path):
    cur = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            token, tag = line.rsplit(" ", 1) if not line.startswith("-END-") else ("-END-", "")
            if token == "-END-":
                if cur:
                    yield cur
                cur = []
                continue
            cur.append((token, LABELS[tag.split("-", 1)[1]]))
    if cur:
        yield cur


def main():
    splits = sys.argv[1:] or ["test"]
    for split in splits:
        convert(split)


def convert(split):
    src = os.path.join(HERE, f"{split}.txt")
    out = os.path.join(HERE, f"{split}_usaddress.xml")
    n, labels = 0, collections.Counter()
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("<AddressCollection>\n")
        for rec in records(src):
            parts = " ".join(f"<{l}>{escape(t)}</{l}>" for t, l in rec)
            fh.write(f"  <AddressString>{parts}</AddressString>\n")
            n += 1
            labels.update(l for _, l in rec)
        fh.write("</AddressCollection>\n")
    print(f"wrote {n} addresses to {out}")
    for label, count in labels.most_common():
        print(f"  {label:28} {count}")


if __name__ == "__main__":
    main()
