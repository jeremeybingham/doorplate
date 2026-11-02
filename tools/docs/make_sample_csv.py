#!/usr/bin/env python3
"""The sample CSV of the Try page (#434): `site/demo/sample-addresses.csv`, invented rows from a seeded generator.

    python tools/docs/make_sample_csv.py [--check]

Every street name is built from syllables that this script picks, every house number, unit and box number is random, and
the cities are a short fixed list with a ZIP prefix of that state: no row is copied from a source, and a row could name a
place that exists only by accident. The shapes are the ones a visitor to the page should see: plain streets, directionals,
units in several styles, PO boxes, rural routes, highways, military, ZIP+4, a missing ZIP, hyphenated numbers, fractions, and
messy case and punctuation. The same seed gives the same file (`--check` fails if the committed file differs), and
`test_sample_csv.py` checks that no row is in the repository's own corpora. See `docs/data-policy.md`.
"""

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site" / "demo" / "sample-addresses.csv"
SEED = 434
ROWS = 300

SYL_A = [
    "bar",
    "cal",
    "dor",
    "el",
    "fen",
    "gar",
    "hal",
    "iv",
    "jun",
    "kes",
    "lor",
    "mar",
    "nor",
    "ol",
    "pen",
    "quil",
    "ros",
    "sal",
    "tam",
    "ulv",
    "ver",
    "wil",
    "yar",
    "zan",
]
SYL_B = [
    "ley",
    "wick",
    "ford",
    "mont",
    "dale",
    "brook",
    "stead",
    "worth",
    "haven",
    "field",
    "crest",
    "wood",
    "mere",
    "ton",
]
SUFFIXES = [
    ("St", "Street"),
    ("Ave", "Avenue"),
    ("Rd", "Road"),
    ("Dr", "Drive"),
    ("Ln", "Lane"),
    ("Ct", "Court"),
    ("Blvd", "Boulevard"),
    ("Way", "Way"),
    ("Pl", "Place"),
    ("Ter", "Terrace"),
]
DIRS = ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]
DIR_WORDS = {
    "N": "North",
    "S": "South",
    "E": "East",
    "W": "West",
    "NE": "Northeast",
    "NW": "Northwest",
    "SE": "Southeast",
    "SW": "Southwest",
}
CITIES = [
    ("Springfield", "IL", "627"),
    ("Riverton", "UT", "840"),
    ("Lakewood", "OH", "441"),
    ("Fairview", "TX", "750"),
    ("Georgetown", "KY", "403"),
    ("Clinton", "IA", "527"),
    ("Salem", "OR", "973"),
    ("Madison", "WI", "537"),
    ("Franklin", "TN", "370"),
    ("Arlington", "VA", "222"),
    ("Bristol", "CT", "060"),
    ("Ashland", "MT", "590"),
    ("Oxford", "MS", "386"),
    ("Dover", "DE", "199"),
    ("Burlington", "VT", "054"),
    ("Milton", "FL", "325"),
]
ROUTES = ["County Road", "State Route", "US Highway", "Farm Road", "Highway"]
MIL = [("APO", "AE", "090"), ("APO", "AP", "962"), ("FPO", "AA", "340")]


def ordinal(k):
    if 10 <= k % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")


RESERVED = {"vermont"}  # a syllable pair that spells a real state, which the anonymizer keeps


def street(r):
    name = r.choice(SYL_A) + r.choice(SYL_B)
    while name in RESERVED:
        name = r.choice(SYL_A) + r.choice(SYL_B)
    if r.random() < 0.18:
        k = r.randint(1, 98)
        return f"{k}{ordinal(k)}"
    return name.capitalize()


def zip5(r, z3):
    return z3 + f"{r.randint(0, 99):02d}"


