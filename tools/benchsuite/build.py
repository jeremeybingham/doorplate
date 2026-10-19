#!/usr/bin/env python3
"""Build the benchmark suite (#75, step 3): the two track files and MANIFEST.md.

    python tools/benchsuite/build.py                         # prints the plan
    python tools/benchsuite/build.py --confirm               # builds benchmarks/suite/v1/
    python tools/benchsuite/build.py --confirm --scale 0.05  # a small test build in local-data/
    python tools/benchsuite/build.py --confirm --twin        # the private twin (an unpublished seed)

Maintainers only: it reads `local-data/nad-2026/nad_r24.parquet` (tools/benchsuite/nad_parquet.py), the
TIGER feature names in `local-data/tiger-2024/` and the GeoNames postal codes in
`local-data/places/geonames-postal/`. The specification is docs/benchmark-suite.md; read it first.

What it does, in the order of the spec:
- keeps only NAD streets with at least 20 address points in their ZIP code, and replaces the house
  number, the unit value and the ZIP+4 with invented ones of the same shape (the anonymization rules)
- draws the `natural` stratum by state population and writes each record in a style with the weights
  of tools/benchsuite/inventory.py; PO boxes, routes, military and general delivery come from templates
  with a real city, state and ZIP; HI, MI, MS, NH, NV and PR have TIGER street names with invented numbers
- draws the `hard` stratum from candidates both libraries are run on: the quotas are in
  tools/benchsuite/hard_classes.json, and the classifier is the one the inventory used
- drops every string found in the exclusion files, and duplicates
- writes the gold token labels (from the field each token came from, never from a parser) to
  `compare.jsonl.gz`, and the fields, the styles, the Pub 28 components and the USPS lines to
  `doorplate.jsonl.gz`

The `hand` stratum is not built here: its records are hand-labeled and added from `hand.jsonl` beside the
output when that file exists. This library formats and parses; it does not validate that an address exists.
"""
import argparse
import collections
import contextlib
import datetime
import gzip
import hashlib
import json
import multiprocessing
import random
import re
import struct
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import duckdb
import usaddress

import doorplate

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402  (the renderer, the labels and the classifier)

NAD = ROOT / "local-data" / "nad-2026" / "nad_r24.parquet"
TIGER = ROOT / "local-data" / "tiger-2024"
GEONAMES = ROOT / "local-data" / "places" / "geonames-postal"
DATA = ROOT / "crates" / "doorplate" / "data"
LOCAL = ROOT / "local-data" / "benchsuite"
PUBLIC_SEED = 75001

# 2020 census populations in millions (rounded), the weight of a state in the `natural` stratum
POP = {
    "CA": 39.5, "TX": 29.1, "FL": 21.5, "NY": 20.2, "PA": 13.0, "IL": 12.8, "OH": 11.8, "GA": 10.7, "NC": 10.4,
    "MI": 10.1, "NJ": 9.3, "VA": 8.6, "WA": 7.7, "AZ": 7.2, "MA": 7.0, "TN": 6.9, "IN": 6.8, "MD": 6.2, "MO": 6.2,
    "WI": 5.9, "CO": 5.8, "MN": 5.7, "SC": 5.1, "AL": 5.0, "LA": 4.7, "KY": 4.5, "OR": 4.2, "OK": 4.0, "CT": 3.6,
    "UT": 3.3, "IA": 3.2, "NV": 3.1, "AR": 3.0, "MS": 3.0, "KS": 2.9, "NM": 2.1, "NE": 2.0, "ID": 1.8, "WV": 1.8,
    "HI": 1.5, "NH": 1.4, "ME": 1.4, "MT": 1.1, "RI": 1.1, "DE": 1.0, "SD": 0.9, "ND": 0.8, "AK": 0.7, "DC": 0.7,
    "VT": 0.6, "WY": 0.6, "PR": 3.3,
}
TIGER_FIPS = {"HI": "15", "MI": "26", "MS": "28", "NH": "33", "NV": "32", "PR": "72"}
TIGER_PER_STATE = 100  # the small floor that puts each of those states in the suite

NATURAL_SHARE, HARD_SHARE, HAND_SHARE = 0.80, 0.15, 0.05
TOTAL = 20000
# synthetic address types in the `natural` stratum (docs/benchmark-suite.md, the mix table)
SYNTH = {"po_box": 432, "rural": 50, "highway": 50, "military": 100, "general_delivery": 50}
ZIP4_SHARE = 0.08  # NAD has a ZIP+4 on 8.6% of rows
ENRICHED = ("AddNum_Pre <> '' or AddNum_Suf <> '' or St_PreMod <> '' or Unit <> '' or St_PosDir <> '' "
            "or St_PosMod <> '' or St_PreSep <> '' or position(' ' in Post_City) > 0")


