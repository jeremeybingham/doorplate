"""The full-text export: what a maintainer's own session may read, for sources the owner has cleared (#122).

    python tools/review/export.py --full [ANSWERS.jsonl] [--out local-data/review/answers-full.md]

The shape-only export (export.py) is what may be shared. This is the other tier, for finding rules
in rows where a shape is not enough: the original lines, the parse, the reviewer's corrected string and
note verbatim, and a one-line description of the edit. It is written only for sources listed in
`local-data/review/full-ok.txt`, one per line:

    irs-eo-bmf  mask=line2        # the care-of name field is reduced to its shape
    fmcsa-census                  # nothing masked

A source that is not listed is skipped, and with no listed source nothing is written. `mask=` names
input fields (`line1`, `line2`, `city`, `state`, `zip`, `last_line`) whose words are replaced by their
shape everywhere in that row's entry: the original lines, the parse (an `attention` component built
from a masked field), the correction and the note. Words that also appear in an unmasked field, and
address vocabulary (`C/O`, `ATTN`, `PO BOX`, `APT`, ...), are kept, so a street line and a care-of
marker stay readable while a name does not.

The file stays in `local-data/review/` (git-ignored). Reading it in a session sends its text to the
model provider, which is why it is an exception and why each source is cleared by hand
(docs/data-policy.md). Findings written to issues, pull requests and docs stay counts, shapes and
invented examples. This library formats and parses; it does not validate that an address exists or can
receive mail.
"""
import difflib
import re
from pathlib import Path

from shape import shape

TOKEN = re.compile(r"[A-Za-z0-9]+|[^\sA-Za-z0-9]")
WORD = re.compile(r"[A-Za-z0-9]+")
FIELDS = ("line1", "line2", "city", "state", "zip", "last_line")
# Words that are address structure, not names: never masked, so a care-of marker or a unit stays readable.
STRUCTURE = {w for w in """
C O CARE OF IN ATTN ATTENTION PO P BOX APT UNIT STE SUITE FL FLOOR BLDG BUILDING RM ROOM DEPT
N S E W NE NW SE SW NORTH SOUTH EAST WEST ST AVE RD DR LN CT BLVD HWY PKWY CIR PL TER WAY
""".split()}


def load_allowlist(path):
    """{source: set of masked field names} from the allowlist file; {} when there is none."""
    allowed = {}
    path = Path(path)
    if not path.exists():
        return allowed
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        source, *opts = line.split()
        mask = set()
        for o in opts:
            if not o.startswith("mask="):
                raise ValueError(f"{path}: unknown option {o!r} (expected mask=FIELD,FIELD)")
            for f in o[5:].split(","):
                if f not in FIELDS:
                    raise ValueError(f"{path}: {f!r} is not a field ({', '.join(FIELDS)})")
                mask.add(f)
        allowed[source] = mask
    return allowed


def masked_words(inp, mask):
    """The upper-cased words of the masked fields that appear in no unmasked field and are not structure."""
    keep = {w.upper() for f in FIELDS if f not in mask for w in WORD.findall(inp.get(f) or "")}
    hide = {w.upper() for f in mask for w in WORD.findall(inp.get(f) or "")}
    return {w for w in hide if w not in keep and w not in STRUCTURE}


def mask_text(text, words):
    """Replace each hidden word in `text` by its shape; everything else is untouched."""
    if not words or not isinstance(text, str):
        return text
    return WORD.sub(lambda m: shape(m.group(0)) if m.group(0).upper() in words else m.group(0), text)


def mask_value(v, words):
    """Mask strings inside a JSON-like value."""
    if isinstance(v, str):
        return mask_text(v, words)
    if isinstance(v, dict):
        return {k: mask_value(x, words) for k, x in v.items()}
    if isinstance(v, list):
        return [mask_value(x, words) for x in v]
    return v