def one(r, shape):
    city, st, z3 = r.choice(CITIES)
    z = zip5(r, z3)
    n = r.randint(1, 9999)
    ab, full = r.choice(SUFFIXES)
    name = street(r)
    if shape == "plain":
        return f"{n} {name} {ab}, {city} {st} {z}"
    if shape == "full":
        return f"{n} {name} {full}, {city}, {st} {z}"
    if shape == "dir":
        d = r.choice(DIRS)
        return f"{n} {DIR_WORDS[d] if r.random() < 0.4 else d} {name} {ab}, {city} {st} {z}"
    if shape == "postdir":
        return f"{n} {name} {ab} {r.choice(DIRS)}, {city} {st} {z}"
    if shape == "apt":
        unit = r.choice(["Apt {}", "Unit {}", "Ste {}", "#{}", "Suite {}", "Apt. {}"])
        num = r.choice(
            [
                str(r.randint(1, 40)),
                f"{r.randint(1, 20)}{r.choice('ABCD')}",
                str(r.randint(100, 950)),
            ]
        )
        return f"{n} {name} {ab} {unit.format(num)}, {city} {st} {z}"
    if shape == "unit2":
        return f"{n} {name} {ab}, {r.choice(['Apt', 'Unit', 'Ste'])} {r.randint(1, 60)}, {city} {st} {z}"
    if shape == "pobox":
        return (
            r.choice(
                ["PO Box {}", "P.O. Box {}", "Post Office Box {}", "PO BOX {}"]
            ).format(r.randint(1, 9999))
            + f", {city} {st} {z}"
        )
    if shape == "route":
        return f"RR {r.randint(1, 9)} Box {r.randint(1, 300)}, {city} {st} {z}"
    if shape == "highway":
        return f"{n} {r.choice(ROUTES)} {r.randint(1, 999)}, {city} {st} {z}"
    if shape == "military":
        p, s2, z3m = r.choice(MIL)
        return f"PSC {r.randint(1, 999)} Box {r.randint(1, 9999)}, {p} {s2} {z3m}{r.randint(0, 99):02d}"
    if shape == "zip4":
        return f"{n} {name} {ab}, {city} {st} {z}-{r.randint(0, 9999):04d}"
    if shape == "nozip":
        return f"{n} {name} {ab}, {city} {st}"
    if shape == "queens":
        return f"{r.randint(10, 99)}-{r.randint(10, 99)} {name} {ab}, {city} {st} {z}"
    if shape == "half":
        return f"{n} 1/2 {name} {ab}, {city} {st} {z}"
    if shape == "messy":
        s = f"{n} {name} {ab}., {city} {st} {z}"
        return r.choice(
            [s.upper(), s.lower(), s.replace(",", " "), s.replace(", ", ",")]
        )
    if shape == "attn":
        return f"c/o {r.choice(['Front Desk', 'Receiving', 'Mail Room'])}, {n} {name} {ab}, {city} {st} {z}"
    if shape == "nonum":
        return f"{name} {ab}, {city} {st} {z}"
    if shape == "range":
        return f"{n}-{n + 2 * r.randint(1, 4)} {name} {ab}, {city} {st} {z}"
    if shape == "tail":
        return f"{n} {name} {ab} {r.choice(['deliver to back door', 'ring bell twice', 'gate code on file'])}, {city} {st} {z}"
    raise ValueError(shape)


# (shape, weight): plain streets dominate, the odd ones are each a few percent.
WEIGHTS = [
    ("plain", 18),
    ("full", 6),
    ("dir", 10),
    ("postdir", 4),
    ("apt", 16),
    ("unit2", 4),
    ("pobox", 8),
    ("route", 4),
    ("highway", 5),
    ("military", 3),
    ("zip4", 5),
    ("nozip", 4),
    ("queens", 3),
    ("half", 2),
    ("messy", 6),
    ("attn", 2),
    ("nonum", 2),
    ("range", 2),
    ("tail", 2),
]


def rows():
    r = random.Random(SEED)
    shapes = [s for s, w in WEIGHTS for _ in range(w)]
    seen, out = set(), []
    while len(out) < ROWS:
        a = one(r, r.choice(shapes))
        if a.lower() not in seen:
            seen.add(a.lower())
            out.append(a)
    return out


def render():
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "address"])
    for i, a in enumerate(rows(), 1):
        w.writerow([f"S{i:03d}", a])
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed file differs from the generator's output",
    )
    args = ap.parse_args()
    text = render()
    if args.check:
        sys.exit(
            0
            if OUT.read_text(encoding="utf-8") == text
            else f"{OUT} differs: run tools/docs/make_sample_csv.py"
        )
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({ROWS} rows)")


if __name__ == "__main__":
    main()
