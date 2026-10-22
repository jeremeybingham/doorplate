#!/usr/bin/env python3
"""The shape-only export: what may leave `local-data/` from a review (#122).

    python tools/review/export.py [ANSWERS.jsonl] [--out local-data/review/shapes.jsonl] [--with-source]

Reads the answers file and writes one line per standing answer (an undone answer is dropped),
with every address and every note reduced to its shape: letters become `a`, digits `9`, runs
collapse (`% JOHN SMITH` is `% a a`). What stays: the verdict, the warning codes (a fixed
vocabulary), the component names with the shapes of their values, the shape of the key, whether
the corrected string parses cleanly and keys the same, the size of the shape group, the
doorplate version and the day. What goes: every value, the record id, the source name (unless
`--with-source`: a private source may not be named, docs/data-policy.md) and the time of day.

That is enough to see a rule: `% a a` -> `a a` says a percent sign marks a care-of line, without
saying whose. It does not train anything; a rule from it still needs a source, a corpus case and
a harness run (tools/harness/README.md). It is not anonymized text, so it does not replace #105
for sharing a real-looking row. This library formats and parses; it does not validate that an
address exists or can receive mail.
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import json  # noqa: E402

from server import DEFAULT_ANSWERS, load_answers, read_jsonl  # noqa: E402
from shape import clip, shape  # noqa: E402

DEFAULT_OUT = DEFAULT_ANSWERS.with_name("shapes.jsonl")
CODE = re.compile(r"^[a-z][a-z0-9_]*$")  # a warning code or a component name


def codes(values):
    """Warning codes: the fixed vocabulary only, so free text can never ride along."""
    return [c for c in (values or []) if isinstance(c, str) and CODE.match(c)]


def key_shape(key):
    """`k2:S|123|N|MAIN|ST||FL|33101` -> `a9:a|9|a|a|a||a|9`: the key's layout without its values."""
    return shape(key) if isinstance(key, str) else None


def component_shapes(components):
    return {k: shape(str(v)) for k, v in (components or {}).items() if CODE.match(k)}


def input_shape(inp):
    parts = [inp.get(k) for k in ("line1", "line2", "city", "state", "zip", "last_line")]
    return clip(" | ".join(shape(p) for p in parts if p), 120)


def safe(a, with_source=False):
    """One answer, reduced to what may be shared."""
    p, c = a.get("parse") or {}, a.get("corrected_parse") or {}
    out = {"day": (a.get("ts") or "")[:10], "role": a.get("role") if CODE.match(a.get("role") or "") else None,
           "verdict": a["verdict"], "input": input_shape(a.get("input") or {})}
    if with_source:
        out["source"] = a.get("source")
    cl = a.get("cluster") or {}
    out["group"] = {"shape": clip(cl.get("shape") or ""), "warnings": [w for w in (cl.get("warnings") or "").split(",") if CODE.match(w)],
                    "size": cl.get("size")}
    out["warnings"] = codes(p.get("warnings"))
    out["components"] = component_shapes(p.get("components"))
    out["unparsed"] = shape(p["unparsed"]) if p.get("unparsed") else None
    out["key"] = key_shape(p.get("key"))
    if a["verdict"] == "right":
        out["warning"] = a.get("warning") if a.get("warning") in ("fair", "noise") else None
    if a["verdict"] == "corrected":
        out["corrected"] = clip(shape(a.get("corrected") or ""), 120)
        out["corrected_warnings"] = codes(c.get("warnings"))
        out["corrected_components"] = component_shapes(c.get("components"))
        out["corrected_clean"] = bool(c) and not c.get("warnings") and not c.get("unparsed") and "error" not in c
        out["same_key"] = bool(p.get("key")) and p.get("key") == c.get("key")
    if a.get("note"):
        out["note"] = clip(shape(a["note"]), 120)
    out["library_version"] = p.get("library_version") or c.get("library_version")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("answers", nargs="?", type=Path, default=DEFAULT_ANSWERS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--with-source", action="store_true", help="keep the source name (a private source may not be named)")
    args = ap.parse_args(argv)
    if not args.answers.exists():
        sys.exit(f"no answers at {args.answers}")
    answers = list(load_answers(args.answers).values())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for a in answers:
            f.write(json.dumps(safe(a, args.with_source), ensure_ascii=False) + "\n")
    by = {}
    for a in answers:
        by[a["verdict"]] = by.get(a["verdict"], 0) + 1
    print(f"wrote {len(answers)} shape-only answer(s) to {args.out}: {by}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