def one_line(inp):
    """The row as one line, as the review page starts the correction box."""
    if inp.get("last_line"):
        return ", ".join(x for x in (inp.get("line1"), inp.get("line2"), inp["last_line"]) if x)
    last = " ".join(x for x in (inp.get("state"), inp.get("zip")) if x)
    return ", ".join(x for x in (inp.get("line1"), inp.get("line2"), inp.get("city"), last) if x)


def edit_summary(original, corrected):
    """Short phrases for what the reviewer changed, word by word: 'deleted leading "ACME LLC"'."""
    a, b = TOKEN.findall(original), TOKEN.findall(corrected)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        old, new = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        words_old = [t for t in a[i1:i2] if WORD.fullmatch(t)]
        words_new = [t for t in b[j1:j2] if WORD.fullmatch(t)]
        if not words_old and not words_new:
            out.append("punctuation changed")
            continue
        where = "leading " if i1 == 0 else "trailing " if i2 == len(a) else ""
        if op == "delete":
            out.append(f'deleted {where}"{old}"')
        elif op == "insert":
            out.append(f'inserted "{new}"')
        else:
            out.append(f'replaced {where}"{old}" with "{new}"')
    return out or ["no change"]


def parse_line(p):
    if not p:
        return "(none)"
    if p.get("error"):
        return f"error: {p['error']}"
    comps = ", ".join(f"{k}={v}" for k, v in (p.get("components") or {}).items())
    bits = [comps or "no components", f"warnings: {','.join(p.get('warnings') or []) or '-'}"]
    if p.get("unparsed"):
        bits.append(f"not placed: {p['unparsed']}")
    bits.append(f"key {p.get('key')}")
    return "; ".join(bits)


def entry(n, a, mask):
    """One answer as a markdown block, with the masked fields' words hidden."""
    inp = a.get("input") or {}
    words = masked_words(inp, mask)
    mk = lambda v: mask_value(v, words)  # noqa: E731
    cl = a.get("cluster") or {}
    head = f"## {n}. {a['verdict']}"
    if a["verdict"] == "right":
        head += f" (warning {a.get('warning') or 'not recorded'})"
    lines = [head, f"- group: {cl.get('size')} row(s), shape `{cl.get('shape')}`, warnings {cl.get('warnings') or '-'}  ·  {a.get('source')} / {a.get('role')}  ·  {(a.get('ts') or '')[:10]}"]
    shown = [f"{k}={mk(inp[k])!r}" for k in FIELDS if inp.get(k)]
    lines.append("- input: " + "; ".join(shown))
    lines.append(f"- parse: {parse_line(mk(a.get('parse')))}")
    if a["verdict"] == "corrected":
        original = one_line(inp)
        lines.append(f"- corrected: {mk(a.get('corrected'))!r}")
        lines.append(f"- corrected parse: {parse_line(mk(a.get('corrected_parse')))}")
        c, p = a.get("corrected_parse") or {}, a.get("parse") or {}
        clean = bool(c) and not c.get("warnings") and not c.get("unparsed") and "error" not in c
        lines.append(f"- clean: {'yes' if clean else 'no'}; same key as the original parse: {'yes' if p.get('key') and p.get('key') == c.get('key') else 'no'}")
        lines.append("- edit: " + "; ".join(mask_text(s, words) for s in edit_summary(original, a.get("corrected") or "")))
    if a.get("note"):
        lines.append(f"- note: {mk(a['note'])}")
    return "\n".join(lines)


def build(answers, allowed):
    """(markdown text, {source: count written}, set of sources skipped)."""
    blocks, counts, skipped = [], {}, set()
    for a in answers:
        src = a.get("source")
        if src not in allowed:
            skipped.add(src)
            continue
        counts[src] = counts.get(src, 0) + 1
        blocks.append(entry(len(blocks) + 1, a, allowed[src]))
    header = ("# Review answers, full text\n\nPrivate: stays in `local-data/review/`. Masked fields (full-ok.txt) show shapes for "
              "their words. Quote nothing from this file in an issue, pull request or doc; write counts, shapes and "
              "invented examples.\n")
    return header + "\n" + "\n\n".join(blocks) + ("\n" if blocks else ""), counts, skipped
