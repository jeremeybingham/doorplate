#!/usr/bin/env python3
"""Score doorplate on MessyStreets (#323): parse each web address as one string, compare with the page's own fields.

    python tools/harness/messy_score.py                 # the plan
    python tools/harness/messy_score.py --confirm       # score all three tiers
    python tools/harness/messy_score.py --confirm --tier raw

Reads `local-data/messy-streets/records.parquet` (tools/ingest/specs/messy-streets.toml: the US-like
rows) and the tier files for each row's `input`, the one string a geocoder would be given (street,
locality, region, postal code, country joined). It parses that string with `parse_many` and compares
ZIP5, state, city and street name with the page's markup fields (and, for gold and silver, the street
name of the existence record). Output is counts and rates per tier, never a row, so it may be quoted
under docs/data-policy.md. The gold and silver rows are held-out checks (docs/benchmarks.md): this
script reads them in bulk to score, nobody reads them.

Read it with care: the labels are the web's own markup, not hand-checked, so a miss is a question and a
hit on a wrong label is still a hit; the city and street name are compared after upper-casing and
dropping punctuation; the state accepts a spelled-out name; the street name counts as found when every
word of our street name is a word of the verified street, which is lenient. The rates are not an
accuracy claim and are not comparable with other parsers' scores on other labels. This library formats
and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "local-data" / "messy-streets"
TIERS = ("gold", "silver", "raw")
STATES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA", "COLORADO": "CO",
    "CONNECTICUT": "CT", "DELAWARE": "DE", "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
    "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT",
    "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
    "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
    "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY", "PUERTO RICO": "PR",
}
FIELDS = ("zip", "state", "city", "street")


def words(s):
    return re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper().replace("&", " AND ")).split()


def norm(s):
    """Upper-case words; the markup's literal missing-value strings (`nan`, `null`, `none`) are empty."""
    n = " ".join(words(s))
    return "" if n in ("NAN", "NULL", "NONE") else n


def state(s):
    n = norm(s)
    return STATES.get(n, n)


def zip5(s):
    m = re.match(r"\s*(\d{5})", s or "")
    return m.group(1) if m else ""


def pass_(field, label, a, verified):
    """True / False, or None when there is nothing to compare."""
    if field == "zip":
        return (a.zip5 or "") == zip5(label) if zip5(label) else None
    if field == "state":
        return state(a.state) == state(label) if state(label) else None
    if field == "city":
        return norm(a.city) == norm(label) if norm(label) else None
    if not verified:
        return None
    ours = set(words(a.street_name))
    return bool(ours) and ours <= set(words(verified))


def score(tiers):
    import duckdb
    from doorplate import parse_many

    con = duckdb.connect()
    out = {}
    for t in tiers:
        rows = con.execute(f"""
            select r.zip, r.state, r.city, r.label_name, json_extract_string(j.json, '$.input') as inp
            from read_parquet('{DIR / "records.parquet"}') r
            join read_ndjson_objects('{DIR / f"release_{t}_10k_final.jsonl.gz"}') j
              on json_extract_string(j.json, '$.id') = r.record_id
            where r.role = '{t}'""").fetchall()
        parsed = parse_many([r[4] or "" for r in rows])
        c = Counter()
        c["rows"] = len(rows)
        for (z, s, city, lab, _), a in zip(rows, parsed):
            for f, label in (("zip", z), ("state", s), ("city", city), ("street", None)):
                r = pass_(f, label, a, lab)
                if r is None:
                    continue
                c[f + "_n"] += 1
                c[f + "_ok"] += bool(r)
        out[t] = c
    return out


def report(out):
    print("| Tier (US-like rows) | Rows | ZIP5 | State | City | Street name |\n|---|---|---|---|---|---|")
    for t, c in out.items():
        cells = []
        for f in FIELDS:
            n = c[f + "_n"]
            cells.append(f"{100 * c[f + '_ok'] / n:.1f}% ({n:,})" if n else "n/a")
        print(f"| {t} | {c['rows']:,} | " + " | ".join(cells) + " |")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--tier", choices=TIERS, action="append", help="a tier to score (default: all three)")
    p.add_argument("--confirm", action="store_true", help="score (without it, print the plan)")
    args = p.parse_args()
    tiers = args.tier or list(TIERS)
    if not (DIR / "records.parquet").exists():
        sys.exit(f"{DIR / 'records.parquet'} is not here; run tools/ingest/ingest.py on tools/ingest/specs/messy-streets.toml")
    if not args.confirm:
        sys.exit(f"plan: parse the `input` of the US-like rows of {', '.join(tiers)} and compare ZIP5, state, city, "
                 "street name with the markup (counts only, about a minute). Re-run with --confirm.")
    report(score(tiers))


if __name__ == "__main__":
    main()
