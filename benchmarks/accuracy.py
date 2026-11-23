#!/usr/bin/env python3
"""Accuracy: golden corpus, usaddress's test files and the geocode benchmark.

    python benchmarks/accuracy.py [--with-libpostal [--libpostal-home DIR]]

Needs the release CLI and `usaddress` (pip install usaddress). The geocode
benchmark is not in the repository (`docs/running-benchmarks.md` says how to get it);
without it that part is skipped. `--with-libpostal` adds libpostal (the Senzing build,
`docs/libpostal-compat.md`) to each geocode split, scored with all three parsers on the
common label set. Prints Markdown.
"""
import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import CLI, GEOCODE, ROOT, machine, need_cli, run  # noqa: E402


def corpus_report(directory):
    """`whole address: 187/190 (98.4%)` and the case count from `corpus test`."""
    out = run([str(CLI), "corpus", "test", "--dir", str(directory)])
    cases = int(re.search(r"golden corpus: (\d+) cases", out).group(1))
    m = re.search(r"whole address:\s+(\d+)/(\d+) \(([\d.]+)%\)", out)
    return cases, int(m.group(1)), int(m.group(2)), m.group(3)


def compare(mode, *args):
    """Run tools/compare/compare_usaddress.py and return the report text."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "report.md"
        run([sys.executable, str(ROOT / "tools/compare/compare_usaddress.py"), "--out", str(out), mode, *args])
        return out.read_text()


def table_row(report, first_cell, cells=11):
    """The first table row that starts with `first_cell` and has `cells` cells
    (the report has a short counts table and the score table)."""
    for line in report.splitlines():
        if line.startswith(f"| {first_cell}"):
            row = [c.strip() for c in line.strip("|").split("|")]
            if len(row) >= cells:
                return row
    return None


def common_rows(report):
    """The `all` and `shared` rows of the common-label table (libpostal), and the pins line above it."""
    _, _, rest = report.partition("## Common labels, with libpostal")
    if not rest:
        return None, []
    pins = next((line for line in rest.splitlines() if line.startswith("libpostal commit")), "")
    rows = []
    for line in rest.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if line.startswith("| ") and cells[0] in ("all", "shared"):
            rows.append(cells)
        if line.startswith("### Seen"):
            break
    return pins, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--with-libpostal", action="store_true", help="add libpostal to the geocode splits (common label set)")
    ap.add_argument("--libpostal-home", help="the libpostal build folder (default: $LIBPOSTAL_HOME or ~/projects/libpostal-senzing)")
    args = ap.parse_args()
    lp_args = ["--with-libpostal"] if args.with_libpostal else []
    if args.with_libpostal and args.libpostal_home:
        lp_args += ["--libpostal-home", args.libpostal_home]
    need_cli()
    print(f"# Accuracy\n\nMachine: {machine()}\n")
    print("Scores are for addresses written one to a line unless noted. \"Coarse\" folds street parts")
    print("into the street name (docs/usaddress-compat.md, \"Scoring rules\"); \"fine\" keeps them apart.\n")

    cases, ok, total, pct = corpus_report(ROOT / "tests" / "corpus")
    print("## Golden corpus (tests/corpus)\n")
    print(f"{ok} of {total} whole addresses right ({pct}%) over {cases} cases. These cases were written")
    print("alongside the parser, so this is a regression check, not an accuracy estimate.\n")

    ext = sorted((ROOT / "tests" / "external" / "usaddress").glob("*.xml"))
    if ext:
        rep = compare("gold", *map(str, ext))
        row = table_row(rep, "**All not in training**")
        print("## usaddress's test files, not in its training data\n")
        print("These are usaddress's own regression tests, so it is expected to score near 100%.\n")
        if row:
            print("| | Addresses | Tokens | Ours: tokens | usaddress: tokens | Ours: whole address | usaddress: whole address |")
            print("|---|---|---|---|---|---|---|")
            print("| all | " + " | ".join(row[1:7]) + " |\n")

    # dev and train were never read while the rules were written; test was.
    splits = [
        ("dev", "Geocode benchmark, dev split (never read while writing rules)"),
        ("train", "Geocode benchmark, train split (never read while writing rules)"),
        ("train80", "Geocode benchmark, train80 (80% of train; rules were fixed against it)"),
        ("train20_heldout", "Geocode benchmark, train20 (20% of train, held out, never read)"),
        ("test", "Geocode benchmark, test split (read while writing rules: optimistic)"),
    ]
    found = False
    for split, title in splits:
        xml = GEOCODE / f"{split}_usaddress.xml"
        if not xml.exists():
            continue
        found = True
        rep = compare("gold", str(xml), *lp_args)
        row = table_row(rep, f"{split}_usaddress.xml")
        print(f"## {title} ({row[1] if row else '?'} one-line addresses)\n")
        if row:
            print("| | Ours | usaddress |\n|---|---|---|")
            print(f"| Tokens (coarse) | {row[3]} | {row[4]} |")
            print(f"| Whole address (coarse) | {row[5]} | {row[6]} |")
            print(f"| Tokens (fine) | {row[7]} | {row[8]} |")
            print(f"| Whole address (fine) | {row[9]} | {row[10]} |\n")
        pins, rows = common_rows(rep)
        if len(rows) == 2 and rows[0][1] == rows[1][1]:
            rows = rows[:1]  # no gold label here is one libpostal cannot produce: `shared` repeats `all`
        if rows:
            note = (" *Shared* leaves out the addresses with a gold label libpostal cannot produce." if len(rows) > 1
                    else " Every gold label here is one libpostal can produce.")
            print(f"With libpostal, on the common label set ({pins.split('. Model load')[0]}).{note}\n")
            print("| Addresses | Count | Ours: whole | usaddress: whole | libpostal: whole | Ours: tokens | usaddress: tokens | libpostal: tokens |")
            print("|---|---|---|---|---|---|---|---|")
            for r in rows:
                print("| " + " | ".join(r) + " |")
            print()
    if not found:
        print("## Geocode benchmark\n\nSkipped: `local-data/geocode-benchmark/` is not here.\n")


if __name__ == "__main__":
    main()
