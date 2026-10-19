#!/usr/bin/env python3
"""Hold out 20% of the geocode benchmark's train split, unread.

    python benchmarks/split_geocode_train.py

Writes `train80_usaddress.xml` (to fix against) and `train20_heldout_usaddress.xml` (never read; score it
only to check that a fix generalizes) next to `train_usaddress.xml` in `local-data/geocode-benchmark/`.
The held-out part is every fifth address (0-based index divisible by 5), so the split is reproducible.
The benchmark states no license and stays in `local-data/`.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "local-data" / "geocode-benchmark"
root = ET.parse(D / "train_usaddress.xml").getroot()
keep, held = ET.Element(root.tag), ET.Element(root.tag)
for i, addr in enumerate(root):
    (held if i % 5 == 0 else keep).append(addr)
for name, part in (("train80", keep), ("train20_heldout", held)):
    ET.ElementTree(part).write(D / f"{name}_usaddress.xml", encoding="utf-8", xml_declaration=True)
    print(f"{name}: {len(part):,} addresses")