# ---- tables from crates/doorplate/data (USPS Pub 28; data, not parser output) ------------------------

SUFFIX = DIRECTIONAL = UNITD = None  # filled in by load_tables


def load_tables():
    global SUFFIX, DIRECTIONAL, UNITD
    s = tomllib.loads((DATA / "suffixes.toml").read_text())["suffix"]
    SUFFIX = {f.upper(): e["abbr"] for e in s for f in e["forms"]}
    d = tomllib.loads((DATA / "directionals.toml").read_text())["directional"]
    DIRECTIONAL = {f.upper(): e["abbr"] for e in d for f in e["forms"]}
    u = tomllib.loads((DATA / "units.toml").read_text())["unit"]
    UNITD = {f.upper(): e["abbr"] for e in u for f in e["forms"]}


# ---- anonymization -------------------------------------------------------------------------------------

def invent(value, rng):
    """Replace each run of digits with random digits of the same length; never the same string."""
    if not re.search(r"\d", value or ""):
        return value
    for _ in range(20):
        out = re.sub(r"\d+", lambda m: "".join(
            str(rng.randint(1 if i == 0 else 0, 9)) for i in range(len(m.group()))), value)
        if out != value:
            return out
    return value


def anonymize(row, rng):
    row = dict(row)
    row["Add_Number"] = invent(row["Add_Number"], rng)
    row["Unit"] = invent(row["Unit"], rng)
    row["Plus_4"] = "".join(str(rng.randint(0, 9)) for _ in range(4)) if re.fullmatch(r"\d{4}", row["Plus_4"].strip()) else ""
    return row


# ---- records -------------------------------------------------------------------------------------------

PLACEHOLDER_CITY = {"NOT STATED", "UNKNOWN", "UNINCORPORATED", "NONE", "N/A", "NA", "NULL", "UNASSIGNED", "TBD", "NOT AVAILABLE"}
SPELLED_TYPES = {"STREET", "ROAD", "AVENUE", "DRIVE", "LANE", "BOULEVARD", "COURT", "CIRCLE", "PLACE", "TRAIL", "PARKWAY",
                 "HIGHWAY", "TERRACE", "ROUTE", "WAY"}
DIRECTION_WORDS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW", "NORTH", "SOUTH", "EAST", "WEST", "NORTHEAST",
                   "NORTHWEST", "SOUTHEAST", "SOUTHWEST"}
DESIGNATOR_GLUED = re.compile(r"^(APT|BLDG|BSMT|DEPT|FL|FRNT|HNGR|LBBY|LOT|LOWR|OFC|PH|RM|SPC|STE|TRLR|UNIT|UPPR)\d", re.I)


def provider_split(row):
    """True for a NAD row whose columns split the address in a way the label rules cannot trust.

    Generator rules, never single rows (docs/benchmark-suite.md, "Labels"): a street type or direction left
    inside the name, a city that is a placeholder or holds a comma or a street type, a house number of
    zeros, a unit that is a lone word or has its designator glued to the value."""
    g = lambda c: row[c].strip().upper()
    name = g("St_Name").split()
    if not name:
        return True
    if not g("St_PosTyp") and any(w in SUFFIX or w in SPELLED_TYPES for w in name[1:]):
        return True
    if g("St_PosTyp") and (name[-1] in SPELLED_TYPES or name[-1] in SUFFIX and len(name) > 1):
        return True  # `COLOGNA RD` + type `ROAD`
    if not g("St_PreDir") and name[0] in DIRECTION_WORDS and len(name) > 1:
        return True
    if not g("St_PosDir") and name[-1] in DIRECTION_WORDS and len(name) > 1:
        return True
    if re.fullmatch(r"0+", g("Add_Number")):
        return True
    if not g("St_PosTyp") and any(ch.isdigit() for ch in g("St_Name")):
        return True  # `HWY 87`, `CR 870A`: a route with no type column
    city = g("Post_City")
    if city in PLACEHOLDER_CITY or not re.fullmatch(r"[A-Z][A-Z .'\-]*", city) or set(city.split()) & SPELLED_TYPES:
        return True
    unit = g("Unit").split()
    if g("St_PosMod") or (len(unit) > 1 and any(w.rstrip(".") in I.DESIGNATOR_WORDS for w in unit[1:])):
        return True  # a post-modifier after the type, or a designator repeated inside the unit (`UNIT UNIT 604`)
    if "/" in g("Unit") or re.search(r"\d[A-Z]{2,}", g("Unit")):
        return True
    ident = unit[1:] if unit and re.fullmatch(r"[A-Z]+\.?", unit[0]) and len(unit) > 1 else unit
    if ident and not any(re.search(r"\d", w) or len(w.strip("#")) <= 2 for w in ident):
        return True  # an identifier that is a word (`MAIN`, `REAR`)
    if len(unit) == 1 and DESIGNATOR_GLUED.match(unit[0]):
        return True
    if len(unit) == 1 and not unit[0].startswith("#") and not re.search(r"\d", unit[0]) and len(unit[0]) > 2:
        return True
    return False


