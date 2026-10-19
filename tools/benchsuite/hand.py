#!/usr/bin/env python3
"""Expand the hand-labeled shapes (tools/benchsuite/hand/shapes.txt) into hand.jsonl: the `hand` stratum.

    python tools/benchsuite/hand.py [--total 1000] [--seed 75] [--check]

The shapes are written by hand, with their gold labels, from the forms messy real rows take (typed forms,
mailing lists, MLS fields, PO boxes, routes, military). This script only fills the slots: invented street
names and numbers, and real city, state and ZIP combinations from the NAD sample. Every label comes from
the template, never from a parser. Output records are checked three ways: the labeled tokens must be the
tokens `usaddress.tokenize` finds in the string, the string must not appear in any exclusion file (the same
files as the generator's), and no string may repeat. `--check` prints one expansion of every shape instead
of writing, for the second reading of the labels (docs/benchmark-suite.md, step 4).

This library formats and parses; it does not validate that an address exists.
"""
import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path

import duckdb
import usaddress

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import build as B  # noqa: E402  (the exclusion files)

SHAPES = HERE / "hand" / "shapes.txt"
OUT = HERE / "hand" / "hand.jsonl"
SAMPLE = ROOT / "local-data" / "nad-2026" / "sample1m.parquet"

LABELS = {
    "N": "AddressNumber", "Ns": "AddressNumberSuffix", "Np": "AddressNumberPrefix", "pd": "StreetNamePreDirectional",
    "pt": "StreetNamePreType", "S": "StreetName", "T": "StreetNamePostType", "D": "StreetNamePostDirectional",
    "Ot": "OccupancyType", "Oi": "OccupancyIdentifier", "C": "PlaceName", "ST": "StateName", "Z": "ZipCode",
    "R": "Recipient", "CN": "CountryName", "Bt": "USPSBoxType", "Bi": "USPSBoxID", "Gt": "USPSBoxGroupType",
    "Gi": "USPSBoxGroupID", "Cr": "CornerOf", "Is": "IntersectionSeparator", "-": None,
}
STREETS = """Alderwick Bramblecote Cinderfall Dovecrest Elmstead Fernhollow Glenmoor Hawthrush Ivywood Juniperline
Kestrel_Run Lindenmere Marrowfield Nettlebrook Oakhaven Pinecrest_Hollow Quillon Ravenscar Saffron_Ridge Thistledown
Umberfield Vesper_Glen Willowbend Yarrowdale Zephyr_Point Ashgrove Brindlemoor Copperbeech Duskwater Emberlane
Foxglove_Bend Gossamer Heatherdown Inkberry Jessamine Knollcrest Larkspur_Rise Mistral Nightjar Orchard_Hollow
Primrose_Gate Quailridge Rosewater Sablewood Tamarind Underhill Violet_Brook Whistlewood Yewdale Amberleigh
Birchmere Cloverfield Driftwood_Cove Eastlake_Heath Fallowmere Granite_Mill Harrowgate Ironwood_Bluff Juno_Hill
Kingfisher Lavender_Fields Meadowlark Nutmeg Olive_Grove Pebblebrook Quince_Orchard Rowan_Close Sandpiper
Tansy_Hollow Upland_Heights Verdant Wrenfield Yarrow Aspenglow Briarwood_Gap Cedar_Brake Dunmore_Glen Elderflower
Fieldstone_Crossing Gilded_Maple Hollyberry Indigo_Run Jasper_Ledge Kelpie Longmeadow Mossy_Creek Northwind
Oriole_Walk Plover Quarry_Hill Ridgeback Starling Teasel Umbra Valley_Forge_Mill Windflower Zinnia""".split()
TYPES = ["St", "Street", "Ave", "Avenue", "Rd", "Road", "Dr", "Drive", "Ln", "Lane", "Ct", "Court", "Blvd", "Boulevard",
         "Way", "Pl", "Place", "Cir", "Circle", "Trl", "Trail", "Pkwy", "Parkway", "Ter", "Terrace"]
ABBR_TYPES = [t for t in TYPES if len(t) <= 4 and t not in ("Road", "Lane", "Drive", "Place", "Court", "Way", "Trail")]
MISSPELT = ["Stret", "Streeet", "Avenu", "Avanue", "Roadd", "Drve", "Lan", "Boulvard", "Corut", "Plce", "Trial", "Parkwy"]
DIRS = ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]
DOTTED = ["N.", "S.", "E.", "W.", "N.E.", "N.W.", "S.E.", "S.W."]
SPELLED = ["North", "South", "East", "West", "Northeast", "Northwest", "Southeast", "Southwest"]
DESIG = ["Apt", "Apt.", "Unit", "Ste", "Suite", "Rm", "Dept", "Ofc", "Spc"]
RECIPIENTS = ["Jane Doe", "John Q. Public", "Pat Sample", "Resident", "Current Resident", "Accounts Payable",
              "Property Management", "Sam Example", "Acme Supply Co", "Front Desk"]
