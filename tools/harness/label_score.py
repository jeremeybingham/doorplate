#!/usr/bin/env python3
"""Score doorplate against the labeled parts of any records file (#93, step 3).

    python tools/harness/label_score.py local-data/nad-2026/records.parquet               # the plan
    python tools/harness/label_score.py local-data/nad-2026/records.parquet --confirm
    python tools/harness/label_score.py local-data/nc-voter-2026/records_current.parquet \\
        --labels local-data/nc-voter-2026/records_snapshot.parquet --confirm

A records file (docs/tools/ingest.md) may carry `label_*` columns: the parts a source stores
separately. The scorer parses each row's `line1`, `line2`, `city`, `state` and `zip` (or its
`last_line`, joined as in run.py) and compares our parts with the labels wherever a label is
present: the predirectional, postdirectional, suffix, unit, house number and street name. It
prints counts only, per source and role: for each field the rows labeled and the rows where we
differ, the top (label -> ours) pairs for the lexicon fields, the top shapes (letters `a`, digits
`9`) of the others, and the top states. Never a row, so the output may be quoted under
docs/data-policy.md.

With `--labels OTHER.parquet`, the labels come from another file: rows are paired by
`(role, pair_id)` (ids that are unique in both files), our parse of RECORDS' one-line form is
scored against OTHER's labels, and the result is reported as a pair score, apart from the rest.
That answers whether parsing the as-entered text gives back the parts someone else entered.

A label's `EXT` post-modifier (`MAIN ST EXT`, labeled type `ST`, modifier `EXT`) is the suffix: Pub 28
appendix C1 lists `EXT` as a primary suffix, so `100 MAIN ST EXT` is read as the street `MAIN STREET`
with the suffix `EXT`. The scorer compares our suffix with the modifier and accepts the name with its
type spelled out (#112).

`--examples FILE` writes the disagreements to a local file, never to the terminal: one tab-separated
line per example with the source, role, field, record id (and pair id), and the label and our value.
FILE must be under `local-data/` (git-ignored). It keeps at most `--examples-max` per distinct
label -> ours pair (or shape pair), so rare pairs show up too. Open the records by id by hand and
report only the finding (docs/data-policy.md).

A source's labels are its providers' choices, not ground truth: many put the suffix inside the
name and leave the type empty (those rows are skipped, since there is no label to compare), and a
unit may be spelled out (`Apartment 4`). A disagreement is a question to look into, not a bug
count. This library formats and parses; it does not validate that an address exists or can
receive mail.
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run  # noqa: E402  (the harness: row parsing shared with run.py)

ROOT = run.ROOT
LABELS = ["label_number_prefix", "label_number", "label_number_suffix", "label_predir", "label_pretype",
          "label_name", "label_type", "label_postdir", "label_postmod", "label_unit_type",
          "label_unit", "label_building"]
BASE = ["record_id", "source", "role", "provider", "line1", "line2", "city", "state", "zip",
        "last_line", "label_number"]
FIELDS = ["predirectional", "postdirectional", "suffix", "unit", "number", "name"]
LEXICON = {"predirectional": "dir", "postdirectional": "post", "suffix": "suf"}


def strip(s):
    return (s or "").strip()


def compact(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def shape(s):
    """Letters become `a`, digits `9`, runs collapse; other characters stay."""
    out = re.sub(r"[A-Za-z]+", "a", s or "")
    return re.sub(r"[0-9]+", "9", out)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("records", type=Path, help="a records.parquet with label_* columns")
    ap.add_argument("--labels", type=Path, help="take the labels from this records file, paired by (role, pair_id)")
    ap.add_argument("--fields", default=",".join(FIELDS), help=f"comma-separated, from {', '.join(FIELDS)}")
    ap.add_argument("--any-zip", action="store_true",
                    help="with --labels: also score pairs whose ZIP codes differ (by default they are dropped: "
                         "the two files may be months apart, and a voter who moved is not a disagreement)")
    ap.add_argument("--any-number", action="store_true",
                    help="with --labels: score the other fields even when the house numbers differ (by default "
                         "they are skipped: a voter who moved within a ZIP code has another street, not a disagreement)")
    ap.add_argument("--by-warning", action="store_true",
                    help="also print, per warning code, the rows with it and how often we differ from the labels "
                         "on those rows (counts only): the measured reliability of each warning (#102)")
    ap.add_argument("--examples", type=Path, metavar="FILE",
                    help="write the disagreements (record ids, fields, label -> ours) to this local file, never "
                         "to the terminal; it must be under local-data/")
    ap.add_argument("--examples-max", type=int, default=5,
                    help="with --examples: at most this many per distinct label -> ours pair (default 5)")
    ap.add_argument("--limit", type=int, help="score only about this many rows (a test slice)")
    ap.add_argument("--chunk-rows", type=int, default=200_000)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--out", type=Path, help="also write the report here (counts only)")
    ap.add_argument("--confirm", action="store_true", help="actually score (default: print the plan)")
    return ap.parse_args(argv)


def columns(con, path):
    return [r[0] for r in con.execute("describe select * from read_parquet(?)", [str(path)]).fetchall()]


def select_list(have, alias, wanted, source_alias=None):
    return ", ".join(f"{alias}.{c}" if c in have else f"NULL AS {c}" for c in wanted)


class Canon:
    """A source's spelling of a suffix or directional, as our parser would write it."""

    def __init__(self):
        import doorplate

        self.doorplate = doorplate
        self.cache = {}

    def __call__(self, kind, v):
        v = strip(v)
        if not v:
            return ""
        key = (kind, v.upper())
        if key not in self.cache:
            text = {"suf": f"1 MAIN {v}", "dir": f"1 {v} MAIN ST", "post": f"1 MAIN ST {v}"}[kind]
            a = self.doorplate.parse_fields(line1=text, city="MIAMI", state="FL", zip="33101")
            self.cache[key] = str({"suf": a.street_suffix, "dir": a.street_dir_prefix,
                                   "post": a.street_dir_suffix}[kind] or "?" + compact(v))
        return self.cache[key]


    def long_word(self, v):
        """The spelled-out form of a suffix spelling, upper case (`ST` is `STREET`), or ''."""
        v = strip(v)
        key = ("long", v.upper())
        if key not in self.cache:
            a = self.doorplate.parse_fields(line1=f"1 MAIN {v}", city="MIAMI", state="FL", zip="33101")
            line1 = a.to_long()["line1"] or ""
            self.cache[key] = line1.upper().split()[-1] if v and a.street_suffix else ""
        return self.cache[key]