def good_city(city):
    return city not in PLACEHOLDER_CITY and bool(re.fullmatch(r"[A-Z][A-Z .'\-]*", city)) and not set(city.split()) & SPELLED_TYPES


def tidy_number(row):
    """Merge a hyphenated prefix or suffix into the house number (`171-` + `49` is `171-49`); None for
    prefixes and suffixes the label rules do not cover (a digit-only prefix, a word, `<NULL>`)."""
    row = dict(row)
    pre, suf, num = row["AddNum_Pre"].strip().upper(), row["AddNum_Suf"].strip().upper(), row["Add_Number"].strip()
    if pre.endswith("-") and re.fullmatch(r"\d+-", pre):
        num, pre = pre + num, ""
    if suf.startswith("-") and re.fullmatch(r"-\d+", suf):
        num, suf = num + suf, ""
    if pre and not re.fullmatch(r"[A-Z]{1,2}", pre):
        return None
    if suf and not (re.fullmatch(r"[A-DF-MO-RT-VX-Z]", suf) or re.fullmatch(r"\d/\d", suf)):
        return None  # a suffix letter that is a compass letter (`42301 N MEQUON`) reads as a predirectional
    if re.search(r"[<>]|\bNULL\b", " ".join(str(v).upper() for v in row.values())):
        return None
    row.update({"AddNum_Pre": pre, "AddNum_Suf": suf, "Add_Number": num})
    return row


def nad_record(row, rng):
    """A structured record from one NAD row (anonymized), or None."""
    row = tidy_number(row)
    if row is None:
        return None
    if row["Building"].strip() or provider_split(row):
        return None  # building names are out of v1
    row = anonymize(row, rng)
    row["Add_Number"] = row["Add_Number"] if re.fullmatch(r"[0-9A-Za-z\-/]+", row["Add_Number"]) else ""
    rec = I.record_from_row(row)
    if rec is None:
        return None
    g = lambda c: row[c].strip().upper()
    plain = not any(g(c) for c in ("AddNum_Pre", "AddNum_Suf", "St_PreMod", "St_PreTyp", "St_PreSep", "St_PosMod"))
    rec.update({"type": "street", "source": "nad", "plain": plain, "parts": {
        "number": g("Add_Number"), "predir": g("St_PreDir"), "name": g("St_Name"), "suffix": g("St_PosTyp"),
        "postdir": g("St_PosDir")}})
    return rec


def num_shape(rng):
    n = rng.choices([1, 2, 3, 4, 5], [6, 22, 32, 30, 10])[0]
    return "".join(str(rng.randint(1 if i == 0 else 0, 9)) for i in range(n))


def street_rec(number, predir, name, suffix, postdir, city, state, zip5, source, rng, unit_p=0.10):
    street = [(number, "AddressNumber")]
    street += [(predir, "StreetNamePreDirectional")] if predir else []
    street += [(w, "StreetName") for w in name.split()]
    street += [(suffix, "StreetNamePostType")] if suffix else []
    street += [(postdir, "StreetNamePostDirectional")] if postdir else []
    unit = []
    if rng.random() < unit_p:
        unit = [(rng.choice(["APT", "STE", "UNIT"]), "OccupancyType"), (num_shape(rng)[:3], "OccupancyIdentifier")]
    return {"street": street, "building": [], "unit": unit, "city": city, "state": state, "zip": zip5,
            "plus4": "".join(str(rng.randint(0, 9)) for _ in range(4)), "has_unit": bool(unit), "has_building": False,
            "type": "street", "source": source, "plain": True,
            "parts": {"number": number, "predir": predir, "name": name, "suffix": suffix, "postdir": postdir}}


def dbf_rows(blob):
    """The rows of a dBASE III file as dicts of strings (the TIGER feature names)."""
    n, hlen, rlen = struct.unpack("<IHH", blob[4:12])
    fields, off = [], 32
    while blob[off] != 0x0D:
        fields.append((blob[off:off + 11].split(b"\0")[0].decode(), blob[off + 16]))
        off += 32
    for i in range(n):
        rec = blob[hlen + i * rlen: hlen + (i + 1) * rlen]
        pos, row = 1, {}
        for name, ln in fields:
            row[name] = rec[pos:pos + ln].decode("latin-1").strip()
            pos += ln
        yield row


