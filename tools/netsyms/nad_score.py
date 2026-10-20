#!/usr/bin/env python3
"""Score doorplate against the labeled parts of the National Address Database (NAD).
(A thin wrapper: the scoring is tools/netsyms/label_score.py on the NAD records.)

    python tools/netsyms/nad_score.py --make-sample --confirm     # one pass over the NAD text file (about 3 minutes)
    python tools/netsyms/nad_score.py                              # score the saved sample

The NAD text file (`local-data/nad-2026/extracted/TXT/NAD_r24.txt`, see docs/data-policy.md) labels
each address's parts: number prefix and suffix, street predirectional, name, type and postdirectional,
unit, building and floor. `--make-sample` draws a random 1,000,000-row sample into a Parquet file in
`local-data/nad-2026/`. The scorer joins each row into line 1 (`AddNo_Full` + `StNam_Full`) and line 2
(`SubAddress`) (tools/ingest/specs/nad.toml), parses it with `parse_fields_many`, and compares our
parts with NAD's wherever NAD has a non-empty label. Output is counts only (never a row), so it may be quoted under docs/data-policy.md.

Read it with care: providers label inconsistently (many put the suffix inside the name and leave the
type empty), so only a disagreement where NAD *has* a label points at a parser question, and
spelled-out designators in `Unit` (`Apartment 4`) will differ from our abbreviations. This library
formats and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
    """Score the saved sample with label_score.py: the same sample as records (built by
    tools/ingest/specs/nad.toml when missing), the same four fields as before."""
    if not args.sample.exists():
        sys.exit(f"{args.sample} is not here; run with --make-sample --confirm first")
    records = ROOT / "local-data" / "nad-2026" / "records.parquet"
    if not records.exists() or records.stat().st_mtime < args.sample.stat().st_mtime:
        sys.path.insert(0, str(ROOT / "tools" / "ingest"))
        import ingest
        spec_path = ROOT / "tools" / "ingest" / "specs" / "nad.toml"
        ingest.build(ingest.load_spec(spec_path), spec_path, None)
    import label_score
    label_score.main([str(records), "--fields", "predirectional,postdirectional,suffix,unit",
                      "--top", str(args.top), "--confirm"])


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
