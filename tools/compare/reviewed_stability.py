#!/usr/bin/env python3
"""Do the rows a person has already judged keep the reading they were judged on? (the away run's over-tuning check)

    python tools/compare/reviewed_stability.py [--review-dir local-data/review] [--out FILE.md] [--ids-out FILE]

Reads every `answers*.jsonl` in the review folder (the last answer for each card id), parses each card's input again with the
installed doorplate, and compares the key with the key stored when the card was reviewed (the `kN:` prefix is compared first: a card
from another key format cannot be compared). Groups, by the person's verdict:

- **right**: `doorplate_right`, `both_right`, `rule_right`, `right`. The stored reading was judged right, so a key that changed is a
  candidate regression (or a deliberate change of how the same row reads).
- **wrong**: `usaddress_right`, `both_wrong`. The stored reading was judged wrong; a key that changed is movement, possibly a fix.
- **corrected**: `corrected` (the person typed the right reading), reported separately.

Other verdicts (labeled, junk, unclear, foreign, dual, insufficient) are not used. Read the numbers with care: the cards are not a
random sample of any source (they are rows where the parsers disagree or a shape was flagged), and they are the work list the rules
were written from, so "wrong cards now read differently" measures the fit to the rows that motivated the rules, not their
generalisation; "right cards still read the same" is the part that guards real rows from the damage of a later rule.

Output is counts, never a row (the cards are real addresses); `--ids-out` writes the ids of the right cards whose key changed, one per
line, for a person to look at in `local-data/review`. This library formats and parses; it does not validate that an address exists or
can receive mail.
"""

import argparse
import collections
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

GROUPS = {
    "right": {"doorplate_right", "both_right", "rule_right", "right"},
    "wrong": {"usaddress_right", "both_wrong"},
    "corrected": {"corrected"},
}
PREFIX = re.compile(r"^(k\d+):")


def group_of(verdict):
    for name, verdicts in GROUPS.items():
        if verdict in verdicts:
            return name
    return None


def one_line(inp):
    """The card as one line, as the review page starts the correction box (tools/review/oneline.py)."""
    if inp.get("last_line"):
        parts = [inp.get("line1"), inp.get("line2"), inp["last_line"]]
    else:
        last = " ".join(x for x in (inp.get("state"), inp.get("zip")) if x)
        parts = [inp.get("line1"), inp.get("line2"), inp.get("city"), last]
    return ", ".join(x for x in parts if x)


def load_cards(review_dir):
    """{card id: answer} with the latest answer (by timestamp) for each id across all answer files."""
    best = {}
    for path in sorted(glob.glob(str(Path(review_dir) / "answers*.jsonl"))):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if not (d.get("id") and isinstance(d.get("input"), dict) and isinstance(d.get("parse"), dict)):
                    continue
                if group_of(d.get("verdict")) is None or not d["parse"].get("key"):
                    continue
                if d["id"] not in best or str(d.get("ts", "")) >= str(best[d["id"]].get("ts", "")):
                    best[d["id"]] = d
    return best


def current_reading(doorplate, inp):
    """(the property key, whether the parser flags the row: a warning or unparsed text) of the card's input now; (None, False) on error."""
    try:
        parsed = _parse(doorplate, inp)
        return parsed.key(), bool(parsed.warnings) or bool(parsed.unparsed)
    except Exception:  # noqa: BLE001  (a row the parser rejects counts as not parsed, never as a crash)
        return None, False


def current_key(doorplate, inp):
    """The property key of the card's input now (None when the parser raises)."""
    return current_reading(doorplate, inp)[0]


def _parse(doorplate, inp):
    """The card's input parsed as the review page parses it: fields, or one joined line when the card has a `last_line`."""
    if inp.get("last_line"):
        return doorplate.parse(one_line(inp))
    return doorplate.parse_fields(
        line1=inp.get("line1") or None, line2=inp.get("line2") or None, city=inp.get("city") or None,
        state=inp.get("state") or None, zip=inp.get("zip") or None,
    )  # fmt: skip