def tiger_streets(state, rng, want):
    """(predir, name, suffix, postdir) of local roads of one state, from the TIGER county files."""
    seen = set()
    for z in sorted(TIGER.glob(f"tl_2024_{TIGER_FIPS[state]}*_featnames.zip")):
        with zipfile.ZipFile(z) as zf:
            blob = zf.read(next(n for n in zf.namelist() if n.endswith(".dbf")))
        for r in dbf_rows(blob):
            if r.get("MTFCC") not in ("S1400", "S1200") or r["PRETYPABRV"] or r["PREQUALABR"] or r["SUFQUALABR"]:
                continue
            if not r["NAME"] or not r["SUFTYPABRV"] or not re.fullmatch(r"[A-Za-z0-9' -]+", r["NAME"]):
                continue
            seen.add((r["PREDIRABRV"].upper(), r["NAME"].upper(), r["SUFTYPABRV"].upper(), r["SUFDIRABRV"].upper()))
    seen = sorted(seen)
    rng.shuffle(seen)
    return seen[:want * 3]


def geonames_places(state):
    """(place, zip) pairs of one state from the GeoNames postal codes (CC BY 4.0, attributed in NOTICE)."""
    path = GEONAMES / ("pr/PR.txt" if state == "PR" else "us/US.txt")
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) > 4 and (f[4] == state or state == "PR"):
            out.append((f[2].upper(), f[1]))
    return out


# ---- synthetic address types ---------------------------------------------------------------------------

def synth_rec(kind, place, rng):
    """A record of one of the shapes NAD has no rows for. `place` is (city, state, zip) from NAD."""
    city, state, zip5 = place
    base = {"building": [], "unit": [], "city": city, "state": state, "zip": zip5, "plus4": "", "has_unit": False,
            "has_building": False, "type": kind, "source": "synthetic", "plain": False, "parts": {}}
    box = str(rng.randint(1, 99999 if rng.random() < 0.3 else 9999))
    if kind == "po_box":
        form = rng.choices([("PO", "BOX"), ("P.O.", "BOX"), ("POST", "OFFICE", "BOX")], [70, 20, 10])[0]
        base["street"] = [(w, "USPSBoxType") for w in form] + [(box, "USPSBoxID")]
        base["synth"] = {"po_box": box, "usps": "PO BOX " + box}
    elif kind in ("rural", "highway"):
        grp = rng.choice(["RR", "RR", "RURAL ROUTE"]) if kind == "rural" else rng.choice(["HC", "HC", "HCR"])
        route = str(rng.randint(1, 99))
        base["street"] = [(w, "USPSBoxGroupType") for w in grp.split()] + [(route, "USPSBoxGroupID"),
                                                                           ("BOX", "USPSBoxType"), (box, "USPSBoxID")]
        k = "RR" if kind == "rural" else "HC"
        base["synth"] = {"rural_route": {"kind": k, "route": route, "box": box}, "usps": f"{k} {route} BOX {box}"}
    elif kind == "military":
        mk = rng.choice(["PSC", "PSC", "UNIT", "CMR"])
        number, post = str(rng.randint(1, 9999)), rng.choice(["APO", "APO", "FPO", "DPO"])
        st, zz = rng.choice([("AE", 9000), ("AE", 9100), ("AP", 96200), ("AA", 34000)])
        zz = f"{zz + rng.randint(0, 99):05d}"
        base.update({"city": post, "state": st, "zip": zz})
        base["street"] = [(mk, "USPSBoxGroupType"), (number, "USPSBoxGroupID"), ("BOX", "USPSBoxType"), (box, "USPSBoxID")]
        base["synth"] = {"military": {"kind": mk, "number": number, "box": box}, "military_post_office": post,
                         "usps": f"{mk} {number} BOX {box}"}
    else:  # general delivery
        base["street"] = [("GENERAL", "USPSBoxType"), ("DELIVERY", "USPSBoxType")]
        base["synth"] = {"general_delivery": True, "usps": "GENERAL DELIVERY"}
    return base


# ---- rendering and the doorplate track -----------------------------------------------------------------

@contextlib.contextmanager
def only(style):
    """Render in exactly one style and with no modifiers (the `inputs` of the key-stability measure)."""
    weights, mods = I.STYLE_WEIGHTS, I.MODIFIERS
    I.STYLE_WEIGHTS, I.MODIFIERS = {style: 1.0}, {k: 0.0 for k in mods}
    try:
        yield
    finally:
        I.STYLE_WEIGHTS, I.MODIFIERS = weights, mods


KEEP_UPPER = {"PSC", "CMR", "UNIT", "APO", "FPO", "DPO", "HC", "HCR", "RR", "PO", "P.O.", "AE", "AP", "AA"}
_cap = I.cap


def cap(w):
    return w if w.upper() in KEEP_UPPER or re.fullmatch(r"(?:[A-Za-z]\.)+", w) else _cap(w)


I.cap = cap