ORDINALS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "11th", "12th", "13th", "22nd", "31st", "42nd"]
ORDWORDS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth"]
SPECIAL = [("St. Louis", "MO", "63101"), ("Fort Worth", "TX", "76102"), ("Ft. Worth", "TX", "76102"),
           ("Mt. Pleasant", "SC", "29464"), ("Saint Paul", "MN", "55101"), ("St. Paul", "MN", "55101"),
           ("Coeur d'Alene", "ID", "83814"), ("O'Fallon", "MO", "63366"), ("Winston-Salem", "NC", "27101"),
           ("Port St. Lucie", "FL", "34952"), ("Ann Arbor", "MI", "48104"), ("Las Cruces", "NM", "88001"),
           ("Mount Vernon", "NY", "10550"), ("Mt. Vernon", "NY", "10550"), ("N. Little Rock", "AR", "72114"),
           ("West Palm Beach", "FL", "33401"), ("W. Palm Beach", "FL", "33401"), ("Fort Lauderdale", "FL", "33301"),
           ("King of Prussia", "PA", "19406"), ("Wilkes-Barre", "PA", "18701"), ("Lee's Summit", "MO", "64063"),
           ("De Pere", "WI", "54115"), ("McKinney", "TX", "75069"), ("La Crosse", "WI", "54601"),
           ("Santa Fe", "NM", "87501"), ("Sault Ste. Marie", "MI", "49783"), ("Winston Salem", "NC", "27101")]
STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
          "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
          "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
          "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
          "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
          "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
          "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
          "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
          "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
          "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}


def load_places(seed):
    """Real (city, state, zip) combinations from the NAD sample, title-cased."""
    rows = duckdb.connect().execute(f"""select c, s, z from (select upper(Post_City) c, State s, Zip_Code z from '{SAMPLE}'
        where regexp_matches(Post_City, '^[A-Za-z ]+$') and length(Zip_Code) = 5
        and State in ({','.join("'" + x + "'" for x in STATES)})) group by 1, 2, 3 having count(*) >= 8
        order by hash(c, z, {seed}) limit 6000""").fetchall()
    return [(c.title(), st, z) for c, st, z in rows if len(c) > 2 and B.good_city(c) and "COUNTY" not in c]


def parse_shapes():
    out = []
    for line in SHAPES.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        count, typ, tag, case, template = [p.strip() for p in line.split("|", 4)]
        out.append({"count": int(count), "type": typ, "tag": tag, "case": case, "template": template})
    return out


