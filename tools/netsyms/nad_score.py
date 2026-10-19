#!/usr/bin/env python3
"""Score doorplate against the labeled parts of the National Address Database (NAD).

    python tools/netsyms/nad_score.py --make-sample --confirm     # one pass over the NAD text file (about 3 minutes)
    python tools/netsyms/nad_score.py                              # score the saved sample

The NAD text file (`local-data/nad-2026/extracted/TXT/NAD_r24.txt`, see docs/data-policy.md) labels
each address's parts: number prefix and suffix, street predirectional, name, type and postdirectional,
unit, building and floor. `--make-sample` draws a random 1,000,000-row sample into a Parquet file in
`local-data/nad-2026/`. The scorer joins each row into line 1 (`AddNo_Full` + `StNam_Full`) and line 2
(`SubAddress`), parses it with `parse_fields_many`, and compares our parts with NAD's wherever NAD has
a non-empty label. Output is counts only (never a row), so it may be quoted under docs/data-policy.md.

Read it with care: providers label inconsistently (many put the suffix inside the name and leave the
type empty), so only a disagreement where NAD *has* a label points at a parser question, and
spelled-out designators in `Unit` (`Apartment 4`) will differ from our abbreviations. This library
formats and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAD = ROOT / "local-data" / "nad-2026" / "extracted" / "TXT" / "NAD_r24.txt"
SAMPLE = ROOT / "local-data" / "nad-2026" / "sample1m.parquet"
COLUMNS = ("State,AddNum_Pre,Add_Number,AddNum_Suf,AddNo_Full,St_PreMod,St_PreDir,St_PreTyp,St_PreSep,St_Name,"
           "St_PosTyp,St_PosDir,St_PosMod,StNam_Full,Building,Floor,Unit,Room,SubAddress,Post_City,Zip_Code,"
           "Plus_4,NAD_Source")


def make_sample(args):
    import duckdb
    if not NAD.exists():
        sys.exit(f"{NAD} is not here (docs/data-policy.md, local-data/README.md)")
    print(f"plan\n  read    {NAD} ({NAD.stat().st_size / 2**30:.1f} GB)\n  write   {args.sample} "
          f"(about 40 MB, {args.rows:,} rows, seed {args.seed})\n  time    about 3 minutes")
    if not args.confirm:
        sys.exit("Dry run. Re-run with --confirm to start.")
    con = duckdb.connect()
    con.execute("set threads=12")
    con.execute(f"""copy (select {COLUMNS} from read_csv('{NAD}', header=true, all_varchar=true, sample_size=50000)
        using sample reservoir({args.rows} rows) repeatable ({args.seed})) to '{args.sample}' (format parquet)""")
    print("done")


def score(args):
    import duckdb
    import doorplate
    if not args.sample.exists():
        sys.exit(f"{args.sample} is not here; run with --make-sample --confirm first")
    df = duckdb.connect().execute(f"select * from '{args.sample}'").fetchdf().fillna("")
    strip = lambda s: (s or "").strip()
    compact = lambda s: re.sub(r"[^A-Z0-9]", "", (s or "").upper())
    res = doorplate.parse_fields_many(
        line1=[(strip(a) + " " + strip(b)).strip() for a, b in zip(df.AddNo_Full, df.StNam_Full)],
        line2=[strip(x) or None for x in df.SubAddress],
        city=[strip(x) or None for x in df.Post_City],
        state=[strip(x) or None for x in df.State],
        zip=[strip(x) or None for x in df.Zip_Code],
    )
    cache = {}

    def canon(kind, v):
        """NAD's spelling of a suffix or directional, as our parser would write it."""
        v = strip(v)
        if not v:
            return ""
        if (kind, v.upper()) not in cache:
            text = {"suf": f"1 MAIN {v}", "dir": f"1 {v} MAIN ST", "post": f"1 MAIN ST {v}"}[kind]
            a = doorplate.parse_fields(line1=text, city="MIAMI", state="FL", zip="33101")
            cache[(kind, v.upper())] = str({"suf": a.street_suffix, "dir": a.street_dir_prefix,
                                            "post": a.street_dir_suffix}[kind] or "?" + compact(v))
        return cache[(kind, v.upper())]

    c = collections.Counter()
    pairs = collections.defaultdict(collections.Counter)
    states = collections.defaultdict(collections.Counter)
    for i, a in enumerate(res):
        if a is None:
            c["no result"] += 1
            continue
        c["rows"] += 1
        st = df.State.iat[i]
        for label, col, kind, ours in (
            ("predirectional", "St_PreDir", "dir", a.street_dir_prefix),
            ("postdirectional", "St_PosDir", "post", a.street_dir_suffix),
            ("suffix", "St_PosTyp", "suf", a.street_suffix),
        ):
            raw = strip(df[col].iat[i])
            if not raw:
                continue
            c[f"{label}: NAD labeled"] += 1
            want, got = canon(kind, raw), str(ours or "")
            if want != got:
                c[f"{label}: we differ"] += 1
                pairs[label][(want, got)] += 1
                states[label][st] += 1
        unit = strip(df.Unit.iat[i])
        if unit:
            c["unit: NAD labeled"] += 1
            if not a.unit_number:
                c["unit: we found none"] += 1
                states["unit"][st] += 1

    print(f"rows scored: {c['rows']:,}\n")
    for label in ("predirectional", "postdirectional", "suffix", "unit"):
        n = c[f"{label}: NAD labeled"]
        d = c["unit: we found none"] if label == "unit" else c[f"{label}: we differ"]
        print(f"{label:16s} NAD labeled {n:>9,}   we differ {d:>7,} ({100 * d / max(n, 1):.2f}%)")
    for label in ("predirectional", "postdirectional", "suffix"):
        print(f"\n{label}: NAD value -> ours (lexicon values only)")
        for (want, got), n in pairs[label].most_common(args.top):
            print(f"  {n:>7,}  {want or '-'} -> {got or '-'}")
        print("  top states", states[label].most_common(5))
    print("\nunit (NAD labeled a Unit, we found none): top states", states["unit"].most_common(5))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sample", type=Path, default=SAMPLE)
    ap.add_argument("--make-sample", action="store_true")
    ap.add_argument("--rows", type=int, default=1_000_000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()
    make_sample(args) if args.make_sample else score(args)


if __name__ == "__main__":
    main()