def render_record(rec, rng):
    I.MODIFIERS["zip4"] = ZIP4_SHARE
    s, out, style, mods = I.render(rec, rng)
    return {"input": s, "tokens": [[t, l] for t, l in I.gold_tokens(out)], "style": style, "mods": mods}


def components(rec, mods, rng):
    """The doorplate-track fields, Pub 28 components and USPS lines for one record (never from a parser)."""
    zip4 = rec["plus4"] if "zip4" in mods and rec["plus4"] else ""
    street_words = " ".join(w for w, _ in rec["street"])
    unit_words = " ".join(w for w, _ in rec["unit"])
    if rec["type"] != "street":
        fields = {"line1": street_words, "line2": None, "city": rec["city"], "state": rec["state"], "zip": rec["zip"]}
        sy = rec["synth"]
        expect = {k: v for k, v in sy.items() if k != "usps"}
        expect.update({"city": rec["city"], "state": rec["state"], "zip5": rec["zip"]})
        return fields, expect, {"delivery": sy["usps"], "last": f"{rec['city']} {rec['state']} {rec['zip']}"}
    fields = {"line1": street_words, "line2": unit_words or None, "city": rec["city"], "state": rec["state"],
              "zip": rec["zip"] + ("-" + zip4 if zip4 else "")}
    if not rec["plain"]:
        return fields, None, None
    p = rec["parts"]
    suffix = SUFFIX.get(p["suffix"]) if p["suffix"] else None
    predir = DIRECTIONAL.get(p["predir"]) if p["predir"] else None
    postdir = DIRECTIONAL.get(p["postdir"]) if p["postdir"] else None
    if (p["suffix"] and not suffix) or (p["predir"] and not predir) or (p["postdir"] and not postdir):
        return fields, None, None
    name = re.sub(r"[.,']", "", p["name"]).strip()  # Pub 28 omits punctuation but hyphens and fractions
    expect = {"street_number": p["number"], "street_name": name, "city": rec["city"], "state": rec["state"],
              "zip5": rec["zip"]}
    for k, v in (("street_dir_prefix", predir), ("street_suffix", suffix), ("street_dir_suffix", postdir)):
        if v:
            expect[k] = v
    if zip4:
        expect["zip4"] = zip4
    usps_unit = ""
    if rec["unit"]:
        first = rec["unit"][0]
        if first[1] == "OccupancyType":
            ut = UNITD.get(first[0].rstrip(".").upper())
            if not ut:
                return fields, None, None
            expect["unit_type"] = ut
            expect["unit_number"] = " ".join(w for w, _ in rec["unit"][1:])
            usps_unit = f"{ut} {expect['unit_number']}"
        else:
            expect["unit_number"] = " ".join(w for w, l in rec["unit"] if w != "#")
    usps = None
    if not rec["unit"] or usps_unit:
        line = " ".join(x for x in (p["number"], predir, name, suffix, postdir, usps_unit) if x)
        usps = {"delivery": line, "last": f"{rec['city']} {rec['state']} {rec['zip']}" + (f"-{zip4}" if zip4 else "")}
    return fields, expect, usps


def other_inputs(rec, first_style, rng, count):
    """Two to four renderings of the record in different styles, for the key stability measure."""
    names = [s for s in I.STYLE_WEIGHTS if s != first_style]
    rng.shuffle(names)
    outs = []
    for style in names[: max(1, count - 1)]:
        with only(style):
            outs.append(I.render(rec, rng)[0])
    return outs


# ---- exclusions ----------------------------------------------------------------------------------------

def norm(s):
    return " ".join(s.split()).lower()


def excluded_strings(training_dir):
    """The normalized strings the suite must not contain, and a note on what was read."""
    seen, notes = set(), []
    pat = re.compile(r"<AddressString>(.*?)</AddressString>", re.S)
    import html

    def xml(path):
        for m in pat.finditer(Path(path).read_text(encoding="utf-8", errors="replace")):
            seen.add(norm(html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))))

    for label, files in (("usaddress test files", (ROOT / "tests" / "external" / "usaddress").glob("*.xml")),
                         ("geocode benchmark splits", (ROOT / "local-data" / "geocode-benchmark").glob("*_usaddress.xml")),
                         ("usaddress training files", training_dir.glob("*.xml") if training_dir.exists() else [])):
        before = len(seen)
        for f in files:
            xml(f)
        notes.append((label, len(seen) - before))
    before = len(seen)
    for f in (ROOT / "tests" / "corpus").glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if "input" in r:
                    seen.add(norm(r["input"]))
                elif "lines" in r:
                    seen.add(norm(", ".join(r["lines"])))
    notes.append(("golden corpus and Pub 28 examples", len(seen) - before))
    return seen, notes


# ---- the build -----------------------------------------------------------------------------------------