class Filler:
    def __init__(self, rng, places, single):
        self.rng, self.places, self.single = rng, places, single
        self.v = {}

    def place(self, need_single):
        if "place" not in self.v:
            pool = self.single if need_single else self.places
            self.v["place"] = self.rng.choice(pool)
        return self.v["place"]

    def get(self, name, template):
        r = self.rng
        if name in self.v:
            return self.v[name]
        place = lambda: self.place("{city1}" in template)
        val = {
            "n": lambda: str(r.randint(1, 99999)) if r.random() < 0.3 else str(r.randint(10, 9999)),
            "n2": lambda: str(r.randint(10, 9999)),
            "street": lambda: r.choice(STREETS).replace("_", " "),
            "street2": lambda: r.choice(STREETS).replace("_", " "),
            "ty": lambda: r.choice(TYPES), "ty2": lambda: r.choice(TYPES), "ty.": lambda: r.choice(ABBR_TYPES) + ".",
            "tyt": lambda: r.choice(MISSPELT),
            "dir": lambda: r.choice(DIRS), "dir2": lambda: r.choice(DIRS), "dirdot": lambda: r.choice(DOTTED),
            "dirw": lambda: r.choice(SPELLED),
            "u": lambda: r.choice([str(r.randint(1, 9)), str(r.randint(10, 480)), f"{r.randint(1, 40)}{r.choice('ABCDEF')}",
                                   r.choice("ABCDEFGH"), f"{r.choice('ABC')}{r.randint(1, 30)}", f"{r.randint(1, 9)}-{r.choice('ABC')}"]),
            "u2": lambda: r.choice([str(r.randint(1, 9)), str(r.randint(10, 480)), f"{r.randint(1, 40)}{r.choice('ABCDEF')}"]),
            "ud": lambda: r.choice([str(r.randint(1, 9)), str(r.randint(10, 480)), f"{r.randint(1, 40)}{r.choice('ABCDEF')}"]),
            "desig": lambda: r.choice(DESIG),
            "city": lambda: place()[0], "city1": lambda: place()[0], "st": lambda: place()[1], "zip": lambda: place()[2],
            "stfull": lambda: STATES[place()[1]],
            "zip4": lambda: f"{place()[2]}-{r.randint(1000, 9999)}", "zip4s": lambda: str(r.randint(1000, 9999)),
            "cityt": lambda: (lambda c: c[: len(c) // 2] + c[len(c) // 2 + 1:])(place()[0]),
            "box": lambda: str(r.randint(1, 9999)) if r.random() < 0.8 else str(r.randint(10000, 99999)),
            "route": lambda: str(r.randint(1, 99)), "mnum": lambda: str(r.randint(1, 9999)),
            "rec": lambda: r.choice(RECIPIENTS), "ord": lambda: r.choice(ORDINALS), "ordw": lambda: r.choice(ORDWORDS),
            "L": lambda: r.choice("ABCDEFGHJKLMNPRSTW"),
        }
        if name in ("cityx", "stx", "zipx"):
            if "special" not in self.v:
                self.v["special"] = r.choice(SPECIAL)
            return self.v["special"][("cityx", "stx", "zipx").index(name)]
        if name in ("mc", "ms", "mz"):
            if "mil" not in self.v:
                st, lo, hi = r.choice([("AE", 9000, 9999), ("AP", 96200, 96699), ("AA", 34000, 34099)])
                self.v["mil"] = (r.choice(["APO", "APO", "FPO", "DPO"]), st, f"{r.randint(lo, hi):05d}")
            return self.v["mil"][("mc", "ms", "mz").index(name)]
        self.v[name] = val[name]()
        return self.v[name]

    def fill(self, text, template):
        def sub(m):
            name, mod = m.group(1), m.group(2)
            v = self.get(name, template)
            return v.upper() if mod == "^" else v.lower() if mod == "_" else v
        return re.sub(r"\{([A-Za-z0-9.]+?)([\^_]?)\}", sub, text)


def expand(shape, rng, places, single):
    f = Filler(rng, places, single)
    pieces, labels, state = [], [], None
    for word in shape["template"].split():
        text, spec = word.rsplit("/", 1)
        text = f.fill(text, shape["template"])
        if shape["case"] == "lower":
            text = text.lower()
        elif shape["case"] == "upper":
            text = text.upper()
        toks = usaddress.tokenize(text) if text.strip() else []
        codes = spec.split("+")
        if codes == ["-"]:
            if toks:
                return None
        elif len(codes) == 1:
            codes = codes * len(toks)
        if codes != ["-"] and len(codes) != len(toks):
            return None
        pieces.append(text)
        labels += [(t, LABELS[c]) for t, c in zip(toks, codes)] if codes != ["-"] else []
    sep = lambda: " " * rng.choice([1, 1, 2, 3]) if shape["case"] == "spacey" else " "
    s = pieces[0]
    for p in pieces[1:]:
        s += sep() + p
    st = f.v.get("place", (None, None, None))[1] or (f.v.get("special") or (None, None))[1] or (f.v.get("mil") or (None, None))[1]
    if usaddress.tokenize(s) != [t for t, _ in labels]:
        return None
    return s, labels, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=75)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--training-dir", type=Path, default=B.LOCAL / "usaddress-training")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    shapes = parse_shapes()
    places = load_places(args.seed)
    single = [p for p in places if " " not in p[0]]
    if args.check:
        for sh in shapes:
            for _ in range(20):
                got = expand(sh, rng, places, single)
                if got:
                    s, labels, _ = got
                    print(f"{sh['tag']:28} {s}\n{'':28} " + " ".join(f"{t}/{(l or '-')[:7]}" for t, l in labels))
                    break
        return
    weight = sum(s["count"] for s in shapes)
    want = [round(s["count"] * args.total / weight) for s in shapes]
    want[want.index(max(want))] += args.total - sum(want)
    excl, _ = B.excluded_strings(args.training_dir)
    seen, recs, failed = set(), [], collections.Counter()
    for sh, n in zip(shapes, want):
        got_n, tries = 0, 0
        while got_n < n and tries < n * 60:
            tries += 1
            got = expand(sh, rng, places, single)
            if not got:
                failed[sh["tag"]] += 1
                continue
            s, labels, st = got
            k = B.norm(s)
            if k in excl or k in seen:
                continue
            seen.add(k)
            got_n += 1
            recs.append({"input": s, "tokens": [[t, l] for t, l in labels], "style": "hand", "mods": [], "type": sh["type"],
                         "state": st, "source": "hand", "tags": ["hand:" + sh["tag"]], "fields": None, "inputs": [s],
                         "expect": None, "usps": None})
        if got_n < n:
            print(f"short: {sh['tag']} {got_n}/{n}", file=sys.stderr)
    rng.shuffle(recs)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in recs))
    print(f"wrote {len(recs)} records to {OUT} from {len(shapes)} shapes; {sum(failed.values())} fills dropped by the token check")


if __name__ == "__main__":
    main()
