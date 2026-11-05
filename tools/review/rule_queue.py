#!/usr/bin/env python3
"""A queue of the rows one rule decides: doorplate as it is against doorplate with the rule switched off (#524).

    python tools/review/rule_queue.py SAMPLE.tsv --name NAME --sites rules.rs:1427,rules.rs:1431 --label "attention lines"
                          [--n 50] [--seed 1] [--max-source-share 0.4] [--out-dir local-data/review/probe-queues] [--confirm]

`SAMPLE.tsv` has one row per line: source, line 1, line 2, city, state, ZIP, tab-separated (a sample of the
key-comparison sources: `local-data/rule-stats/disable-sample-src.tsv`). The sites are tagger call sites in the
`file:line` form of `tools/rules/rule_stats.py`; `tools/rules/disable_check.py` says how many rows each one changes. The
tool runs the `rule_disable` example twice over the sample (build it first, as `disable_check.py` says): once with
nothing disabled and once with `DOORPLATE_DISABLE` naming the sites. The rows whose key, warnings or unparsed text differ
are the rows the rule decides. It draws `--n` of them at random (seeded), in turns across the sources with no source above
`--max-source-share`, and writes `queue-NAME.jsonl` in the format of the review page: the fields, the group (`cluster.size`
is how many rows of the sample the rule changed) and `alt`, the reading without the rule (key, warning codes, unparsed text).

The page shows doorplate's reading as usual and, below it, the reading without the rule; the reviewer says which is right
(`rule_right`, `rule_off_right`, `both_right`, `both_wrong`; the other verdicts as always). The share of the changed rows
where `rule_off_right` wins, weighted back by source, is the rows a wrong decision would cost: score with
`python tools/review/rule_queue.py --name NAME --score`. The queue holds real addresses and stays in `local-data/`; stdout is counts only.
This library formats and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import collections
import json
import os
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXE = ROOT / "target" / "release" / "examples" / "rule_disable"
DEFAULT_OUT = ROOT / "local-data" / "review" / "probe-queues"
FIELDS = ("line1", "line2", "city", "state", "zip")


def read_sample(path):
    """[(source, [line1, line2, city, state, zip])] from the six-column sample file."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = line.split("\t")
        c += [""] * (6 - len(c))
        out.append((c[0], c[1:6]))
    return out


def run_exe(exe, sample_fields, sites=""):
    """The (key, warnings, unparsed) of every row, with `sites` switched off (`sites` empty: nothing is)."""
    tmp = ROOT / "local-data" / "rule-stats" / ".rule_queue_input.tsv"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text("".join("\t".join(f) + "\n" for f in sample_fields), encoding="utf-8")
    env = dict(os.environ)
    env.pop("DOORPLATE_DISABLE", None)
    if sites:
        env["DOORPLATE_DISABLE"] = sites
    try:
        out = subprocess.run([str(exe), str(tmp)], capture_output=True, text=True, env=env, check=True).stdout.splitlines()
    finally:
        tmp.unlink(missing_ok=True)
    return parse_output(out[1:])


def parse_output(lines):
    rows = []
    for line in lines:
        c = line.split("\t")
        if c == ["error"] or len(c) < 1:
            rows.append(("error", [], ""))
            continue
        c += [""] * (3 - len(c))
        rows.append((c[0], [w for w in c[1].split("|") if w], c[2]))
    return rows


def changed(base, off):
    """Indices where the key, the warnings or the unparsed text differ."""
    return [i for i, (a, b) in enumerate(zip(base, off, strict=True)) if a != b]


def snake(w):
    """`MissingStreetNumber` -> `missing_street_number` (the example prints the Debug names)."""
    out = ""
    for i, ch in enumerate(w):
        if ch.isupper() and i:
            out += "_"
        out += ch.lower()
    return out


def draw(idx, sources, n, cap, seed):
    """`n` of the changed row indices, in turns across the sources (a seeded random order inside each), no source above `cap` of n."""
    rnd = random.Random(seed)
    by = collections.defaultdict(list)
    for i in idx:
        by[sources[i]].append(i)
    for v in by.values():
        rnd.shuffle(v)
    limit = max(1, int(n * cap))
    taken, out = collections.Counter(), []
    names = sorted(by)
    rnd.shuffle(names)
    while len(out) < n:
        progress = False
        for s in names:
            if len(out) >= n:
                break
            if by[s] and taken[s] < limit:
                out.append(by[s].pop())
                taken[s] += 1
                progress = True
        if not progress:
            break
    return out