class Result:
    """Counts per (source, role)."""

    def __init__(self):
        self.c = defaultdict(Counter)
        self.pairs = defaultdict(Counter)    # (src, role, field) -> (want, got)
        self.shapes = defaultdict(Counter)   # (src, role, field) -> (label shape, our shape)
        self.states = defaultdict(Counter)   # (src, role, field) -> state
        self.dropped = Counter()             # (src, role) -> pairs dropped for a different ZIP
        self.pairs_seen = Counter()          # (src, role) -> pairs joined
        self.other_number = Counter()        # (src, role) -> pairs whose other fields were skipped (number differs)
        self.w = defaultdict(Counter)        # (src, role, warning code or "(none)") -> rows, "<field>: labeled/differ"
        self.example_max = 0                 # --examples-max, 0 when --examples is off
        self.examples = []                   # (src, role, field, record id, pair id, want, got)
        self.example_n = Counter()           # (src, role, field, want or shape, got or shape) -> kept


def compare(row, lab, a, fields, canon, res, guard_number=False):
    """Count one parsed row against its labels. `lab` maps label column to its value. With
    `guard_number`, a row whose labeled house number differs from ours is counted for the
    `number` field only (the other fields would compare two different addresses)."""
    src, role, state = row[1] or "", row[2] or "", norm_state(row[7])
    key = (src, role)
    c = res.c[key]
    if a is None:
        c["no result"] += 1
        return
    c["rows"] += 1
    codes = [str(w) for w in a.warnings] or ["(none)"]
    for code in codes:
        res.w[key + (code,)]["rows"] += 1

    def count(field, labeled, differ, want="", got=""):
        if not labeled:
            return
        c[f"{field}: labeled"] += 1
        for code in codes:
            res.w[key + (code,)][f"{field}: labeled"] += 1
            if differ:
                res.w[key + (code,)][f"{field}: differ"] += 1
        if differ:
            c[f"{field}: differ"] += 1
            res.states[key + (field,)][state] += 1
            if field in LEXICON:
                res.pairs[key + (field,)][(want, got)] += 1
                group = (want, got)
            else:
                res.shapes[key + (field,)][(shape(want), shape(got))] += 1
                group = (shape(want), shape(got))
            if res.example_max and res.example_n[key + (field,) + group] < res.example_max:
                res.example_n[key + (field,) + group] += 1
                res.examples.append((src, role, field, str(row[0]), str(lab.get("_pair_id") or ""), want, got))

    if "number" in fields and strip(lab.get("label_number")):
        want = "".join(strip(lab.get(k)) for k in ("label_number_prefix", "label_number", "label_number_suffix"))
        differ = compact(want) != compact(a.street_number)
        count("number", True, differ, want, a.street_number or "")
        if differ and guard_number:
            res.other_number[key] += 1
            return
    elif guard_number and strip(lab.get("label_number")):
        want = "".join(strip(lab.get(k)) for k in ("label_number_prefix", "label_number", "label_number_suffix"))
        if compact(want) != compact(a.street_number):
            res.other_number[key] += 1
            return
    # A label's `EXT` post-modifier is the suffix (Pub 28 appendix C1); the type is part of our name.
    ext = canon("suf", lab.get("label_postmod")) == "EXT" and bool(strip(lab.get("label_type")))
    for field, col, ours in (("predirectional", "label_predir", a.street_dir_prefix),
                             ("postdirectional", "label_postdir", a.street_dir_suffix),
                             ("suffix", "label_type", a.street_suffix)):
        if field not in fields:
            continue
        raw = strip(lab.get(col))
        if raw:
            want, got = canon(LEXICON[field], "EXT" if ext and field == "suffix" else raw), str(ours or "")
            count(field, True, want != got, want, got)
    if "unit" in fields:
        raw = strip(lab.get("label_unit"))
        # Differ when the source labels a unit and we found none (spelled-out types are not compared).
        # A unit whose value is nowhere in the text we parsed is the source's, not a miss: counted apart.
        missing = bool(raw) and not a.unit_number
        if missing and compact(raw) not in compact(" ".join(strip(row[i]) for i in (4, 5, 9))):
            c["unit: not in the text"] += 1
            missing = False
        count("unit", bool(raw), missing, raw, a.unit_number or "")
    if "name" in fields and strip(lab.get("label_name")):
        name = strip(lab.get("label_name"))
        pre = strip(lab.get("label_pretype"))
        ours = compact((a.street_name or "") + (a.highway["name"] if a.highway else ""))
        accepted = (compact(name), compact(pre + name))
        if not strip(lab.get("label_type")) and a.street_suffix:
            # The source puts the suffix inside the name and leaves the type empty: `OAK ST` is our `OAK` + `ST`.
            ours_full = compact(a.street_name or "") + compact(a.street_suffix)
            ours_long = compact(a.street_name or "") + compact(canon.long_word(a.street_suffix))
            if compact(name) in (ours_full, ours_long) or compact(pre + name) in (ours_full, ours_long):
                accepted += (ours,)
        if ext:  # `MAIN ST EXT`: our name is `MAIN STREET`
            word = compact(canon.long_word(lab.get("label_type")))
            accepted += (compact(name) + word, compact(pre + name) + word)
        same = ours in accepted
        count("name", True, not same, name, (a.street_name or "") + (a.highway["name"] if a.highway else ""))


