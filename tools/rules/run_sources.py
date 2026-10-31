#!/usr/bin/env python3
"""Rule firing counts over the records files (#401), one TSV per source, counts only.

    VIRTUAL_ENV=/tmp/venv-rs maturin develop --release --features rule-stats   # in crates/doorplate-py
    python tools/rules/run_sources.py OUTDIR [--sample N] [--sources FILE]

Needs the extension built with the `rule-stats` feature (in a venv of its own, not the one other tools
use). For each records file in `local-data/keycompare/sources.txt` it parses a random sample of N rows
(default 2,000,000; 0 for every row; reservoir sample with a fixed seed) with `parse_fields` (or `parse` on the fields joined into one line with `--oneline`, under a default
state with `--default-state XX`) on one
thread, and writes `OUTDIR/<source>.tsv` in the format of the `rule_stats` example. Rows with a
`last_line` are left out, as in `key_diff.py`. Only counts are written or printed; DuckDB errors can
quote rows, so only their type is printed.
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("line1", "line2", "city", "state", "zip")
CHUNK = 250_000


def main():
    import doorplate._core as core
    import duckdb

    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--sample", type=int, default=2_000_000)
    ap.add_argument(
        "--oneline", action="store_true", help="join the fields into one line, parse()"
    )
    ap.add_argument(
        "--default-state",
        help="parse under this default_state (a USPS code), with the state and ZIP left out",
    )
    ap.add_argument(
        "--sources", default=str(ROOT / "local-data/keycompare/sources.txt")
    )
    args = ap.parse_args()
    if not hasattr(core, "_rule_stats_run"):
        sys.exit("the extension was not built with --features rule-stats")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    paths = [
        line.strip()
        for line in Path(args.sources).read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for rel in paths:
        src = ROOT / rel
        con = duckdb.connect()
        try:
            cols = {
                r[0] for r in con.execute(f"describe select * from '{src}'").fetchall()
            }
            use = [c for c in FIELDS if c in cols]
            name = con.execute(f"select any_value(source) from '{src}'").fetchone()[0]
            keep = "where last_line is null" if "last_line" in cols else ""
            sample = (
                f"using sample reservoir({args.sample} rows) repeatable (1)"
                if args.sample
                else ""
            )
            res = con.execute(f"select {', '.join(use)} from '{src}' {keep} {sample}")
            t = time.time()
            done = 0
            while True:
                batch = res.fetchmany(CHUNK)
                if not batch:
                    break
                cols_out = {c: [r[i] for r in batch] for i, c in enumerate(use)}
                empty = [None] * len(batch)
                if args.default_state:
                    # The hint only matters when the input names no state or ZIP.
                    cols_out["state"] = cols_out["zip"] = empty
                core._rule_stats_run(
                    *(cols_out.get(c, empty) for c in FIELDS),
                    args.oneline,
                    args.default_state,
                )
                done += len(batch)
                print(f"{name}: {done} rows, {time.time() - t:.0f} s", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - DuckDB errors can quote rows
            sys.exit(f"failed: {type(e).__name__}")
        rows, parses = core._rule_stats_take()
        with open(out / f"{name}.tsv", "w") as f:
            f.write(f"# parses\t{parses}\n")
            f.writelines(
                f"{kind}\t{site}\t{label}\t{fires}\t{inputs}\n"
                for kind, site, label, fires, inputs in rows
            )
        print(f"{name}: {parses} rows parsed")


if __name__ == "__main__":
    main()