def card(seq, name, label, sites, source, i, fields, alt, size, by_source=None):
    e = {"seq": seq, "id": f"rule|{name}|{source}|{i}", "source": source, "role": "rule", "record_id": str(i)}
    for k, v in zip(FIELDS, fields, strict=True):
        if v:
            e[k] = v
    e["cluster"] = {"shape": f"rule: {label}", "warnings": "", "size": size}
    key, warns, unparsed = alt
    e["alt"] = {"label": label, "sites": sites, "key": key, "warnings": [snake(w) for w in warns], "unparsed": unparsed,
                "changed_by_source": by_source or {}}
    return e


def build(sample, base, off, name, label, sites, n, seed, cap):
    sources = [s for s, _ in sample]
    ch = changed(base, off)
    per_source = collections.Counter(sources[i] for i in ch)
    pick = draw(ch, sources, n, cap, seed)
    seen, cards = set(), []
    for i in pick:
        s, f = sample[i]
        k = " ".join(" ".join(f).lower().split())
        if k in seen:
            continue
        seen.add(k)
        cards.append(card(len(cards) + 1, name, label, sites, s, i, f, off[i], len(ch), dict(per_source)))
    return cards, len(ch), per_source


def score(answers, queue):
    """(verdict counts, share of the changed sample rows where the reading without the rule is right, weighted by source).
    `answers` are the standing answers of the queue's cards; `queue` the cards (each carries `alt.changed_by_source`)."""
    q = {e["id"]: e for e in queue}
    ans = [a for a in answers if a["id"] in q]
    counts = collections.Counter(a["verdict"] for a in ans)
    pop = next((e["alt"]["changed_by_source"] for e in queue if e.get("alt")), {})
    by = collections.defaultdict(lambda: [0, 0])
    for a in ans:
        by[a["source"]][1] += 1
        by[a["source"]][0] += a["verdict"] == "rule_off_right"
    total = sum(pop.values())
    wrong = sum(pop.get(s, 0) * w / n for s, (w, n) in by.items() if n)
    return counts, (wrong / total if total else 0.0), total


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sample", type=Path, nargs="?")
    ap.add_argument("--name", required=True)
    ap.add_argument("--sites", help="tagger call sites, comma-separated (file:line)")
    ap.add_argument("--label", help="what the rule does, shown on the card")
    ap.add_argument("--score", action="store_true", help="score the queue NAME from its answers (counts only)")
    ap.add_argument("--answers", type=Path, help="the answers file of the queue (default: answers-probe-NAME.jsonl in local-data/review)")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-source-share", type=float, default=0.4)
    ap.add_argument("--exe", type=Path, default=EXE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    if args.score:
        sys.path.insert(0, str(HERE))
        from server import load_answers, read_jsonl

        ans = args.answers or ROOT / "local-data" / "review" / f"answers-probe-{args.name}.jsonl"
        counts, share, total = score(list(load_answers(ans).values()), read_jsonl(args.out_dir / f"queue-{args.name}.jsonl"))
        print(f"{args.name}: verdicts {dict(counts)}; the reading without the rule is right on {share:.1%} of the {total} changed sample rows")
        return 0
    if not (args.sample and args.sites and args.label):
        sys.exit("a build needs SAMPLE, --sites and --label")
    if (ROOT / "local-data").resolve() not in args.out_dir.resolve().parents and args.out_dir.resolve() != (ROOT / "local-data").resolve():
        sys.exit(f"--out-dir must be under {ROOT / 'local-data'}: the queue holds real addresses")
    if not args.exe.exists():
        sys.exit("build the example first: cargo build --release -p doorplate --features rule-stats,corpus --example rule_disable")
    sample = read_sample(args.sample)
    fields = [f for _, f in sample]
    base = run_exe(args.exe, fields)
    off = run_exe(args.exe, fields, args.sites)
    cards, total, per_source = build(sample, base, off, args.name, args.label, args.sites.split(","), args.n, args.seed, args.max_source_share)
    print(f"{args.name}: {total} of {len(sample)} sample rows change without {args.sites}; by source {dict(per_source)}")
    print(f"queue of {len(cards)} cards, sources {dict(collections.Counter(c['source'] for c in cards))}")
    if not args.confirm:
        print("Dry run. Nothing was written. Re-run with --confirm.")
        return 0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"queue-{args.name}.jsonl"
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cards), encoding="utf-8")
    order = args.out_dir / "order.txt"
    names = order.read_text().split() if order.exists() else []
    if args.name not in names:
        order.write_text("\n".join(names + [args.name]) + "\n")
    print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
