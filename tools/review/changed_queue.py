#!/usr/bin/env python3
"""A queue of the rows whose reading changed between two builds, from two key dumps (#568, phase H of #566).

    python tools/review/changed_queue.py BEFORE_DIR AFTER_DIR --name NAME [--label "v0.5.1"] [--n 150] [--seed 1]
                          [--max-source-share 0.4] [--out-dir local-data/review/probe-queues] [--confirm]

`BEFORE_DIR` and `AFTER_DIR` are directories written by `tools/compare/key_diff.py dump-all` (add `--unit` to both to also
compare the unit-level key). A row is *changed* when its property key, its unit-level key (when both dumps have it) or its
warning codes differ. Each changed row falls in one stratum: the source, the role and the kind of change (`key`, `unit` or
`warnings`: the first that applies). The queue is drawn in turns across the strata (a seeded random order inside each), with no
source above `--max-source-share` of the queue, and written as `queue-NAME.jsonl` in the format of the review page: the input
fields from the source's records file, the earlier reading as `alt` (key and warning codes; the dumps do not hold the unparsed
text), and the stratum as the group. The page shows the current reading as usual and the earlier one below it.

Stdout is counts only: the changed rows and the queue by stratum. The queue holds real addresses and stays under `local-data/`.
Without `--confirm` it prints the plan and writes nothing. This library formats and parses; it does not validate that an
address exists or can receive mail.
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import rule_queue  # the card format and the field names are shared with the rule queues

DEFAULT_OUT = ROOT / "local-data" / "review" / "probe-queues"
KINDS = ("key", "unit", "warnings")


def changed_rows(before, after):
    """[(source, role, rn, kind)] for every row that differs, and the `after` dump's records path per source.

    `kind` is the first of key, unit, warnings that differs. Rows missing from either dump are not compared."""
    import duckdb

    before, after = Path(before), Path(after)
    names = sorted(
        p.stem for p in before.glob("*.parquet") if (after / p.name).exists()
    )
    if not names:
        sys.exit("no source in both directories")
    con = duckdb.connect()
    rows, records = [], {}
    for name in names:
        b, a = before / f"{name}.parquet", after / f"{name}.parquet"
        try:
            both_unit = all(
                "key_unit"
                in {
                    r[0]
                    for r in con.execute(f"describe select * from '{p}'").fetchall()
                }
                for p in (b, a)
            )
            unit = (
                "when b.key_unit is distinct from a.key_unit then 'unit'"
                if both_unit
                else ""
            )
            res = con.execute(
                f"select b.rn, b.role, case when b.key is distinct from a.key then 'key' {unit} "
                f"when b.warnings is distinct from a.warnings then 'warnings' end as kind "
                f"from '{b}' b join '{a}' a using (rn, role) "
                f"where b.key is distinct from a.key or b.warnings is distinct from a.warnings"
                f"{' or b.key_unit is distinct from a.key_unit' if both_unit else ''}"
            ).fetchall()
            meta = json.loads((after / f"{name}.json").read_text())
        except Exception as e:  # noqa: BLE001  DuckDB errors can quote rows
            sys.exit(f"{name} failed: {type(e).__name__}")
        records[name] = meta["records"]
        rows += [(name, role, rn, kind) for rn, role, kind in res]
    return rows, records


def draw(rows, n, cap, seed):
    """`n` rows in turns across the strata (source, role, kind), a seeded random order inside each, no source above `cap` of n."""
    rnd = random.Random(seed)
    strata = collections.defaultdict(list)
    for r in rows:
        strata[(r[0], r[1], r[3])].append(r)
    for v in strata.values():
        rnd.shuffle(v)
    names = sorted(strata)
    rnd.shuffle(names)
    limit = max(1, int(n * cap))
    taken, out = collections.Counter(), []
    while len(out) < n:
        progress = False
        for s in names:
            if len(out) >= n:
                break
            if strata[s] and taken[s[0]] < limit:
                out.append(strata[s].pop())
                taken[s[0]] += 1
                progress = True
        if not progress:
            break
    return out


def fetch(picked, records, before):
    """{(source, rn): (fields, key, warnings)}: the input fields from the records file, the earlier reading from the before dump."""
    import duckdb

    con = duckdb.connect()
    by = collections.defaultdict(list)
    for r in picked:
        by[r[0]].append(r[2])
    out = {}
    for name, rns in by.items():
        ids = ",".join(str(i) for i in sorted(set(rns)))
        try:
            cols = {
                r[0]
                for r in con.execute(
                    f"describe select * from '{records[name]}'"
                ).fetchall()
            }
            sel = ", ".join(c if c in cols else f"'' as {c}" for c in rule_queue.FIELDS)
            f = con.execute(
                f"select rn, {sel} from (select row_number() over () - 1 as rn, * from '{records[name]}') where rn in ({ids})"
            ).fetchall()
            k = con.execute(
                f"select rn, role, key, warnings from '{Path(before) / (name + '.parquet')}' where rn in ({ids})"
            ).fetchall()
        except Exception as e:  # noqa: BLE001
            sys.exit(f"{name} failed: {type(e).__name__}")
        fields = {rn: [x or "" for x in rest] for rn, *rest in f}
        for rn, role, key, warns in k:
            out[(name, rn, role)] = (fields.get(rn), key, warns)
    return out


def build(picked, got, name, label, total, per_source):
    cards = []
    for source, role, rn, kind in picked:
        fields, key, warns = got[(source, rn, role)]
        card = rule_queue.card(
            len(cards) + 1,
            name,
            label,
            [],
            source,
            rn,
            fields,
            (key or "", [w for w in (warns or "").split("|") if w], ""),
            total,
            per_source,
        )
        card["role"] = role
        card["id"] = f"changed|{name}|{source}|{role}|{rn}"
        card["cluster"]["shape"] = f"changed since {label}: {kind}"
        cards.append(card)
    return cards


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument(
        "--label",
        default="the earlier build",
        help="what the earlier build is called on the card (a tag)",
    )
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-source-share", type=float, default=0.4)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    local = (ROOT / "local-data").resolve()
    if local not in args.out_dir.resolve().parents and args.out_dir.resolve() != local:
        sys.exit(f"--out-dir must be under {local}: the queue holds real addresses")
    rows, records = changed_rows(args.before, args.after)
    per_source = collections.Counter(r[0] for r in rows)
    per_stratum = collections.Counter((r[0], r[1], r[3]) for r in rows)
    print(f"{len(rows)} changed rows; by source {dict(per_source)}")
    for (s, role, kind), c in sorted(per_stratum.items()):
        print(f"  stratum {s}/{role}/{kind}: {c}")
    picked = draw(rows, args.n, args.max_source_share, args.seed)
    print(
        f"queue of {len(picked)} cards; by stratum {dict(collections.Counter((r[0], r[1], r[3]) for r in picked))}"
    )
    if not args.confirm:
        print("Dry run. Nothing was written. Re-run with --confirm.")
        return 0
    got = fetch(picked, records, args.before)
    cards = build(picked, got, args.name, args.label, len(rows), dict(per_source))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"queue-{args.name}.jsonl"
    out.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cards),
        encoding="utf-8",
    )
    order = args.out_dir / "order.txt"
    names = order.read_text().split() if order.exists() else []
    if args.name not in names:
        order.write_text("\n".join(names + [args.name]) + "\n")
    print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
