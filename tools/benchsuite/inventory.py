#!/usr/bin/env python3
"""Step 2 of the benchmark suite (#75), part 2: where each library goes wrong, as counts.

    python tools/benchsuite/inventory.py [--records 200000] [--seed 75] [--out DIR]

Draws records from the NAD sample (`local-data/nad-2026/sample1m.parquet`), writes each in one style
(docs/benchmark-suite.md, "Styles"), labels every token from the NAD column it came from (never from a
parser), runs doorplate and usaddress on the strings, and sorts the records either one gets wrong
into classes with one classifier. It prints counts and rates only, never a record; the rows stay in
memory (docs/data-policy.md). The output fills in the hard-stratum table of docs/benchmark-suite.md.

The classifier looks only at the gold and the predicted labels, so both libraries are sorted the same
way: a wrong record belongs to the class of its first token whose coarse label (street parts folded
into StreetName, as in tools/compare/compare_usaddress.py) differs from the gold, written
`gold -> predicted`. A record that either library cannot align token for token is its own class.

This library formats and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import collections
import json
import math
import multiprocessing
import random
import re
import sys
from pathlib import Path

import pandas as pd
import usaddress

import doorplate

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "compare"))
from compare_usaddress import OUT_OF_SCOPE, coarse, norm, scored  # noqa: E402

SAMPLE = ROOT / "local-data" / "nad-2026" / "sample1m.parquet"

# usaddress labels for the NAD columns (docs/benchmark-suite.md, "Labels")
STREET_COLUMNS = [
    ("AddNum_Pre", "AddressNumberPrefix"), ("Add_Number", "AddressNumber"), ("AddNum_Suf", "AddressNumberSuffix"),
    ("St_PreMod", "StreetNamePreModifier"), ("St_PreDir", "StreetNamePreDirectional"),
    ("St_PreTyp", "StreetNamePreType"), ("St_PreSep", "StreetName"), ("St_Name", "StreetName"),
    ("St_PosTyp", "StreetNamePostType"), ("St_PosDir", "StreetNamePostDirectional"), ("St_PosMod", "StreetName"),
]

# Pub 28 Appendix C2 designators (USPS data), the abbreviation and the spelled-out form
DESIGNATORS = {
    "APT": "APARTMENT", "BLDG": "BUILDING", "BSMT": "BASEMENT", "DEPT": "DEPARTMENT", "FL": "FLOOR", "FRNT": "FRONT",
    "HNGR": "HANGAR", "LBBY": "LOBBY", "LOT": "LOT", "LOWR": "LOWER", "OFC": "OFFICE", "PH": "PENTHOUSE",
    "RM": "ROOM", "SPC": "SPACE", "STE": "SUITE", "TRLR": "TRAILER", "UNIT": "UNIT", "UPPR": "UPPER",
}
DESIGNATOR_WORDS = set(DESIGNATORS) | set(DESIGNATORS.values())
TYPES = {
    "ST": "STREET", "AVE": "AVENUE", "RD": "ROAD", "DR": "DRIVE", "LN": "LANE", "CT": "COURT", "BLVD": "BOULEVARD",
    "PL": "PLACE", "CIR": "CIRCLE", "TRL": "TRAIL", "PKWY": "PARKWAY", "HWY": "HIGHWAY", "TER": "TERRACE", "WAY": "WAY",
    "LOOP": "LOOP", "PT": "POINT", "XING": "CROSSING", "SQ": "SQUARE", "ALY": "ALLEY", "BND": "BEND", "PIKE": "PIKE",
}
DIRS = {"N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST", "NE": "NORTHEAST", "NW": "NORTHWEST",
        "SE": "SOUTHEAST", "SW": "SOUTHWEST"}
# a street name whose last word is one of these, with no type column, is probably a provider split
SUFFIX_WORDS = set(TYPES) | set(TYPES.values()) | {"BLV", "BVD", "HIGHWAY", "FWY", "EXPY", "PKY", "TRCE", "RUN", "PATH", "ROW"}

# Style weights: a starting point for the sign-off, not a measurement. The local sources are almost
# all uppercase (shapes.py: 99% of the DBPR and Netsyms line 1s), so how often people write mixed case
# cannot be measured here. Per-style error rates are printed too, so a different mix is arithmetic.
STYLE_WEIGHTS = {
    "upper-commas": 0.30, "mixed-commas": 0.20, "upper-nocommas": 0.25, "spelled-out": 0.15, "mixed-nocommas": 0.10,
}
# Modifiers, each applied to a share of the records; the unit form (designator, `#` or bare) is
# whatever the NAD provider wrote, with `#` forced on a share of the designator forms.
MODIFIERS = {"hash-unit": 0.10, "zip4": 0.0, "no-zip": 0.03, "no-state": 0.02, "noise": 0.05, "extra-text": 0.03}


def words(value):
    return [w for w in re.split(r"\s+", (value or "").strip()) if w]


def unit_words(unit):
    """[(word, label)] for a NAD Unit value, or None when its form is not one the rules cover."""
    ws = words(unit)
    if not ws:
        return []
    first = ws[0].rstrip(".").upper()
    if ws[0].startswith("#"):
        rest = [ws[0][1:]] if len(ws[0]) > 1 else []
        return [("#", "OccupancyIdentifier")] + [(w, "OccupancyIdentifier") for w in rest + ws[1:]]
    if first in DESIGNATOR_WORDS:
        if len(ws) == 1:
            return None
        return [(ws[0], "OccupancyType")] + [(w, "OccupancyIdentifier") for w in ws[1:]]
    if len(ws) == 1:
        return [(ws[0], "OccupancyIdentifier")]
    return None


def record_from_row(r):
    """The structured record, or None when the row is not usable (a provider split, an odd unit)."""
    g = lambda c: (r[c] or "").strip().upper()  # NAD is about half mixed case; the style decides the case
    if not (g("Add_Number") and g("St_Name") and g("Post_City") and re.fullmatch(r"[A-Z]{2}", g("State"))
            and re.fullmatch(r"\d{5}", g("Zip_Code"))):
        return None
    if not g("St_PosTyp") and words(g("St_Name"))[-1].upper() in SUFFIX_WORDS:
        return None  # the provider probably left the type inside the name; the label audit decides
    if g("Floor") or g("Room"):
        return None  # no rule for how a floor or a room is written yet; counted by shapes.py
    if g("Add_Number") and not re.fullmatch(r"[0-9A-Za-z\-/]+", g("Add_Number")):
        return None
    street = [(w, lab) for col, lab in STREET_COLUMNS for w in words(g(col))]
    unit = unit_words(g("Unit")) if g("Unit") else []
    if unit is None:
        return None
    building = [(w, "BuildingName") for w in words(g("Building"))]
    if any(not any(ch.isalnum() for ch in w) for w, _ in street + building):
        return None
    return {"street": street, "building": building, "unit": unit, "city": g("Post_City"), "state": g("State"),
            "zip": g("Zip_Code"), "plus4": g("Plus_4") if re.fullmatch(r"\d{4}", g("Plus_4")) else "",
            "has_unit": bool(unit), "has_building": bool(building)}


def cap(w):
    """Title-case a word: `5TH` -> `5th`, `MC` -> `Mc`."""
    if not any(c.isalpha() for c in w):
        return w
    if re.fullmatch(r"\d+[A-Z]{1,2}", w):
        return w[:-2] + w[-2:].lower() if len(w) > 2 else w
    return w[0].upper() + w[1:].lower()


def pick_style(rng):
    x, acc = rng.random(), 0.0
    for name, w in STYLE_WEIGHTS.items():
        acc += w
        if x < acc:
            return name
    return "upper-commas"


def render(rec, rng):
    """(string, [(word, label)], style, modifiers) for one record."""
    style = pick_style(rng)
    mods = [m for m, p in MODIFIERS.items() if rng.random() < p]
    spelled = style == "spelled-out"
    commas = style in ("upper-commas", "mixed-commas", "spelled-out")
    mixed = style in ("mixed-commas", "mixed-nocommas")

    def spell(w, lab):
        u = w.rstrip(".").upper()
        if spelled and lab in ("StreetNamePostType", "StreetNamePreType") and u in TYPES:
            return TYPES[u]
        if spelled and lab in ("StreetNamePreDirectional", "StreetNamePostDirectional") and u in DIRS:
            return DIRS[u]
        if spelled and lab == "OccupancyType" and u in DESIGNATORS:
            return DESIGNATORS[u]
        return w

    line1 = [(spell(w, lab), lab) for w, lab in rec["street"] + rec["building"]]
    unit = rec["unit"]
    if unit and unit[0][0] != "#" and unit[0][1] == "OccupancyType" and "hash-unit" in mods:
        unit = [("#", "OccupancyIdentifier")] + unit[1:]
    unit = [(spell(w, lab), lab) for w, lab in unit]
    city = [(w, "PlaceName") for w in words(rec["city"])]
    if "noise" in mods and len(city) and rng.random() < 0.3:
        c = city[-1][0]
        if len(c) > 5:
            city[-1] = (c[: len(c) - rng.randint(1, 2)], "PlaceName")
    tail = []
    if "no-state" not in mods:
        tail.append((rec["state"], "StateName"))
    if "no-zip" not in mods:
        z = rec["zip"] + ("-" + rec["plus4"] if rec["plus4"] and "zip4" in mods else "")
        tail.append((z, "ZipCode"))
    toks = line1 + unit + city + tail
    if "noise" in mods:
        idx = [i for i, (w, lab) in enumerate(toks) if lab == "StreetNamePostType" and w.upper() in TYPES]
        if idx and rng.random() < 0.6:
            i = idx[0]
            toks[i] = (toks[i][0] + ".", toks[i][1])
    if "extra-text" in mods:
        if commas and rng.random() < 0.5:  # a recipient line needs a comma to be unambiguous
            toks = [("C/O", "Recipient"), ("PROPERTY", "Recipient"), ("MGMT", "Recipient")] + toks
        else:
            toks = toks + [("USA", "CountryName")]
    if mixed:
        toks = [(w if lab in ("StateName", "ZipCode") else cap(w), lab) for w, lab in toks]
    # commas after the street, unit and city (the last token of each group)
    marks = []
    n_line, n_unit, n_city = len(line1), len(unit), len(city)
    if commas:
        off = len(toks) - (len(line1) + n_unit + n_city + len(tail))  # leading recipient words
        stops = {off + n_line + n_unit - 1, off + n_line + n_unit + n_city - 1}
        if "extra-text" in mods and toks[0][1] == "Recipient":
            stops.add(2)
        marks = sorted(stops)
        if rng.random() < 0.5 and n_unit:  # unit on its own comma group, half the time
            marks.append(off + n_line - 1)
    out = []
    for i, (w, lab) in enumerate(toks):
        out.append((w + ("," if i in marks and i < len(toks) - 1 else ""), lab))
    s = " ".join(w for w, _ in out)
    if "noise" in mods and rng.random() < 0.5 and " " in s:
        i = s.index(" ")
        s = s[:i] + " " + s[i:]
    return s, out, style, mods


def parse_ours(s):
    return doorplate.parse_tokens(s)


def parse_theirs(s):
    return usaddress.parse(s)


def gold_tokens(out):
    """Tokenize each rendered word as usaddress does, carrying its label."""
    gold = []
    for w, lab in out:
        for t in usaddress.tokenize(w):
            gold.append((t, lab))
    return gold


def compare(gold, pred):
    """First coarse mismatch (gold_fine, gold_coarse, pred_coarse) or None; token count must match."""
    if len(pred) != len(gold):
        return ("misaligned",)
    first = None
    for (gt, gl), (pt, pl) in zip(gold, pred):
        if not scored(gt):
            continue
        g, p = norm(gl), norm(pl)
        if g == "CountryName" and p is None:
            continue  # doorplate drops a trailing USA on purpose, with `country_ignored`: the fields are right
        if coarse(g) != coarse(p):
            first = first or (g, coarse(g), coarse(p))
    return first


def fine_wrong(gold, pred):
    return len(pred) == len(gold) and any(
        scored(gt) and norm(gl) != norm(pl) and not (gl == "CountryName" and pl is None)
        for (gt, gl), (_, pl) in zip(gold, pred))


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=75)
    ap.add_argument("--workers", type=int, default=4, help="processes for the parsers (the profile has 4 CPUs)")
    ap.add_argument("--out", type=Path, default=ROOT / "local-data" / "benchsuite")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    df = pd.read_parquet(SAMPLE).fillna("")
    rows = df.to_dict("records")
    rng.shuffle(rows)
    recs, dropped = [], 0
    for r in rows:
        rec = record_from_row(r)
        if rec is None:
            dropped += 1
            continue
        recs.append(rec)
        if len(recs) >= args.records:
            break
    print(f"# Where each library goes wrong (local counts; no rows)\n\n{len(recs):,} records drawn from the NAD "
          f"sample (seed {args.seed}); {dropped:,} rows skipped as unusable (provider splits, floors and rooms, "
          f"odd units) before that.\n", file=sys.stderr)

    inputs, golds, meta = [], [], []
    for rec in recs:
        s, out, style, mods = render(rec, rng)
        inputs.append(s)
        golds.append(gold_tokens(out))
        meta.append((style, mods, rec))

    with multiprocessing.Pool(args.workers) as pool:
        ours = pool.map(parse_ours, inputs, chunksize=2000)
        theirs = pool.map(parse_theirs, inputs, chunksize=2000)

    libs = {"doorplate": ours, "usaddress": theirs}
    n = len(recs)
    res = {"records": n, "seed": args.seed, "usaddress": "0.5.16", "libraries": {}}
    for name, preds in libs.items():
        wrong, fine, classes = 0, 0, collections.Counter()
        by = collections.defaultdict(collections.Counter)
        detail = collections.defaultdict(collections.Counter)
        profile = collections.defaultdict(collections.Counter)
        for gold, pred, (style, mods, rec) in zip(golds, preds, meta):
            first = compare(gold, pred)
            fw = fine_wrong(gold, pred)
            fine += fw
            oos = any(l in OUT_OF_SCOPE for _, l in gold)
            for key in ([("style", style)] + [("modifier", m) for m in mods] + [("unit", "yes" if rec["has_unit"] else "no")]
                        + [("building", "yes" if rec["has_building"] else "no"),
                           ("city_words", "multi" if " " in rec["city"] else "single"),
                           ("unmodeled-by-doorplate", "yes" if oos else "no")]):
                by[key]["n"] += 1
                by[key]["wrong"] += first is not None
            if first is None:
                continue
            wrong += 1
            cls = "misaligned" if first[0] == "misaligned" else f"{first[1]} -> {first[2]}"
            classes[cls] += 1
            if first[0] != "misaligned":
                detail[cls][first[0]] += 1
            for key in (("style", style), ("unit", "yes" if rec["has_unit"] else "no"),
                        ("city_words", "multi" if " " in rec["city"] else "single"),
                        ("building", "yes" if rec["has_building"] else "no"), ("unmodeled-by-doorplate", "yes" if oos else "no")):
                profile[cls][key] += 1
        lo, hi = wilson(wrong, n)
        res["libraries"][name] = {
            "wrong_coarse": wrong, "wrong_fine": fine, "rate_coarse": wrong / n, "ci95": [lo, hi],
            "classes": {c: {"records": k, "per_10k": round(10000 * k / n, 2), "fine_gold": dict(detail[c]),
                            "profile": {f"{a}:{b}": v for (a, b), v in profile[c].most_common(12)}}
                        for c, k in classes.most_common()},
            "by": {f"{a}:{b}": {"n": v["n"], "wrong": v["wrong"], "pct": round(100 * v["wrong"] / v["n"], 2)}
                   for (a, b), v in sorted(by.items())},
        }
    both_wrong = sum(1 for g, a, b in zip(golds, ours, theirs) if compare(g, a) and compare(g, b))
    only_us = sum(1 for g, a, b in zip(golds, ours, theirs) if compare(g, a) and not compare(g, b))
    only_them = sum(1 for g, a, b in zip(golds, ours, theirs) if not compare(g, a) and compare(g, b))
    res["paired"] = {"both_right": n - both_wrong - only_us - only_them, "only_doorplate_right": only_them,
                     "only_usaddress_right": only_us, "both_wrong": both_wrong}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "inventory.json").write_text(json.dumps(res, indent=1))
    report(res)


def report(res):
    n = res["records"]
    print(f"## Overall ({n:,} records)\n")
    print("| Library | Wrong (coarse) | Rate | 95% interval | Wrong (fine) |\n|---|---|---|---|---|")
    for name, d in res["libraries"].items():
        print(f"| {name} | {d['wrong_coarse']:,} | {100 * d['rate_coarse']:.2f}% | "
              f"{100 * d['ci95'][0]:.2f} to {100 * d['ci95'][1]:.2f}% | {d['wrong_fine']:,} |")
    p = res["paired"]
    print(f"\nPaired: both right {p['both_right']:,}; only doorplate right {p['only_doorplate_right']:,}; "
          f"only usaddress right {p['only_usaddress_right']:,}; both wrong {p['both_wrong']:,}.\n")
    for name, d in res["libraries"].items():
        print(f"## Error classes: {name} (per 10,000 records; classes of 1 or more)\n")
        print("| Class | Records | Per 10k | Share of its errors | Common gold labels in the class |\n|---|---|---|---|---|")
        tot = d["wrong_coarse"]
        for c, v in d["classes"].items():
            if v["per_10k"] < 1:
                continue
            fg = ", ".join(f"{k} {m}" for k, m in sorted(v["fine_gold"].items(), key=lambda x: -x[1])[:3])
            print(f"| {c} | {v['records']:,} | {v['per_10k']} | {100 * v['records'] / tot:.1f}% | {fg} |")
        print()
        print(f"### {name}: error rate by style, modifier and record feature\n")
        print("| Group | Records | Wrong | Rate |\n|---|---|---|---|")
        for k, v in d["by"].items():
            print(f"| {k} | {v['n']:,} | {v['wrong']:,} | {v['pct']}% |")
        print()


if __name__ == "__main__":
    main()