def compare(cards, doorplate):
    """Counters per group, per source, per stored version, and the ids of right cards whose key changed."""
    version = doorplate.__version__
    tot = collections.defaultdict(collections.Counter)
    by_source = collections.defaultdict(collections.Counter)
    by_version = collections.defaultdict(collections.Counter)
    changed_right = []
    same_version = collections.Counter()
    flagged = collections.defaultdict(collections.Counter)  # group -> cards, with a warning now
    for cid, d in cards.items():
        g = group_of(d["verdict"])
        stored = d["parse"]["key"]
        now, warned = current_reading(doorplate, d["input"])
        v = d["parse"].get("library_version") or "unknown"
        tot[g]["cards"] += 1
        by_version[v]["cards"] += g == "right"
        if now is None:
            tot[g]["not_parsed"] += 1
            continue
        sp, np_ = PREFIX.match(stored), PREFIX.match(now)
        if not (sp and np_) or sp.group(1) != np_.group(1):
            tot[g]["other_key_format"] += 1
            continue
        flagged[g]["cards"] += 1
        flagged[g]["warned"] += warned
        tot[g]["comparable"] += 1
        same = stored == now
        tot[g]["unchanged" if same else "changed"] += 1
        if g == "right":
            by_source[d.get("source") or "?"]["cards"] += 1
            by_source[d.get("source") or "?"]["changed"] += not same
            by_version[v]["comparable"] += 1
            by_version[v]["changed"] += not same
            if not same:
                changed_right.append(cid)
        if v == version:
            same_version["cards"] += 1
            same_version["changed"] += not same
    return tot, by_source, by_version, changed_right, same_version, flagged


def report(doorplate, cards):
    tot, by_source, by_version, changed_right, same_version, flagged = compare(cards, doorplate)
    out = [
        "## Reviewed rows: do they keep the reading they were judged on?", "",
        f"doorplate {doorplate.__version__}; {len(cards):,} judged cards (the latest answer for each id), re-parsed from their stored input. "
        "A card is comparable when its stored key and the key now are in the same key format. Counts only.", "",
        "| Verdict group | Cards | Comparable | Key unchanged | Key changed | Other key format | Not parsed |", "|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    for g in ("right", "wrong", "corrected"):
        t = tot[g]
        out.append(f"| {g} | {t['cards']:,} | {t['comparable']:,} | {t['unchanged']:,} | {t['changed']:,} | {t['other_key_format']:,} | {t['not_parsed']:,} |")
    r = tot["right"]
    if r["comparable"]:
        out += ["", f"Of the comparable right cards, {r['changed']:,} of {r['comparable']:,} ({100 * r['changed'] / r['comparable']:.1f}%) read differently now.", ""]
    if same_version["cards"]:
        out += [
            f"Of the {same_version['cards']:,} cards stored under this same version string, {same_version['changed']:,} read differently now "
            "(a development version string such as `0.6.0-dev` is not one build: rules land under it, so some change is expected).", "",
        ]  # fmt: skip
    out += ["### Does the parser flag the rows a person judged wrong? (warning or unparsed text now; comparable cards)", "",
            "| Verdict group | Cards | With a warning | Without |", "|---|---|---|---|"]  # fmt: skip
    for g in ("right", "wrong"):
        f = flagged[g]
        out.append(f"| {g} | {f['cards']:,} | {f['warned']:,} | {f['cards'] - f['warned']:,} |")
    out += ["", "A person-judged error with no warning is a silent one; a right card with a warning is a flag that was not needed. The cards are not "
            "a random sample, so these are counts of the cards, not rates for a source.", ""]  # fmt: skip
    out += ["### Right cards by source (comparable)", "", "| Source | Cards | Key changed |", "|---|---|---|"]
    for s, c in sorted(by_source.items(), key=lambda kv: -kv[1]["cards"])[:15]:
        out.append(f"| {s} | {c['cards']:,} | {c['changed']:,} |")
    out += ["", "### Right cards by the version they were judged on", "", "| Version at review | Cards | Comparable | Key changed |", "|---|---|---|---|"]
    for v, c in sorted(by_version.items()):
        if c["cards"]:
            out.append(f"| {v} | {c['cards']:,} | {c['comparable']:,} | {c['changed']:,} |")
    return out, changed_right


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review-dir", default=str(ROOT / "local-data" / "review"))
    ap.add_argument("--out", help="write the Markdown here as well")
    ap.add_argument("--ids-out", help="write the ids of right cards whose key changed here (local-data only)")
    args = ap.parse_args(argv)
    import doorplate

    cards = load_cards(args.review_dir)
    if not cards:
        sys.exit(f"no judged cards in {args.review_dir}")
    out, changed = report(doorplate, cards)
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    if args.ids_out:
        Path(args.ids_out).write_text("".join(f"{i}\n" for i in sorted(changed)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
