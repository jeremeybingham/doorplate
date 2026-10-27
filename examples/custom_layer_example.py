"""Teach doorplate your own spellings, places and ZIPs (every name here is invented).

    python examples/custom_layer_example.py

A custom layer is a folder of small files (`layer.toml`, `aliases.toml`, `overrides.toml`,
`places.tsv`, `zips.tsv`) that adds to the shipped tables and never replaces them. This script
writes a tiny one to a temporary folder, loads it with `doorplate.load_layer`, and shows what
changes: the parse, the key and the `custom_layer` provenance. The same folder works from the
command line (`doorplate parse --custom-layer DIR ...`, `doorplate layer check DIR`). A layer can
change a key, so store its `fingerprint` with the keys. This library formats and parses; it does
not validate that an address exists or can receive mail.
"""
import tempfile
from pathlib import Path

import doorplate

LAYER = 'name = "county-extras"\nversion = "2026.10.1"\nnotes = "Spellings seen in an invented county export"\n'
ALIASES = """\
[[suffix]]
abbr = "TRL"
spellings = ["TRAYL"]
evidence = "invented county export: 41 lines like `120 OAK TRAYL`"
"""
PLACES = "state\tname\tcounty\tvariants\tevidence\nFL\tQUINCEWOOD HEIGHTS\tZEPHYR\tQUINCEWOD HEIGHTS\tinvented county export\n"
ZIPS = "zip\tstate\tplace\tevidence\n33999\tFL\tQUINCEWOOD HEIGHTS\tinvented county export\n"

LINES = [
    "123 Oak Trayl, Miami, FL 33101",
    "12 Willow Way, Quincewod Heights, FL 33999",
]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in (
            ("layer.toml", LAYER),
            ("aliases.toml", ALIASES),
            ("places.tsv", PLACES),
            ("zips.tsv", ZIPS),
        ):
            (folder / name).write_text(text)
        layer = doorplate.load_layer(folder)  # raises doorplate.LayerError listing every problem
        print(layer, layer.counts())
        for line in LINES:
            before, after = doorplate.parse(line), doorplate.parse(line, custom_layer=layer)
            print(f"\n{line}")
            for label, a in (("without", before), ("with", after)):
                place = a.place["name"] if a.place else None
                print(f"  {label + ':':9} suffix={a.street_suffix} place={place} key={a.key()}")
        print("\nreported in every parse:", after.custom_layer)
        return layer


if __name__ == "__main__":
    main()
