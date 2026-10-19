#!/usr/bin/env python3
"""Stream the NAD text file out of its zip into a Parquet file of the 23 address columns.

    python tools/benchsuite/nad_parquet.py            # prints the plan
    python tools/benchsuite/nad_parquet.py --confirm  # runs it (about 10 minutes, writes about 4 GB)

The suite generator (step 3 of #75) needs street counts for every ZIP code, which the 1,000,000-row
sample cannot give. The 42 GB text file is never written to disk: `7z x -so` pipes it through a named
pipe into DuckDB, which keeps the columns of `tools/netsyms/nad_score.py` and writes
`local-data/nad-2026/nad_r24.parquet` (git-ignored; row-level NAD data stays in `local-data/`,
docs/data-policy.md). This library formats and parses; it does not validate that an address exists.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "local-data" / "nad-2026" / "TXT.zip"
MEMBER = "TXT/NAD_r24.txt"
OUT = ROOT / "local-data" / "nad-2026" / "nad_r24.parquet"
KEEP = ("State,AddNum_Pre,Add_Number,AddNum_Suf,AddNo_Full,St_PreMod,St_PreDir,St_PreTyp,St_PreSep,St_Name,"
        "St_PosTyp,St_PosDir,St_PosMod,StNam_Full,Building,Floor,Unit,Room,SubAddress,Post_City,Zip_Code,"
        "Plus_4,NAD_Source").split(",")


def header():
    p = subprocess.Popen(["7z", "x", "-so", str(ZIP), MEMBER], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    line = p.stdout.readline().decode().strip()
    p.kill()
    return line.split(",")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    if not ZIP.exists():
        sys.exit(f"{ZIP} is not here (local-data/README.md says how to download it)")
    cols = header()
    missing = [c for c in KEEP if c not in cols]
    if missing:
        sys.exit(f"columns missing from the header: {missing}")
    print(f"plan\n  read    {ZIP} ({ZIP.stat().st_size / 2**30:.1f} GB), streamed through a pipe, nothing extracted\n"
          f"  write   {OUT} (about 4 GB, {len(KEEP)} of {len(cols)} columns, all text)\n  time    about 10 minutes")
    if not args.confirm:
        sys.exit("Dry run. Re-run with --confirm to start.")
    import duckdb
    tmp = tempfile.mkdtemp()
    fifo = os.path.join(tmp, "nad.csv")
    os.mkfifo(fifo)
    sz = subprocess.Popen(["7z", "x", "-so", str(ZIP), MEMBER], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def pump():
        with open(fifo, "wb") as w:
            while chunk := sz.stdout.read(1 << 20):
                w.write(chunk)

    t = threading.Thread(target=pump)
    t.start()
    con = duckdb.connect()
    con.execute(f"set threads={args.threads}")
    spec = ", ".join(f"'{c}': 'VARCHAR'" for c in cols)
    con.execute(f"""copy (select {", ".join(KEEP)} from read_csv('{fifo}', header=true, columns={{{spec}}},
        auto_detect=false, delim=',', quote='"', escape='"', null_padding=true, ignore_errors=true)
        ) to '{OUT}' (format parquet, compression zstd)""")
    t.join()
    os.remove(fifo)
    os.rmdir(tmp)
    n = con.execute(f"select count(*) from '{OUT}'").fetchone()[0]
    print(f"done: {n:,} rows (the file's header says 99,226,272 records), {OUT.stat().st_size / 2**30:.1f} GB")


if __name__ == "__main__":
    main()