NAD_COLUMNS = ("State,AddNum_Pre,Add_Number,AddNum_Suf,AddNo_Full,St_PreMod,St_PreDir,St_PreTyp,St_PreSep,St_Name,"
               "St_PosTyp,St_PosDir,St_PosMod,StNam_Full,Building,Floor,Unit,Room,SubAddress,Post_City,Zip_Code,Plus_4,"
               "NAD_Source")
JOIN = f"""from '{NAD}' n join common c on c.State = n.State and c.Zip_Code = n.Zip_Code and c.StNam_Full = n.StNam_Full"""
HASH = "hash(n.Add_Number, n.StNam_Full, n.Zip_Code, n.Unit, n.Post_City, {seed}) % 1000000"


def counts_by_state(con, where=""):
    return dict(con.execute(f"select n.State, count(*) {JOIN} where n.Add_Number <> '' {where} group by 1").fetchall())


def hashed_rows(con, where, fractions, seed):
    """Rows chosen by a hash of their own values (not by thread timing), so the same seed gives the same
    rows on every run: each state keeps the share `fractions[state]` (0 to 1) of its usable rows."""
    con.execute("create or replace table frac(State varchar, p double)")
    con.executemany("insert into frac values (?, ?)", list(fractions.items()))
    h = HASH.format(seed=seed)
    q = f"""select {', '.join('n.' + c for c in NAD_COLUMNS.split(','))}, {h} as h {JOIN}
            join frac f on f.State = n.State
            where n.Add_Number <> '' {where} and {h} < f.p * 1000000
            order by h, {', '.join('n.' + c for c in NAD_COLUMNS.split(','))}"""
    return con.execute(q).fetchdf().fillna("").to_dict("records")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--scale", type=float, default=1.0, help="a fraction of the full size (tests)")
    ap.add_argument("--twin", action="store_true", help="the private twin: seed from local-data/benchsuite/TWIN_SEED")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--training-dir", type=Path, default=LOCAL / "usaddress-training")
    args = ap.parse_args()
    load_tables()

    if args.twin:
        seed_file = LOCAL / "TWIN_SEED"
        if not seed_file.exists():
            seed_file.parent.mkdir(parents=True, exist_ok=True)
            seed_file.write_text(str(random.SystemRandom().randint(10**8, 10**9)))
        seed = int(seed_file.read_text())
    else:
        seed = PUBLIC_SEED
    out_dir = args.out or (LOCAL / "twin" if args.twin else (ROOT / "benchmarks" / "suite" / "v1" if args.scale == 1.0
                                                           else LOCAL / f"test-{args.scale}"))
    total = round(TOTAL * args.scale)
    n_hard = round(total * HARD_SHARE)
    n_nat = round(total * NATURAL_SHARE)
    synth = {k: max(2, round(v * args.scale)) for k, v in SYNTH.items()}
    n_tiger = {s: max(2, round(TIGER_PER_STATE * args.scale)) for s in TIGER_FIPS}
    n_nad = n_nat - sum(synth.values()) - sum(n_tiger.values())
    cand = round(600_000 * args.scale)
    print(f"plan\n  read     {NAD.name}, {TIGER.name}, {GEONAMES.name}, the exclusion files\n"
          f"  write    {out_dir} (compare.jsonl.gz, doorplate.jsonl.gz, MANIFEST.md; under 10 MB)\n"
          f"  records  {n_nat} natural ({n_nad} NAD, {sum(n_tiger.values())} TIGER, {sum(synth.values())} synthetic) "
          f"+ {n_hard} hard from {cand:,} candidates; {'the private twin (seed kept in local-data/)' if args.twin else f'seed {seed}'}\n"
          f"  time     about {max(1, round(6 * args.scale))} minutes ({args.workers} workers)")
    if not args.confirm:
        sys.exit("Dry run. Re-run with --confirm to start.")

    rng = random.Random(seed)
    excl, excl_notes = excluded_strings(args.training_dir)
    con = duckdb.connect()
    con.execute("set threads=4")
    con.execute(f"""create table common as select State, Zip_Code, StNam_Full from '{NAD}'
        where Add_Number <> '' and StNam_Full <> '' and Post_City <> '' and length(Zip_Code) = 5
        group by all having count(*) >= 20""")
    nad_states = {s: w for s, w in POP.items() if s not in TIGER_FIPS}
    tot_pop = sum(nad_states.values())
    quota = {s: round(n_nad * w / tot_pop) for s, w in nad_states.items()}
    usable = counts_by_state(con)
    # a pool 12 times each state's quota (the filters drop about 15%, and a short state hands its need on)
    pool = hashed_rows(con, "", {s: min(1.0, 12 * max(q, 5) / usable[s]) for s, q in quota.items() if s in usable}, seed)
    pool_all = [r for r in pool]
    total_usable = sum(usable.values())
    uniform = hashed_rows(con, "", {s: min(1.0, cand / 2 / total_usable) for s in usable}, seed + 1)
    enr_counts = counts_by_state(con, f"and ({ENRICHED})")
    enr_total = sum(enr_counts.values())
    enriched = hashed_rows(con, f"and ({ENRICHED})", {s: min(1.0, cand / 2 / enr_total) for s in enr_counts}, seed + 2)
    rng.shuffle(pool)
    rng.shuffle(uniform)
    rng.shuffle(enriched)

    taken, recs = set(), []

    def keep(rec, stratum, tags):
        r = render_record(rec, rng)
        k = norm(r["input"])
        if k in excl or k in taken:
            return None
        taken.add(k)
        fields, expect, usps = components(rec, r["mods"], rng)
        extra = other_inputs(rec, r["style"], rng, rng.randint(2, 4))
        item = {"stratum": stratum, "tags": tags, "rec": rec, "r": r, "fields": fields, "expect": expect, "usps": usps,
                "inputs": [r["input"]] + extra}
        recs.append(item)
        return item

    # natural: NAD streets by state population; a state short of rows hands its need to the others
    by_state = collections.defaultdict(list)
    for row in pool:
        by_state[row["State"]].append(row)
    cursor = {st: iter(rows) for st, rows in by_state.items()}
    got = collections.Counter()

    per_city, per_street = collections.Counter(), collections.Counter()
    city_cap = max(3, round(0.005 * n_nad))  # no city is more than 0.5% of the NAD records; no street more than twice

    def take(state, n):
        done = 0
        for row in cursor.get(state, ()):
            ck = (state, row["Post_City"].strip().upper())
            sk = (state, row["Zip_Code"], row["StNam_Full"].strip().upper())
            if per_city[ck] >= city_cap or per_street[sk] >= 2:
                continue
            rec = nad_record(row, rng)
            if rec and keep(rec, "natural", []):
                per_city[ck] += 1
                per_street[sk] += 1
                done += 1
                if done >= n:
                    return done
        return done

    for state in sorted(nad_states):
        got[state] = take(state, quota[state])
    short = {}
    for _ in range(4):
        need = n_nad - sum(got.values())
        live = {st: w for st, w in nad_states.items() if st in cursor and got[st] >= quota[st]}
        if need <= 0 or not live:
            break
        lw = sum(live.values())
        for state, w in sorted(live.items()):
            got[state] += take(state, max(1, round(need * w / lw)))
    short = {st: quota[st] - got[st] for st in nad_states if got[st] < quota[st]}
    nat_places = []
    # synthetic types use the real city, state and ZIP of NAD rows
    place_rows = [r for r in pool if good_city(r["Post_City"].strip().upper()) and re.fullmatch(r"\d{5}", r["Zip_Code"])]
    for kind, n in synth.items():
        got = 0
        while got < n:
            row = rng.choice(place_rows)
            rec = synth_rec(kind, (row["Post_City"].strip().upper(), row["State"], row["Zip_Code"]), rng)
            if keep(rec, "natural", []):
                got += 1
    for state, n in n_tiger.items():
        places = geonames_places(state)
        got = 0
        for predir, name, suffix, postdir in tiger_streets(state, rng, n):
            if got >= n:
                break
            city, zip5 = rng.choice(places)
            rec = street_rec(num_shape(rng), predir, name, suffix, postdir, city, state, zip5, "tiger", rng)
            if keep(rec, "natural", []):
                got += 1

    # hard: candidates both libraries are run on
    quotas = {c["class"]: c["quota"] for c in json.loads((HERE / "hard_classes.json").read_text())["classes"]}
    scale_q = n_hard / sum(quotas.values())
    quotas = {c: max(2, round(q * scale_q)) for c, q in quotas.items()}
    rows = enriched[: cand // 2] + uniform[: cand // 2]
    cands = []
    for row in rows:
        rec = nad_record(row, rng)
        if rec is None:
            continue
        r = render_record(rec, rng)
        k = norm(r["input"])
        if k in excl or k in taken:
            continue
        cands.append((rec, r))
    inputs = [r["input"] for _, r in cands]
    with multiprocessing.Pool(args.workers) as p:
        ours = p.map(I.parse_ours, inputs, chunksize=2000)
        theirs = p.map(I.parse_theirs, inputs, chunksize=2000)
    qualify = collections.defaultdict(list)
    classes_of = {}
    for i, ((rec, r), a, b) in enumerate(zip(cands, ours, theirs)):
        gold = [(t, l) for t, l in r["tokens"]]
        hit = set()
        for pred in (a, b):
            first = I.compare(gold, pred)
            if first and first[0] != "misaligned":
                c = f"{first[1]} -> {first[2]}"
                if c in quotas:
                    hit.add(c)
        classes_of[i] = sorted(hit)
        for c in hit:
            qualify[c].append(i)
    used, achieved = set(), {}
    for c in sorted(quotas, key=lambda c: len(qualify[c])):
        order = [i for i in qualify[c] if i not in used]
        rng.shuffle(order)
        take = order[: quotas[c]]
        achieved[c] = len(take)
        for i in take:
            used.add(i)
            rec, r = cands[i]
            item = {"stratum": "hard", "tags": classes_of[i], "rec": rec, "r": r}
            fields, expect, usps = components(rec, r["mods"], rng)
            item.update({"fields": fields, "expect": expect, "usps": usps,
                         "inputs": [r["input"]] + other_inputs(rec, r["style"], rng, rng.randint(2, 4))})
            taken.add(norm(r["input"]))
            recs.append(item)

    hand = HERE / "hand" / "hand.jsonl"
    hand_n = 0
    if hand.exists():
        for line in hand.read_text().splitlines()[: round(1000 * args.scale)]:
            if line.strip():
                recs.append({"hand": json.loads(line)})
                hand_n += 1

    rng.shuffle(recs)
    out_dir.mkdir(parents=True, exist_ok=True)
    compare, dp = [], []
    for n, item in enumerate(recs, 1):
        rid = f"v1-{n:06d}"
        if "hand" in item:
            h = item["hand"]
            compare.append({"id": rid, **{k: h[k] for k in ("input", "tokens", "style", "mods", "type", "state", "source", "tags")},
                            "stratum": "hand"})
            dp.append({"id": rid, "stratum": "hand", **{k: h.get(k) for k in ("type", "state", "source", "tags", "fields",
                                                                                "inputs", "expect", "usps")}})
            continue
        rec, r = item["rec"], item["r"]
        common = {"stratum": item["stratum"], "type": rec["type"], "state": rec["state"], "source": rec["source"],
                  "tags": item["tags"]}
        compare.append({"id": rid, "input": r["input"], "tokens": r["tokens"], "style": r["style"], "mods": r["mods"], **common})
        dp.append({"id": rid, **common, "fields": item["fields"], "inputs": item["inputs"], "expect": item["expect"],
                   "usps": item["usps"]})
    files = {}
    for name, rows_ in (("compare.jsonl.gz", compare), ("doorplate.jsonl.gz", dp)):
        path = out_dir / name
        with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            for row in rows_:
                gz.write((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode())
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    manifest(out_dir, compare, dp, files, achieved, quotas, short, excl_notes, seed, args, hand_n)
    print(f"wrote {len(compare):,} records to {out_dir}")


def manifest(out_dir, compare, dp, files, achieved, quotas, short, excl_notes, seed, args, hand_n):
    def table(title, key, rows):
        c = collections.Counter(key(r) for r in rows)
        return [f"## {title}", "", "| Value | Records |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in sorted(c.items())] + [""]

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    expect_n = sum(1 for r in dp if r.get("expect"))
    usps_n = sum(1 for r in dp if r.get("usps"))
    lines = [f"# Suite v1: manifest", "", f"Built {datetime.date.today()} by `tools/benchsuite/build.py` at commit `{commit}`"
             f"{' (a test build: scale ' + str(args.scale) + ')' if args.scale != 1.0 else ''}"
             f"{' (the private twin)' if args.twin else ''}; {'seed ' + str(seed) if not args.twin else 'its seed is not published'}. usaddress {usaddress.__version__ if hasattr(usaddress, '__version__') else '0.5.16'}.", "",
             f"{len(compare):,} records, of which {hand_n} hand-labeled. `expect` is set on {expect_n:,} records and `usps` on {usps_n:,}"
             " (records with a number prefix or suffix, a premodifier, a pre-type or a post-modifier have neither).", ""]
    lines += ["## Checksums (SHA-256 of the gzip files)", ""] + [f"- `{n}`: `{h}`" for n, h in files.items()] + [""]
    lines += table("By stratum", lambda r: r["stratum"], compare)
    lines += table("By style", lambda r: r.get("style", "(none)"), compare)
    lines += table("By address type", lambda r: r["type"], compare)
    lines += table("By source", lambda r: r["source"], compare)
    lines += table("By state", lambda r: r["state"], compare)
    lines += ["## Hard classes", "", "| Class | Quota | Built |", "|---|---|---|"]
    lines += [f"| {c} | {quotas[c]} | {achieved.get(c, 0)} |" for c in sorted(quotas, key=lambda c: -quotas[c])] + [""]
    if short:
        lines += ["## States short of their natural quota", ""] + [f"- {s}: {n} short" for s, n in sorted(short.items())] + [""]
    lines += ["## Exclusions applied", ""] + [f"- {label}: {n:,} strings" for label, n in excl_notes] + [""]
    (out_dir / "MANIFEST.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