def norm_state(s):
    return (s or "").strip().upper()


def fetch_chunk(con, args, have_a, have_b, k, n):
    """Rows of chunk `k` of `n`, as (base columns..., labels dict)."""
    base = [c for c in BASE if c != "label_number"]
    if args.labels:
        # Pair by (role, pair_id), unique in both files; chunk by a hash of the pair.
        a_cols = select_list(have_a, "a", base)
        b_cols = ", ".join(f"b.{c}" if c in have_b else f"NULL AS {c}" for c in LABELS)
        b_cols += ", (left(a.zip, 5) is not distinct from left(b.zip, 5)) AS same_zip, a.pair_id AS pair_id"
        has_label = " or ".join(f"{c} is not null" for c in LABELS if c in have_b)
        sql = f"""
        select {a_cols}, {b_cols} from
          (select * from read_parquet(?) where pair_id is not null and hash(pair_id) % {n} = {k}
           qualify count(*) over (partition by role, pair_id) = 1) a
          join
          (select * from read_parquet(?) where pair_id is not null and hash(pair_id) % {n} = {k}
           and ({has_label}) qualify count(*) over (partition by role, pair_id) = 1) b
          on a.role = b.role and a.pair_id = b.pair_id"""
        params = [str(args.records), str(args.labels)]
    else:
        cols = ", ".join(c if c in have_a else f"NULL AS {c}" for c in base + LABELS)
        sql = (f"select {cols} from read_parquet(?, file_row_number = true) "
               f"where file_row_number >= {k * args.chunk_rows} and file_row_number < {(k + 1) * args.chunk_rows}")
        params = [str(args.records)]
    return con.execute(sql, params).fetchall()


