#!/usr/bin/env python3
"""The worklist: a ranked list of failure shapes for a run of tools/harness/run.py (#93, step 4).

    python tools/harness/shapes_report.py RUN_ID_OR_PATH [--before RUN] [--top 10]

For each source and role in the run it reports, as counts only:

- the rows, the share with a warning, with an `unparsed` remainder, and with each mismatch code;
- the warning codes by rate;
- the top failure shapes: for rows with an `unparsed` remainder, the shape of the input and of
  the leftover; for each of the top warning codes, the shapes of the inputs. A shape turns
  letters into `a` and digits into `9` and collapses runs (`123 N OAK ST APT 4` is
  `9 a a a a 9`), so a shape is a form of address, never an address;
- the input shapes behind a `street` mismatch (#112), and for `missing_street_number` how many of
  its rows start with a spelled-out number (`ONE PENN PLAZA`) and have a street suffix: a measure
  of building numbers written as words, nothing more (`ONE MILE RD` is a street);
- the style of the inputs that fail (case, unit forms, commas, spelled-out types), beside the
  style of all inputs (a sample of each), reusing `line_styles` of tools/benchsuite/shapes.py.

For a source that groups its rows (FMCSA's country, Netsyms's original provider), a table of the
providers comes first, and `--provider NAME` reports one provider alone (`shapes-NAME.md`): a
source's foreign or odd rows then do not hide its US findings.

With `--before RUN` it also shows what changed between two runs of the same input (the warning
codes, the unparsed share and the shapes whose counts moved most), for a rule's before/after.

The input text is read from the records file named in the run's manifest and joined to the
flagged rows by `(source, role, record_id)`; a run made from the Netsyms SQLite (`--db`) has no
text to join, so it gets the leftover shapes only. The report is written to `shapes.md` in the
run directory. Counts only (never a row), so it may be quoted under docs/data-policy.md. This
library formats and parses; it does not validate that an address exists or can receive mail.

This does not train the parser. Each shape is a question; a fix still needs a source for its
rule (docs/usps-pub28-notes.md) and goes through the rule-PR loop in docs/tools/harness.md.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_ROOT = ROOT / "local-data" / "netsyms-runs"
MAX_SHAPE = 48

MACRO = ("create or replace macro shape(x) as "
         "regexp_replace(regexp_replace(coalesce(x, ''), '[A-Za-z]+', 'a', 'g'), '[0-9]+', '9', 'g')")
# The shape of the whole input text of a record: line 1, line 2 and the last line, when present.
INPUT_SHAPE = ("shape(r.line1) || case when r.line2 is not null then ' | ' || shape(r.line2) else '' end"
               " || case when r.last_line is not null then ' | ' || shape(r.last_line) else '' end")


def clip(s):
    return s if len(s) <= MAX_SHAPE else s[:MAX_SHAPE - 1] + "…"


def open_run(arg, partial):
    run = Path(arg)
    if not run.is_dir():
        run = DEFAULT_ROOT / arg
    if not (run / "manifest.json").exists():
        sys.exit(f"{run} is not a run directory")
    if not (run / "DONE").exists() and not partial:
        sys.exit(f"{run} has no DONE marker (incomplete); resume it, or pass --partial")
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest.get("schema_version") not in (3, 4, 5, 6, 7, 8, 9):
        sys.exit(f"{run}: schema_version {manifest.get('schema_version')} has no role column (it needs 3 to 9); "
                 "rerun with the current tools/harness/run.py")
    return run, manifest


def connect(run, manifest, provider=None):
    """A DuckDB connection with views over the run's artifacts and, when there is a records
    file, over its input text. Returns (connection, has_text)."""
    import duckdb

    con = duckdb.connect()
    con.execute(MACRO)
    where = f" where provider = '{provider.replace(chr(39), chr(39) * 2)}'" if provider else ""
    for t in ("agg_state_source", "agg_warnings", "flagged"):
        con.execute(f"create view {t} as select * from read_parquet('{run / t}/*.parquet'){where}")
    inp = manifest["input"]
    rec = Path(inp["path"])
    has_text = inp.get("kind") == "records" and rec.exists()
    if has_text:
        st = rec.stat()
        if st.st_size != inp.get("size"):
            print(f"note: {rec.name} has changed size since the run; input shapes may not match", file=sys.stderr)
        have = {r[0] for r in con.execute(f"describe select * from read_parquet('{rec}')").fetchall()}
        cols = ", ".join(c if c in have else f"NULL AS {c}" for c in
                         ("source", "role", "record_id", "provider", "line1", "line2", "last_line"))
        con.execute(f"create view recs as select {cols} from read_parquet('{rec}'){where}")
    return con, has_text


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        out.append("| " + " | ".join(f"{c:,}" if isinstance(c, int) else
                                      f"{c:.2f}%" if isinstance(c, float) else str(c) for c in r) + " |")
    return out


def keys(con):
    return con.execute("select source, role from agg_state_source group by 1, 2 order by 1, 2").fetchall()


def totals(con, source, role):
    cols = {r[0] for r in con.execute("describe agg_state_source").fetchall()}
    want = ["rows", "with_warnings", "no_result", "flagged", "m_number", "m_state", "m_zip5", "m_zip4",
            "m_city", "m_unit", "m_street", "last_line_rows", "last_line_crossed"]
    want = [c for c in want if c in cols]
    vals = con.execute("select " + ", ".join(f"sum({c})" for c in want)
                       + " from agg_state_source where source = ? and role = ?", [source, role]).fetchone()
    t = dict(zip(want, (int(v or 0) for v in vals)))
    t["unparsed"] = con.execute("select count(*) from flagged where source = ? and role = ? "
                                "and unparsed is not null", [source, role]).fetchone()[0]
    return t


def provider_table(con, source, role, top):
    """The providers (a country, a license type, an original data provider) with the most rows."""
    rows = con.execute(
        "select provider, sum(rows) n, 100.0 * sum(with_warnings) / sum(rows), 100.0 * sum(flagged) / sum(rows) "
        "from agg_state_source where source = ? and role = ? group by 1 order by 2 desc", [source, role]).fetchall()
    if len(rows) < 2:
        return []
    out = ["### Providers (use `--provider NAME` to report one alone)", ""]
    out += md_table(["provider", "rows", "with a warning", "flagged"],
                    [(p or "(none)", int(n), w, f) for p, n, w, f in rows[:top]])
    if len(rows) > top:
        out.append(f"\n({len(rows) - top:,} more providers)")
    return out + [""]


def warning_counts(con, source, role):
    return dict(con.execute("select code, sum(n) from agg_warnings where source = ? and role = ? group by 1",
                            [source, role]).fetchall())


def unparsed_shapes(con, source, role, has_text):
    """(input shape, leftover shape) -> rows, for rows with an unparsed remainder."""
    if has_text:
        sql = (f"select {INPUT_SHAPE} as i, shape(f.unparsed) as u, count(*) from flagged f "
               "join recs r on r.source = f.source and r.role = f.role and r.record_id = f.record_id "
               "where f.source = ? and f.role = ? and f.unparsed is not null group by 1, 2")
    else:
        sql = ("select '' as i, shape(unparsed) as u, count(*) from flagged "
               "where source = ? and role = ? and unparsed is not null group by 1, 2")
    return {(clip(i), clip(u)): n for i, u, n in con.execute(sql, [source, role]).fetchall()}


def code_shapes(con, source, role, code):
    """input shape -> rows, for rows flagged with one warning code (needs the input text)."""
    sql = (f"select {INPUT_SHAPE} as i, count(*) from flagged f "
           "join recs r on r.source = f.source and r.role = f.role and r.record_id = f.record_id "
           "where f.source = ? and f.role = ? and list_contains(string_split(f.warnings, ','), ?) group by 1")
    return {clip(i): n for i, n in con.execute(sql, [source, role, code]).fetchall()}


NUMBER_WORDS = ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN", "ELEVEN", "TWELVE",
                "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN", "TWENTY")


def mismatch_shapes(con, source, role, code):
    """input shape -> rows, for rows flagged with one mismatch code (needs the input text)."""
    sql = (f"select {INPUT_SHAPE} as i, count(*) from flagged f "
           "join recs r on r.source = f.source and r.role = f.role and r.record_id = f.record_id "
           "where f.source = ? and f.role = ? and list_contains(string_split(f.mismatches, ','), ?) group by 1")
    return {clip(i): n for i, n in con.execute(sql, [source, role, code]).fetchall()}


def number_word_rows(con, source, role):
    """Leading number word -> rows, for `missing_street_number` rows whose line 1 starts with one and
    whose parse found a street suffix (needs the input text). Counts only."""
    words = "|".join(NUMBER_WORDS)
    sql = ("select regexp_extract(upper(trim(r.line1)), '^(" + words + ")( |$)', 1) as w, count(*) from flagged f "
           "join recs r on r.source = f.source and r.role = f.role and r.record_id = f.record_id "
           "where f.source = ? and f.role = ? and list_contains(string_split(f.warnings, ','), 'missing_street_number') "
           "and f.street_suffix is not null and regexp_matches(upper(trim(r.line1)), '^(" + words + ")( |$)') group by 1")
    return dict(con.execute(sql, [source, role]).fetchall())


def styles(con, source, role, sample):
    """Style counts (tools/benchsuite/shapes.py: line_styles) of a sample of the inputs that have
    an unparsed remainder and of a sample of all inputs of the role."""
    sys.path.insert(0, str(ROOT / "tools" / "benchsuite"))
    try:
        from shapes import line_styles
    except Exception as e:  # pandas missing, say
        return None, None, type(e).__name__
    bad = [r[0] for r in con.execute(
        "select r.line1 from flagged f join recs r on r.source = f.source and r.role = f.role "
        "and r.record_id = f.record_id where f.source = ? and f.role = ? and f.unparsed is not null "
        f"and r.line1 is not null using sample {int(sample)} rows", [source, role]).fetchall()]
    allr = [r[0] for r in con.execute(
        f"select line1 from recs where source = ? and role = ? and line1 is not null using sample {int(sample)} rows",
        [source, role]).fetchall()]
    return line_styles(bad), line_styles(allr), None


def section(con, source, role, has_text, top, sample):
    t = totals(con, source, role)
    n = t["rows"] or 1
    warns = warning_counts(con, source, role)
    out = [f"## {source} / {role}", "",
           f"{t['rows']:,} rows. With a warning {100 * t['with_warnings'] / n:.2f}%, flagged "
           f"{100 * t['flagged'] / n:.2f}%, with an `unparsed` remainder {t['unparsed']:,} "
           f"({100 * t['unparsed'] / n:.2f}%).", ""]
    mism = [(k[2:], t[k]) for k in ("m_number", "m_state", "m_zip5", "m_zip4", "m_city", "m_unit", "m_street")
            if k in t and t[k]]
    if mism:
        out += ["Mismatches (rows): " + ", ".join(f"{k} {v:,} ({100 * v / n:.2f}%)" for k, v in mism), ""]
    if t.get("last_line_rows"):
        out += [f"Last-line rows: {t['last_line_rows']:,}, boundary crossings {t.get('last_line_crossed', 0):,}.", ""]
    out += provider_table(con, source, role, top)
    ranked = sorted(warns.items(), key=lambda kv: -kv[1])
    out += ["### Warning codes", ""] + md_table(
        ["code", "rows", "share of rows"], [(c, k, 100 * k / n) for c, k in ranked[:top]]) + [""]
    shapes = unparsed_shapes(con, source, role, has_text)
    if shapes:
        total = sum(shapes.values())
        rows = sorted(shapes.items(), key=lambda kv: -kv[1])[:top]
        out += ["### Unparsed remainder: shape of the input -> shape of the leftover", ""]
        out += md_table(["input shape", "leftover shape", "rows", "share of unparsed"],
                        [(f"`{i}`" if i else "(not available)", f"`{u}`", k, 100 * k / total) for (i, u), k in rows]) + [""]
    if has_text:
        for code, k in ranked[:3]:
            cs = code_shapes(con, source, role, code)
            if not cs:
                continue
            out += [f"### `{code}`: top input shapes ({k:,} rows)", ""]
            out += md_table(["input shape", "rows", "share of the code"],
                            [(f"`{i}`", c, 100 * c / k) for i, c in sorted(cs.items(), key=lambda kv: -kv[1])[:top]]) + [""]
        if t.get("m_street"):
            ms = mismatch_shapes(con, source, role, "street")
            if ms:
                out += [f"### `street` mismatch: top input shapes ({t['m_street']:,} rows, "
                        f"{100 * t['m_street'] / n:.2f}% of the rows)", ""]
                out += md_table(["input shape", "rows", "share of the mismatch"],
                                [(f"`{i}`", c, 100 * c / t["m_street"])
                                 for i, c in sorted(ms.items(), key=lambda kv: -kv[1])[:top]]) + [""]
        if warns.get("missing_street_number"):
            nw = number_word_rows(con, source, role)
            total = warns["missing_street_number"]
            out += [f"### `missing_street_number`: a spelled-out number and a street suffix", "",
                    f"{sum(nw.values()):,} of {total:,} rows ({100 * sum(nw.values()) / total:.2f}%) start with a number "
                    "word and have a street suffix (`ONE PENN PLAZA`; `ONE MILE RD` is one too, so this is an upper "
                    "bound for building numbers)." + (" By word: " + ", ".join(
                        f"{w} {k:,}" for w, k in sorted(nw.items(), key=lambda kv: -kv[1])[:top]) + "." if nw else ""), ""]
        if t["unparsed"]:
            bad, allr, err = styles(con, source, role, sample)
            if err:
                out += [f"(style comparison skipped: {err} importing tools/benchsuite/shapes.py)", ""]
            elif bad and bad["n"] and allr["n"]:
                names = sorted(k for k in set(bad) | set(allr) if k != "n")
                out += [f"### Style of inputs with an unparsed remainder, against all inputs "
                        f"(samples of {bad['n']:,} and {allr['n']:,})", ""]
                out += md_table(["style", "unparsed", "all"], [(k, 100 * bad[k] / bad["n"], 100 * allr[k] / allr["n"])
                                                              for k in names]) + [""]
    return out, t, warns, shapes


def change_section(source, role, before, after, top):
    (tb, wb, sb), (ta, wa, sa) = before, after
    out = [f"### {source} / {role}: change", ""]
    rows = [("rows", tb["rows"], ta["rows"]), ("with a warning", tb["with_warnings"], ta["with_warnings"]),
            ("unparsed remainder", tb["unparsed"], ta["unparsed"])]
    out += md_table(["", "before", "after", "change"], [(k, a, b, f"{b - a:+,}") for k, a, b in rows]) + [""]
    codes = sorted(set(wb) | set(wa), key=lambda c: -abs(wa.get(c, 0) - wb.get(c, 0)))[:top]
    out += md_table(["warning code", "before", "after", "change"],
                    [(c, wb.get(c, 0), wa.get(c, 0), f"{wa.get(c, 0) - wb.get(c, 0):+,}") for c in codes
                     if wa.get(c, 0) != wb.get(c, 0)]) + [""]
    moved = sorted(set(sb) | set(sa), key=lambda k: -abs(sa.get(k, 0) - sb.get(k, 0)))[:top]
    moved = [k for k in moved if sa.get(k, 0) != sb.get(k, 0)]
    if moved:
        out += ["Unparsed remainder shapes that moved most:", ""]
        out += md_table(["input shape", "leftover shape", "before", "after", "change"],
                        [(f"`{i}`" if i else "(n/a)", f"`{u}`", sb.get((i, u), 0), sa.get((i, u), 0),
                          f"{sa.get((i, u), 0) - sb.get((i, u), 0):+,}") for i, u in moved]) + [""]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run", help="run id (under local-data/netsyms-runs/) or a path")
    ap.add_argument("--before", help="an earlier run of the same input, for the change section")
    ap.add_argument("--provider", help="report only this provider (a country, say), for sources that group rows")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--sample", type=int, default=200_000, help="rows per style sample (default 200,000)")
    ap.add_argument("--partial", action="store_true", help="allow a run without a DONE marker")
    ap.add_argument("--out", type=Path, help="where to write the report (default: shapes.md in the run)")
    args = ap.parse_args(argv)
    run, manifest = open_run(args.run, args.partial)
    try:
        con, has_text = connect(run, manifest, args.provider)
        out = [f"# Shapes: run {manifest['run_id']}", "",
               f"- commit `{manifest['git_commit'][:10]}`{' (dirty tree)' if manifest['git_dirty'] else ''}, "
               f"doorplate {manifest['doorplate_version']}, data tables `{manifest['data_tables_sha256'][:12]}`",
               f"- input `{Path(manifest['input']['path']).name}` ({manifest['input'].get('kind', 'records')})"
               + ("" if has_text else "; no input text to join, so shapes are of the leftovers only")
               + (f"; provider `{args.provider}` only" if args.provider else ""), "",
               "Counts only. A shape turns letters into `a` and digits into `9` and collapses runs. A "
               "warning or a leftover is a question about the parser or about the source, not a verdict "
               "on either. Rule changes found here go through the rule-PR loop "
               "(docs/tools/harness.md); every rule needs a source.", ""]
        prev = None
        if args.before:
            brun, bman = open_run(args.before, args.partial)
            bcon, bhas = connect(brun, bman, args.provider)
            prev = {k: (totals(bcon, *k), warning_counts(bcon, *k), unparsed_shapes(bcon, *k, bhas))
                    for k in keys(bcon)}
            out += [f"- compared with run {bman['run_id']} (commit `{bman['git_commit'][:10]}`)", ""]
        for source, role in keys(con):
            lines, t, w, s = section(con, source, role, has_text, args.top, args.sample)
            out += lines
            if prev and (source, role) in prev:
                out += change_section(source, role, prev[(source, role)], (t, w, s), args.top)
    except SystemExit:
        raise
    except Exception as e:  # DuckDB messages can quote rows (docs/data-policy.md)
        sys.exit(f"shapes report failed: {type(e).__name__}")
    text = "\n".join(out) + "\n"
    dest = args.out or run / ("shapes.md" if not args.provider else f"shapes-{''.join(ch for ch in args.provider if ch.isalnum())}.md")
    dest.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
