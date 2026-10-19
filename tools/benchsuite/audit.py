#!/usr/bin/env python3
"""Step 4 of the benchmark suite (#75): print records for the blind label audit.

    python tools/benchsuite/audit.py [--suite DIR] [--random 500] [--seed 4] [--skip N] [--count N]

Prints a random sample of the comparison track plus every record the generator flags as doubtful, each
as `id input` and then the gold labels inline (`token/label`). It never runs either parser, so the
reviewer cannot see their output (docs/benchmark-suite.md, "Keeping it fair"). The flags are rules about
the source columns, not about how a parser does:
a street name that holds a type or direction word, a house number with a letter or hyphen, a city with a
digit or an abbreviation, a single-letter street name, a unit identifier of letters only.
"""
import argparse
import gzip
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = {
    "AddressNumber": "N", "AddressNumberSuffix": "Ns", "AddressNumberPrefix": "Np", "StreetNamePreDirectional": "pd",
    "StreetNamePreType": "pt", "StreetNamePreModifier": "pm", "StreetName": "S", "StreetNamePostType": "T",
    "StreetNamePostDirectional": "D", "OccupancyType": "Ot", "OccupancyIdentifier": "Oi", "PlaceName": "C",
    "StateName": "ST", "ZipCode": "Z", "Recipient": "R", "CountryName": "CN", "USPSBoxType": "Bt", "USPSBoxID": "Bi",
    "USPSBoxGroupType": "Gt", "USPSBoxGroupID": "Gi", "BuildingName": "Bn",
}
TYPE_WORDS = {"ST", "AVE", "RD", "DR", "LN", "CT", "BLVD", "PL", "CIR", "TRL", "PKWY", "HWY", "TER", "WAY", "STREET",
              "ROAD", "AVENUE", "DRIVE", "LANE", "COURT", "BOULEVARD", "CIRCLE", "PLACE", "TRAIL", "LOOP"}
DIRS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW", "NORTH", "SOUTH", "EAST", "WEST"}


def flags(rec):
    out = []
    toks = rec["tokens"]
    name = [t.strip(",.").upper() for t, l in toks if l == "StreetName"]
    if any(w in TYPE_WORDS or w in DIRS for w in name):
        out.append("name-has-type-or-dir")
    if len(name) == 1 and len(name[0]) == 1:
        out.append("one-letter-name")
    if any(l in ("AddressNumber",) and re.search(r"[A-Za-z-]", t) for t, l in toks):
        out.append("number-letter-or-hyphen")
    city = [t.strip(",.").upper() for t, l in toks if l == "PlaceName"]
    if any(re.search(r"\d", w) for w in city) or any(w in ("ST", "FT", "MT", "N", "S", "E", "W") for w in city[:1]):
        out.append("city-digit-or-abbrev")
    if any(l == "OccupancyIdentifier" and re.fullmatch(r"[A-Za-z]+", t.strip(",")) and len(t.strip(",")) > 1 for t, l in toks):
        out.append("unit-letters-only")
    return out


def show(rec):
    inline = " ".join(f"{t}/{CODE.get(l, l)}" for t, l in rec["tokens"])
    return f"{rec['id']} [{rec['style']}{'+' + '+'.join(rec.get('mods', [])) if rec.get('mods') else ''}] {rec['input']}\n    {inline}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, default=ROOT / "benchmarks" / "suite" / "v1")
    ap.add_argument("--random", type=int, default=500)
    ap.add_argument("--seed", type=int, default=4)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--count", type=int, default=125)
    ap.add_argument("--flagged", action="store_true", help="list the flagged records instead of the random ones")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()
    recs = [json.loads(l) for l in gzip.open(args.suite / "compare.jsonl.gz", "rt")]
    flagged = [(r, flags(r)) for r in recs]
    if args.stats:
        import collections
        c = collections.Counter(f for _, fl in flagged for f in fl)
        print(len(recs), "records;", sum(1 for _, fl in flagged if fl), "flagged;", dict(c))
        return
    if args.flagged:
        pick = [r for r, fl in flagged if fl]
        random.Random(args.seed).shuffle(pick)
    else:
        pick = random.Random(args.seed).sample(recs, args.random)
    for r in pick[args.skip: args.skip + args.count]:
        print(show(r))


if __name__ == "__main__":
    main()
