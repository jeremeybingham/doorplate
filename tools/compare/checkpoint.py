#!/usr/bin/env python3
"""The foundation checkpoint: the key comparison with the last release over all the large sources, once.

    python tools/compare/checkpoint.py --baseline-python ../venv031/bin/python                  # the plan
    python tools/compare/checkpoint.py --baseline-python ../venv031/bin/python --confirm        # run it

The release plan (docs/backlog.md) folds the `k3` into 0.4.0 in two phases. The foundation phase must leave every key
unchanged, and this is the single run that shows it: it parses every records file with the released build and with
the current build (`tools/compare/key_diff.py dump`, each in its own interpreter) and compares the keys row by row
(`key_diff.py diff`). The current build's dump is then **frozen** as the baseline the `k3` rules are measured
against (`key_diff.py diff BASELINE NEW`, by source and role).

Without --confirm it only prints the plan and exits. The sources are listed in a file kept with the private data
(`local-data/keycompare/sources.txt`, one records path per line, relative to the repository root): the repository
names no private source. Output is counts only, never address text; everything is written under `local-data/`.

Needs the interpreter with the current build (`maturin develop --release`; the default is the one running this
script) and DuckDB and PyArrow in both interpreters. The released build's dumps are reused when they exist.
"""
import argparse
import datetime
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY_DIFF = Path(__file__).with_name("key_diff.py")
DEFAULT_SOURCES = ROOT / "local-data" / "keycompare" / "sources.txt"
ROWS_PER_SECOND = 150_000  # one interpreter on this machine's 14 threads, from the 0.4.0 runs


def sh(*cmd, cwd=ROOT):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def commit():
    try:
        dirty = " (dirty tree)" if sh("git", "status", "--porcelain") else ""
        return sh("git", "rev-parse", "--short", "HEAD"), dirty
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nogit", ""


def version_of(python):
    try:
        return sh(str(python), "-I", "-c", "import doorplate; print(doorplate.__version__)")
    except subprocess.CalledProcessError:
        return None


def read_sources(path):
    """The records files, one per line; blank lines and `#` comments are skipped."""
    if not path.is_file():
        sys.exit(f"{path} not found: list the records files there, one path per line")
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(Path(line) if Path(line).is_absolute() else ROOT / line)
    return out


def count_rows(records):
    import duckdb

    try:
        return duckdb.connect().execute(f"select count(*), any_value(source) from '{records}'").fetchone()
    except Exception as e:  # DuckDB errors can quote rows: print the type only
        sys.exit(f"failed to read a records file: {type(e).__name__}")


def plan(args, sources):
    c, dirty = commit()
    cur, old = version_of(args.python), version_of(args.baseline_python)
    out = args.out or ROOT / "local-data" / "keycompare" / f"checkpoint-{c}"
    rows = [(p, *count_rows(p)) for p in sources if p.is_file()]
    missing = [p for p in sources if not p.is_file()]
    total = sum(n for _, n, _ in rows)
    reuse = [name for _, _, name in rows if (args.baseline / f"{name}.parquet").is_file()]
    size = sum((args.baseline / f"{name}.parquet").stat().st_size for name in reuse) / 1e9
    print(f"""plan
  commit           {c}{dirty}
  current build    {cur or 'NOT IMPORTABLE'}   ({args.python})
  released build   {old or 'NOT IMPORTABLE'}   ({args.baseline_python})
  sources          {len(rows)} records files, {total:,} rows{f'; MISSING: {len(missing)}' if missing else ''}
  released dumps   {len(reuse)} of {len(rows)} already in {args.baseline} (reused; the rest are parsed with the released build)
  output           {out}  (the current build's dumps, the report, and the frozen-baseline note)
  time             about {total / ROWS_PER_SECOND / 60:.0f} minutes for the current build{'' if len(reuse) == len(rows) else ', more for the missing released dumps'}
  disk             about {size:.1f} GB (the dumps hold keys and warning codes only, as large as the released ones)
  before running   rebuild the current build from this commit: maturin develop --release""")
    if not cur or not old or missing or dirty:
        print("\nnot ready:" + "".join([
            "\n  - the current build cannot be imported (maturin develop --release)" if not cur else "",
            "\n  - the released build cannot be imported (a venv with the released wheel)" if not old else "",
            f"\n  - {len(missing)} records file(s) missing" if missing else "",
            "\n  - the tree is dirty: the checkpoint should name a commit" if dirty else "",
        ]))
        return None
    return out, rows


def run(args, out, rows):
    out.mkdir(parents=True, exist_ok=True)
    for records, _, name in rows:
        if not (args.baseline / f"{name}.parquet").is_file():
            print(f"released build: {name}", flush=True)
            sh(str(args.baseline_python), "-I", str(KEY_DIFF), "dump", str(records), "--out", str(args.baseline))
        print(f"current build:  {name}", flush=True)
        sh(str(args.python), "-I", str(KEY_DIFF), "dump", str(records), "--out", str(out))
    res = subprocess.run([str(args.python), "-I", str(KEY_DIFF), "diff", str(args.baseline), str(out)],
                         cwd=ROOT, capture_output=True, text=True)
    c, _ = commit()
    stamp = datetime.date.today().isoformat()
    report = (f"# Foundation checkpoint {c} ({stamp})\n\nReleased build {version_of(args.baseline_python)} against "
              f"current build {version_of(args.python)}, row by row (`key_diff.py diff`). Counts only.\n\n"
              f"```\n{res.stdout}```\n")
    (out / "report.md").write_text(report)
    passed = res.returncode == 0
    (out / "FROZEN.md").write_text(
        f"# Frozen baseline for the k3 ({c}, {stamp})\n\n"
        f"This directory holds the keys of the foundation checkpoint. Compare a rule's build with it:\n\n"
        f"    python tools/compare/key_diff.py diff {out} NEW_DUMP_DIR\n\n"
        f"Checkpoint result: {'zero key differences from ' + str(version_of(args.baseline_python)) if passed else 'KEYS DIFFER, see report.md'}.\n")
    print(res.stdout)
    print(f"report: {out / 'report.md'}")
    return 0 if passed else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline-python", type=Path, required=True,
                    help="interpreter with the released doorplate installed (a throwaway venv)")
    ap.add_argument("--python", type=Path, default=Path(sys.executable), help="interpreter with the current build")
    ap.add_argument("--baseline", type=Path, default=ROOT / "local-data" / "keycompare" / "v031",
                    help="the released build's dumps (reused when present)")
    ap.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    ap.add_argument("--out", type=Path, help="default: local-data/keycompare/checkpoint-<commit>")
    ap.add_argument("--confirm", action="store_true", help="run it; without this only the plan is printed")
    args = ap.parse_args()
    ready = plan(args, read_sources(args.sources))
    if not args.confirm:
        print("\nplan only; add --confirm to run")
        return
    if ready is None:
        sys.exit("not ready (see above)")
    sys.exit(run(args, *ready))


if __name__ == "__main__":
    main()
