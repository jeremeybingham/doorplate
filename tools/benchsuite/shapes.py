#!/usr/bin/env python3
"""Step 2 of the benchmark suite (#75), part 1: how addresses are shaped and written, as counts.

    python tools/benchsuite/shapes.py [--out local-data/benchsuite/shapes.json]

Reads the local sources (the Florida DBPR export, the Florida auction listings, the Netsyms sample, the
NAD sample) and prints Markdown tables of shares: the address type, the unit forms, the case, commas,
spelled-out types and directionals, ZIP+4, a trailing USA, noise. It prints counts and shares only, never
a row (docs/data-policy.md). The shares fill in the composition and style tables of
docs/benchmark-suite.md. This library formats and parses; it does not validate that an address exists.
"""
import argparse
import collections
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

import doorplate

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "local-data"

DESIGNATOR = re.compile(r"\b(APT|APARTMENT|UNIT|STE|SUITE|BLDG|BUILDING|FL|FLOOR|RM|ROOM|LOT|TRLR|SPC|SPACE|DEPT)\b\.?", re.I)
HASH = re.compile(r"#\s*\w")
SPELLED_TYPE = re.compile(r"\b(STREET|AVENUE|ROAD|DRIVE|LANE|BOULEVARD|COURT|CIRCLE|PLACE|TRAIL|PARKWAY|HIGHWAY|TERRACE)\b", re.I)
ABBR_TYPE = re.compile(r"\b(ST|AVE|RD|DR|LN|BLVD|CT|CIR|PL|TRL|PKWY|HWY|TER)\b\.?", re.I)
SPELLED_DIR = re.compile(r"\b(NORTH|SOUTH|EAST|WEST|NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST)\b", re.I)
ZIP4 = re.compile(r"\b\d{5}[- ]?\d{4}\b")
TRAILING_COUNTRY = re.compile(r"\b(USA|US|UNITED STATES)\.?\s*$", re.I)


def kind(line):
    try:
        return doorplate.address_type(line)
    except Exception:
        return "empty"


def share(counter):
    n = sum(counter.values())
    return {k: [v, round(100 * v / n, 3)] for k, v in counter.most_common()} if n else {}


def case_of(s):
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return "no-letters"
    if all(c.isupper() for c in letters):
        return "upper"
    if all(c.islower() for c in letters):
        return "lower"
    return "mixed"


def line_styles(lines):
    """Style counts for one-line-1 strings (street and unit forms, case, spelling, noise)."""
    c = collections.Counter()
    for s in lines:
        c["n"] += 1
        c["case:" + case_of(s)] += 1
        has_des, has_hash = bool(DESIGNATOR.search(s)), bool(HASH.search(s))
        c["unit:designator" if has_des else "unit:hash" if has_hash else "unit:none-visible"] += 1
        c["type:spelled" if SPELLED_TYPE.search(s) else "type:abbreviated" if ABBR_TYPE.search(s) else "type:none"] += 1
        c["dir:spelled"] += bool(SPELLED_DIR.search(s))
        c["periods"] += "." in s
        c["double-space"] += "  " in s
        c["comma"] += "," in s
    return c


def pct(counter, prefix=None):
    n = counter["n"]
    return {k: [v, round(100 * v / n, 2)] for k, v in sorted(counter.items()) if k != "n"}, n


def dbpr(rows):
    d = pd.read_parquet(LOCAL / "florida-dbpr" / "normalized.parquet").fillna("").sample(rows, random_state=1)
    s1, s2, s3 = list(d.s1), list(d.s2), list(d.s3)
    types = collections.Counter(kind(" ".join(x for x in t if x)) for t in zip(s1, s2, s3))
    with_text = [a for a in s1 if a.strip()]
    c = line_styles(with_text)
    c["line2-present"] = sum(1 for a, b in zip(s1, s2) if a.strip() and b.strip())
    return {"type": share(types), "style": pct(c)}


def florida_raw():
    d = pd.read_csv(LOCAL / "florida" / "raw_addresses.csv", dtype=str).fillna("")
    col = [c for c in d.columns if c.startswith("raw")][0]
    lines = [s for s in d[col] if s.strip()]
    c = line_styles(lines)
    for s in lines:
        c[f"commas:{min(s.count(','), 3)}"] += 1
        c["zip4"] += bool(ZIP4.search(s))
        c["trailing-country"] += bool(TRAILING_COUNTRY.search(s))
        c["state-dash-zip"] += bool(re.search(r"\b[A-Z]{2}-\s*\d{5}", s))
    types = collections.Counter(kind(s) for s in lines)
    return {"type": share(types), "style": pct(c)}


def netsyms(rows):
    con = sqlite3.connect(LOCAL / "netsyms-2026" / "sample.sqlite")
    rs = con.execute(
        "select number, street, street2, city, state, zipcode, plus4 from sample where country='US' limit ?", (rows,)
    ).fetchall()
    types = collections.Counter(kind(" ".join(x for x in r[:3] if x)) for r in rs)
    c = line_styles([" ".join(x for x in r[:3] if x) for r in rs])
    c["plus4"] = sum(1 for r in rs if r[6])
    c["line2-present"] = sum(1 for r in rs if r[2])
    return {"type": share(types), "style": pct(c)}


def nad(rows):
    d = pd.read_parquet(LOCAL / "nad-2026" / "sample1m.parquet").fillna("").head(rows)
    n = len(d)
    out = collections.Counter()
    for col in ("Unit", "Building", "Floor", "Room", "SubAddress", "AddNum_Pre", "AddNum_Suf", "St_PreMod", "St_PreSep",
                "St_PosMod", "Plus_4", "St_PreDir", "St_PosDir", "St_PreTyp", "St_PosTyp"):
        out[col] = int((d[col].str.strip() != "").sum())
    out["n"] = n
    return {"columns": {k: [v, round(100 * v / n, 3)] for k, v in out.items() if k != "n"}, "n": n}


def table(title, section):
    lines = [f"### {title}", ""]
    if "type" in section:
        lines += ["Address type (all rows with any text; `empty` is a blank line 1)", "", "| Type | Rows | Share |", "|---|---|---|"]
        lines += [f"| {k} | {v[0]:,} | {v[1]}% |" for k, v in section["type"].items()]
        lines.append("")
    if "style" in section:
        stats, n = section["style"]
        lines += [f"Writing styles (of {n:,} line-1 strings)", "", "| Feature | Rows | Share |", "|---|---|---|"]
        lines += [f"| {k} | {v[0]:,} | {v[1]}% |" for k, v in stats.items()]
        lines.append("")
    if "columns" in section:
        lines += [f"NAD columns non-empty (of {section['n']:,} rows)", "", "| Column | Rows | Share |", "|---|---|---|"]
        lines += [f"| {k} | {v[0]:,} | {v[1]}% |" for k, v in section["columns"].items()]
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=500_000)
    ap.add_argument("--out", type=Path, default=LOCAL / "benchsuite" / "shapes.json")
    args = ap.parse_args()
    res = {
        "dbpr": dbpr(args.rows),
        "florida_raw": florida_raw(),
        "netsyms": netsyms(args.rows),
        "nad": nad(args.rows),
        "doorplate": doorplate.__file__,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=1))
    print("# Shapes and styles (local counts; no rows)\n")
    for title, key in (("Florida DBPR licensee addresses (mailing addresses)", "dbpr"),
                       ("Florida auction listings (one-line)", "florida_raw"),
                       ("Netsyms sample (address points)", "netsyms"),
                       ("NAD r24 sample", "nad")):
        print(table(title, res[key]))


if __name__ == "__main__":
    main()