def n_chunks(con, args):
    n = con.execute("select count(*) from read_parquet(?)", [str(args.records)]).fetchone()[0]
    return n, max(1, -(-n // args.chunk_rows))


def score(args):
    import duckdb
    from doorplate import parse_fields_many, parse_many

    fields = [f for f in args.fields.split(",") if f]
    bad = [f for f in fields if f not in FIELDS]
    if bad:
        sys.exit(f"unknown field(s) {bad}; choose from {FIELDS}")
    con = duckdb.connect()
    have_a = set(columns(con, args.records))
    have_b = set(columns(con, args.labels)) if args.labels else have_a
    labels_in = have_b if args.labels else have_a
    if not [c for c in LABELS if c in labels_in]:
        sys.exit("no label_* columns to score against")
    n, chunks = n_chunks(con, args)
    canon, res = Canon(), Result()
    res.example_max = args.examples_max if args.examples else 0
    limit_left = args.limit
    nb = len(BASE) - 1
    for k in range(chunks):
        rows = fetch_chunk(con, args, have_a, have_b, k, chunks)
        if limit_left is not None:
            rows = rows[:limit_left]
            limit_left -= len(rows)
        # run.parse_rows takes run.COLS rows; its last slot (label_number) is unused here.
        base = [r[:nb] + (None,) for r in rows]
        parsed = run.parse_rows(base, parse_fields_many, parse_many)
        for r, b, a in zip(rows, base, parsed):
            if args.labels:
                res.pairs_seen[(b[1] or "", b[2] or "")] += 1
                if not r[nb + len(LABELS)] and not args.any_zip:
                    res.dropped[(b[1] or "", b[2] or "")] += 1
                    continue
            lab = dict(zip(LABELS, r[nb:nb + len(LABELS)]))
            if args.labels:
                lab["_pair_id"] = r[nb + len(LABELS) + 1]
            compare(b, lab, a, fields, canon, res,
                    guard_number=bool(args.labels) and not args.any_number)
        if limit_left is not None and limit_left <= 0:
            break
    return res, fields, n


def examples_path(path):
    """`path` resolved, which must be under local-data/ (git-ignored): examples hold row ids."""
    path = Path(path).resolve()
    if (ROOT / "local-data").resolve() not in path.parents:
        sys.exit(f"--examples must be a file under {ROOT / 'local-data'} (it holds record ids, not for the repository)")
    return path


def write_examples(res, path):
    """One tab-separated line per kept example; returns how many. Never printed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("source\trole\tfield\trecord_id\tpair_id\tlabel\tours\n")
        for row in res.examples:
            f.write("\t".join(str(v).replace("\t", " ").replace("\n", " ") for v in row) + "\n")
    return len(res.examples)


def render(res, fields, top, mode):
    out = []
    for key in sorted(res.c):
        src, role = key
        c = res.c[key]
        out += [f"## {src} / {role}{' (paired labels)' if mode == 'pair' else ''}: "
                f"{c['rows']:,} rows scored" + (f", {c['no result']:,} with no result" if c["no result"] else ""), "",
                *([f"{res.pairs_seen[key]:,} pairs joined, {res.dropped[key]:,} dropped for a different ZIP "
                   "(a move between the files, not a disagreement); "
                   f"{res.other_number[key]:,} more have another house number: counted for `number` only", ""]
                  if mode == "pair" else []),
                "| field | labeled | we differ | share |", "|---|---|---|---|"]
        for f in fields:
            n, d = c[f"{f}: labeled"], c[f"{f}: differ"]
            out.append(f"| {f} | {n:,} | {d:,} | {100 * d / max(n, 1):.2f}% |")
        if c["unit: not in the text"]:
            out += ["", f"{c['unit: not in the text']:,} labeled units are nowhere in the text we parsed (the source's, not a "
                    "miss): not counted as differences"]
        for f in fields:
            if f in LEXICON and res.pairs[key + (f,)]:
                out += ["", f"{f}: label -> ours (lexicon values only)", ""]
                out += [f"- {n:,}  {w or '-'} -> {g or '-'}" for (w, g), n in res.pairs[key + (f,)].most_common(top)]
            elif f not in LEXICON and res.shapes[key + (f,)]:
                out += ["", f"{f}: shape of the label -> shape of ours (`a` letters, `9` digits)", ""]
                out += [f"- {n:,}  `{w}` -> `{g}`" for (w, g), n in res.shapes[key + (f,)].most_common(top)]
            if res.states[key + (f,)]:
                out.append(f"- {f}, top states: " + ", ".join(f"{s or '-'} {n:,}" for s, n in
                                                              res.states[key + (f,)].most_common(5)))
        out.append("")
    return "\n".join(out)


def render_by_warning(res, fields):
    """Per warning code: the rows that carry it and, for each field, the labeled rows among them and the share
    where we differ. A row with several warnings counts under each. The first line is every row, the baseline."""
    out = []
    for key in sorted(res.c):
        src, role = key
        c = res.c[key]
        out += [f"## {src} / {role}: by warning ({c['rows']:,} rows scored)", "",
                "| warning | rows | " + " | ".join(f"{f}: differ / labeled" for f in fields) + " |",
                "|---|---|" + "---|" * len(fields)]

        def cells(counter):
            return " | ".join(f"{counter[f'{f}: differ']:,} / {counter[f'{f}: labeled']:,} "
                              f"({100 * counter[f'{f}: differ'] / counter[f'{f}: labeled']:.1f}%)"
                              if counter[f"{f}: labeled"] else "-" for f in fields)

        out.append(f"| (every row) | {c['rows']:,} | {cells(c)} |")
        rows = sorted(((k[2], v) for k, v in res.w.items() if k[:2] == key), key=lambda kv: -kv[1]["rows"])
        out += [f"| `{code}` | {v['rows']:,} | {cells(v)} |" for code, v in rows]
        out.append("")
    return "\n".join(out)


def main(argv=None):
    args = parse_args(argv)
    for p in (args.records, args.labels):
        if p and not p.exists():
            sys.exit(f"{p} not found (build it with tools/ingest/ingest.py)")
    if args.examples:
        args.examples = examples_path(args.examples)
    import duckdb

    try:
        con = duckdb.connect()
        n, chunks = n_chunks(con, args)
    except Exception as e:  # DuckDB messages can quote rows (docs/data-policy.md)
        sys.exit(f"could not read {args.records}: {type(e).__name__}")
    print(f"plan\n  records  {args.records} ({n:,} rows, {chunks} chunk(s) of {args.chunk_rows:,})"
          + (f"\n  labels   {args.labels} (paired by role and pair_id)" if args.labels else "")
          + f"\n  fields   {args.fields}" + (f"\n  limit    {args.limit:,} rows" if args.limit else "")
          + (f"\n  examples {args.examples} (at most {args.examples_max} per label -> ours pair)" if args.examples else ""))
    if not args.confirm:
        print("\nDry run. Nothing was scored. Re-run with --confirm to start.")
        return 0
    try:
        res, fields, _ = score(args)
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"scoring failed: {type(e).__name__}")
    text = render(res, fields, args.top, "pair" if args.labels else "own")
    if args.by_warning:
        text = render_by_warning(res, fields) + "\n" + text
    print()
    print(text)
    if args.examples:
        print(f"{write_examples(res, args.examples):,} examples written to {args.examples} (not shown here)")
    if args.out:
        args.out.write_text(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
