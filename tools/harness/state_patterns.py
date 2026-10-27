#!/usr/bin/env python3
"""Per-state street-pattern counts: the evidence for the state rules (#53, for #8 and #11).

    python tools/harness/state_patterns.py --input local-data/netsyms-2026/records.parquet [--confirm]
    python tools/harness/state_patterns.py --nad local-data/nad-2026/nad_r24.parquet [--confirm]

Counts, by state and source, how many rows match each street pattern in PATTERNS (Texas `RR`,
`PR 123`, county-road forms, hyphenated house numbers, Puerto Rico `URB` and Spanish words, the
state-route spellings, a trailing number in the street) and how many rows end in a word that is
not in the suffix table. It reads the text of the street line only and does not parse, so a
count says what the text looks like, not how doorplate reads it.

- `--input` reads a records file (`tools/ingest/`): `line1` and `state`, grouped by `source`.
- `--nad` reads the National Address Database Parquet and builds the street line from
  `AddNo_Full` and `StNam_Full`; its source is `nad`.

Like the other harness scripts it prints a plan and exits until `--confirm`. The output goes to
`--out` (default `local-data/state-patterns/NAME/`): `state_patterns.csv` (source, state, pattern,
rows, matches), `last_words.csv` (the most common last words not in the suffix table, with a
minimum count, so they are words of the vocabulary, never rows) and `state_patterns.md` (a table
per pattern by state). Counts only (docs/data-policy.md): no row, no house number and no street
name is printed or written, and a reader error prints only the exception type. This library formats
and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import csv
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "crates" / "doorplate" / "data"
DEFAULT_OUT = ROOT / "local-data" / "state-patterns"
MIN_WORD_COUNT = 100  # a last word is listed only when this many rows end in it
TOP_WORDS = 200

# Patterns run on the normalized street line `s`: upper case, `. , #` turned into spaces, runs of
# spaces collapsed. `NUM` is a house number led street (so a rural route, which has none, is
# told from a street word). Each entry: name -> (regex, what it counts, which issue it feeds).
PATTERNS = {
    # Texas: Ranch Road, or Rural Route? (#8)
    "rr_rural_route": (r"^RR ?[0-9]", "line starts `RR` + number (a rural route form)", "#8"),
    "rr_street_word": (r"^[0-9]+[A-Z]? (.* )?RR( |$)", "`RR` as a word after a house number", "#8"),
    "ranch_road": (r"( |^)RANCH (ROAD|RD)( |$)", "`RANCH ROAD` spelled out", "#8"),
    "rm_fm_number": (r"( |^)(RM|FM|RANCH TO MARKET|FARM TO MARKET) ?[0-9]", "`RM` / `FM` + number (Texas)", "#8"),
    # `PR` + number: Texas private road, or Puerto Rico? (#8)
    "pr_number": (r"^[0-9]+[A-Z]? (.* )?PR ?[0-9]", "`PR` + number after a house number", "#8"),
    "pr_road": (r"( |^)(PR|PRIVATE ROAD|PRIV RD) ?(ROAD|RD)?( |$)", "`PR` / `PRIVATE ROAD` words", "#8"),
    # County roads (Alabama `LEE ROAD 123`, `CTY RD 5`, `CO RD 5`) (#8, #11)
    "cty_form": (r"( |^)(CTY|CNTY)( |$)", "`CTY` / `CNTY` word", "#8"),
    "co_form": (r"( |^)CO ?(RD|ROAD|HWY|HIGHWAY|ROUTE|RTE|ST)( |$)", "`CO` + road word", "#8"),
    "county_road_word": (r"( |^)COUNTY ?(ROAD|RD|HWY|HIGHWAY|ROUTE|RTE|LINE)( |$)", "`COUNTY ROAD` and kin spelled out", "#8"),
    "cr_number": (r"( |^)CR ?[0-9]", "`CR` + number", "#8"),
    "name_road_number": (r"^[0-9]+[A-Z]? [A-Z]+( [A-Z]+)? (ROAD|RD) [0-9]+[A-Z]?( [NSEW]{1,2})?$",
                         "`<NAME> ROAD <number>` (Alabama county roads; `COUNTY ROAD 7` counts here too)", "#8"),
    # House numbers
    "hyphen_house_number": (r"^[0-9]+-[0-9]+[A-Z]?( |$)", "hyphenated house number (Queens style)", "#99, #100"),
    # Puerto Rico
    "urb": (r"( |^)URB( |$)", "`URB` (urbanization)", "#8"),
    "spanish_words": (r"( |^)(CALLE|AVENIDA|CARR|CARRETERA|CAMINO|PASEO|SECTOR|BARRIO|BO|RESIDENCIAL|RES|KM)( |$)",
                      "Spanish street words", "#8"),
    # State route spellings (the Florida `SR` rule)
    "sr_number": (r"( |^)SR ?[0-9]", "`SR` + number", "#8, #11"),
    "state_route_words": (r"( |^)STATE (ROUTE|ROAD|RT|RTE|HWY|HIGHWAY)( |$)", "`STATE ROUTE` / `STATE ROAD` and kin", "#8, #11"),
    "st_rt": (r"( |^)ST (RT|RTE|RD|HWY)( |$)", "`ST RT` / `ST RTE` / `ST HWY` (street, or state?)", "#8, #11"),
    "sh_number": (r"( |^)(SH|STH) ?[0-9]", "`SH` / `STH` + number", "#8, #11"),
    "hwy_word": (r"( |^)(HWY|HIGHWAY)( |$)", "`HWY` / `HIGHWAY` word", "#11"),
}


def suffix_forms():
    """Every spelling of a street suffix in the lexicon (forms and observed)."""
    data = tomllib.loads((DATA / "suffixes.toml").read_text())
    out = set()
    for e in data["suffix"]:
        out.update(e.get("forms", []))
        out.update(e.get("observed", []))
        out.add(e["name"])
        out.add(e["abbr"])
    return {w.upper() for w in out}


def directional_forms():
    data = tomllib.loads((DATA / "directionals.toml").read_text())
    out = set()
    for e in data["directional"]:
        out.update(e.get("forms", []))
        out.add(e["abbr"])
    return {w.upper() for w in out}


def q(s):
    return s.replace("'", "''")


def street_expr(kind):
    """The SQL for the normalized street line over the input table `src`."""
    if kind == "nad":
        raw = "coalesce(AddNo_Full, '') || ' ' || coalesce(StNam_Full, '')"
    else:
        raw = "coalesce(line1, '')"
    return ("trim(regexp_replace(regexp_replace(upper(" + raw + "), '[.,#]', ' ', 'g'), ' +', ' ', 'g'))")


def build_sql(kind, table, suffixes, directionals):
    state = "State" if kind == "nad" else "state"
    source = "'nad'" if kind == "nad" else "coalesce(source, '')"
    sfx = "|".join(sorted((s for s in suffixes if len(s) > 1), key=len, reverse=True))
    dirs = "|".join(sorted(directionals, key=len, reverse=True))
    trailing = f"( |^)({sfx}) [0-9]+[A-Z]?( ({dirs}))?$"
    # Trailing number in the street: a suffix word then a number (`SHORE ROAD 20`).
    pats = {n: r for n, (r, _, _) in PATTERNS.items()}
    pats["trailing_number"] = trailing
    cols = ",\n  ".join(
        f"count(*) filter (where regexp_matches(s, '{q(r)}')) as \"{n}\"" for n, r in pats.items())
    # Last word of the street (less a trailing directional), when the street has a name and a type word.
    core = f"regexp_replace(s, ' ({dirs})$', '')"
    last = f"regexp_extract({core}, '([A-Z]+)$', 1)"
    unknown = (f"count(*) filter (where regexp_matches(s, '^[0-9]+[A-Z]? [A-Z0-9]+ [A-Z]+') "
               f"and {last} <> '' and not list_contains(sfx_list, {last})) as \"unknown_last_word\"")
    base = (f"select {source} as source, upper(trim({state})) as state, {street_expr(kind)} as s "
            f"from {table}")
    sfx_list = "[" + ", ".join(f"'{q(w)}'" for w in sorted(suffixes | directionals)) + "]"
    sql = (f"with src as ({base}), cfg as (select {sfx_list} as sfx_list)\n"
           f"select source, state, count(*) as total,\n  {cols},\n  {unknown}\n"
           f"from src, cfg group by source, state order by source, state")
    names = list(pats) + ["unknown_last_word"]
    words_sql = (f"with src as ({base}), cfg as (select {sfx_list} as sfx_list)\n"
                 f"select {last} as word, count(*) as rows, count(distinct state) as states from src, cfg "
                 f"where regexp_matches(s, '^[0-9]+[A-Z]? [A-Z0-9]+ [A-Z]+') and {last} <> '' "
                 f"and not list_contains(sfx_list, {last}) group by word "
                 f"having count(*) >= {MIN_WORD_COUNT} order by rows desc limit {TOP_WORDS}")
    return sql, words_sql, names


def write_outputs(out, rows, names, words, source_note):
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "state_patterns.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "state", "pattern", "rows", "matches"])
        for r in rows:
            for i, n in enumerate(names):
                w.writerow([r[0], r[1], n, r[2], r[3 + i]])
    with open(out / "last_words.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word", "rows", "states"])
        w.writerows(words)
    descr = {n: (d, i) for n, (_, d, i) in PATTERNS.items()}
    descr["trailing_number"] = ("a suffix word then a number (`SHORE ROAD 20`)", "#8, #37 class F")
    descr["unknown_last_word"] = (
        "street of a name and a type position whose last word is not in the suffix table or the directionals",
        "#8")
    sources = sorted({r[0] for r in rows})
    lines = ["# Street patterns by state", "", source_note, "",
             "Counts only (`docs/data-policy.md`). A count is rows whose street line has the text shape; "
             "it is not a parse and not a verdict. 'per 10k' is matches per 10,000 rows of the state.", ""]
    for src in sources:
        srows = [r for r in rows if r[0] == src]
        total = sum(r[2] for r in srows)
        lines += [f"## Source `{src or '(none)'}`: {total:,} rows", "",
                  "| pattern | feeds | matches | per 10k |", "|---|---|---:|---:|"]
        for i, n in enumerate(names):
            m = sum(r[3 + i] for r in srows)
            lines.append(f"| `{n}` | {descr[n][1]} | {m:,} | {10000 * m / total:.1f} |" if total else f"| `{n}` | | 0 | 0 |")
        lines.append("")
        for i, n in enumerate(names):
            top = sorted((r for r in srows if r[3 + i] > 0), key=lambda r: -r[3 + i])
            if not top:
                continue
            lines += [f"### `{n}`: {descr[n][0]}", "", "| state | rows | matches | per 10k |", "|---|---:|---:|---:|"]
            for r in top:
                lines.append(f"| {r[1] or '?'} | {r[2]:,} | {r[3 + i]:,} | {10000 * r[3 + i] / r[2]:.1f} |")
            lines.append("")
    (out / "state_patterns.md").write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--input", help="a records.parquet from tools/ingest/")
    g.add_argument("--nad", help="the National Address Database Parquet (local-data/nad-2026/nad_r24.parquet)")
    ap.add_argument("--out", help=f"output folder (default {DEFAULT_OUT.relative_to(ROOT)}/NAME)")
    ap.add_argument("--threads", type=int, help="DuckDB threads (default: all)")
    ap.add_argument("--confirm", action="store_true", help="run (without it, only print the plan)")
    args = ap.parse_args()

    path = Path(args.nad or args.input)
    kind = "nad" if args.nad else "records"
    if not path.is_file():
        sys.exit(f"{path} is not a file")
    out = Path(args.out) if args.out else DEFAULT_OUT / (path.parent.name + "-" + path.stem)
    print(f"input:     {path} ({kind}, {path.stat().st_size / 1e9:.2f} GB)")
    print(f"patterns:  {len(PATTERNS) + 2} ({', '.join(PATTERNS)}, trailing_number, unknown_last_word)")
    print(f"output:    {out}/ (state_patterns.csv, last_words.csv, state_patterns.md; counts only)")
    if not args.confirm:
        print("plan only; add --confirm to run")
        return

    import duckdb

    try:
        con = duckdb.connect()
        if args.threads:
            con.execute(f"set threads = {int(args.threads)}")
        table = f"read_parquet('{q(str(path))}')"
        sql, words_sql, names = build_sql(kind, table, suffix_forms(), directional_forms())
        rows = con.execute(sql).fetchall()
        words = con.execute(words_sql).fetchall()
    except Exception as e:  # DuckDB errors can quote source rows: print the type only
        sys.exit(f"failed: {type(e).__name__}")
    note = f"Input: `{path.name}` ({kind}); made by `tools/harness/state_patterns.py` (#53)."
    write_outputs(out, rows, names, words, note)
    print(f"{sum(r[2] for r in rows):,} rows, {len(rows)} source/state groups; wrote {out}/")


if __name__ == "__main__":
    main()
