"""The full-text export: what a maintainer's own session may read, for sources the owner has cleared (#122).

    python tools/review/export.py --full [ANSWERS.jsonl] [--out local-data/review/answers-full.md]

The shape-only export (export.py) is what may be shared. This is the other tier, for finding rules
in rows where a shape is not enough: the original lines, the parse, the reviewer's corrected string and
note verbatim, and a one-line description of the edit. It is written only for sources listed in
`local-data/review/full-ok.txt`, one per line:

    irs-eo-bmf  mask=line2        # the care-of name field is reduced to its shape
    fmcsa-census                  # nothing masked
    nc-voter-current  anon keep=CPO,CPU   # every word is replaced by the anonymizer's, except these

`anon` goes further, for a source whose fields hold addresses of private people and names in places
we cannot predict (the NC voter file's mailing lines): every word the anonymizer would replace
(`doorplate anonymize`, docs/anonymizing.md) is replaced by its invented word, house numbers and the end of
a ZIP included, in the lines, the parse, the correction and the note, and `keep=WORD,WORD` leaves named words
alone (the campus-box words `CPO`, `CPU` the review is about). The parse was made on the real text, so the rules
are seen as they behaved; only the display changes. The city and state stay, as the anonymizer keeps them.

A source that is not listed is skipped, and with no listed source nothing is written. `mask=` names
input fields (`line1`, `line2`, `city`, `state`, `zip`, `last_line`) whose words are replaced by their
shape everywhere in that row's entry: the original lines, the parse (an `attention` component built
from a masked field), the correction and the note. Words that also appear in an unmasked field, and
address vocabulary (`C/O`, `ATTN`, `PO BOX`, `APT`, ...), are kept, so a street line and a care-of
marker stay readable while a name does not.

The file stays in `local-data/review/` (git-ignored). Reading it in a session sends its text to the
model provider, so the transcript is not shared unedited (docs/data-policy.md, principle 4: every
ingested source is listed since 2026-10-29). Nothing from a row reaches the repository. Findings written to issues, pull requests and docs stay counts, shapes and
invented examples. This library formats and parses; it does not validate that an address exists or can
receive mail.
"""
import difflib
import re
from pathlib import Path

from oneline import one_line
from shape import shape

TOKEN = re.compile(r"[A-Za-z0-9]+|[^\sA-Za-z0-9]")
WORD = re.compile(r"[A-Za-z0-9]+")
FIELDS = ("line1", "line2", "city", "state", "zip", "last_line")
# Words that are address structure, not names: never masked, so a care-of marker or a unit stays readable.
STRUCTURE = {w for w in """
C O CARE OF IN ATTN ATTENTION PO P BOX APT UNIT STE SUITE FL FLOOR BLDG BUILDING RM ROOM DEPT
N S E W NE NW SE SW NORTH SOUTH EAST WEST ST AVE RD DR LN CT BLVD HWY PKWY CIR PL TER WAY
""".split()}


class Rule(set):
    """The masked field names of one source (a set), plus `anon` (replace every word) and `keep` (words `anon` leaves alone)."""

    anon = False
    keep = frozenset()


def load_allowlist(path):
    """{source: Rule} from the allowlist file; {} when there is none. A Rule is the set of masked field names."""
    allowed = {}
    path = Path(path)
    if not path.exists():
        return allowed
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        source, *opts = line.split()
        mask = Rule()
        for o in opts:
            if o == "anon":
                mask.anon = True
            elif o.startswith("keep="):
                mask.keep = frozenset(w.upper() for w in o[5:].split(",") if w)
            elif o.startswith("mask="):
                for f in o[5:].split(","):
                    if f not in FIELDS:
                        raise ValueError(f"{path}: {f!r} is not a field ({', '.join(FIELDS)})")
                    mask.add(f)
            else:
                raise ValueError(f"{path}: unknown option {o!r} (expected mask=FIELD,FIELD, anon or keep=WORD,WORD)")
        if mask.keep and not mask.anon:
            raise ValueError(f"{path}: keep= goes with anon")
        allowed[source] = mask
    return allowed


def masked_words(inp, mask):
    """The upper-cased words of the masked fields that appear in no unmasked field and are not structure."""
    keep = {w.upper() for f in FIELDS if f not in mask for w in WORD.findall(inp.get(f) or "")}
    hide = {w.upper() for f in mask for w in WORD.findall(inp.get(f) or "")}
    return {w for w in hide if w not in keep and w not in STRUCTURE}


def mask_text(text, words):
    """Replace each hidden word in `text` by its shape, or by its entry when `words` is a dict (anon mode)."""
    if not words or not isinstance(text, str):
        return text

    def sub(m):
        w = m.group(0)
        if isinstance(words, dict):
            new = words.get(w.upper())
            return w if new is None else _case_like(new, w)
        return shape(w) if w.upper() in words else w

    return WORD.sub(sub, text)


def _case_like(new, old):
    """`new` written in the case style of `old` (upper, title or lower)."""
    return new.upper() if old.isupper() else new.capitalize() if old[:1].isupper() else new.lower()


def anon_words(inp, anonymizer, keep=()):
    """{UPPER word: replacement} for the words of one row, from the doorplate anonymizer (docs/anonymizing.md).

    The row is anonymized as the one line the harness parses (`one_line`), so the city and state stay and the
    street, unit and numbers change; the words are paired by position. If the word count changes (rare) every
    word is reduced to its shape instead. Address vocabulary (STRUCTURE) and the `keep` words stay as written;
    a word the anonymizer replaces anywhere in the row is replaced everywhere in it.
    """
    value = one_line(inp)
    old = WORD.findall(value)
    new = WORD.findall(anonymizer.anonymize(value).text)
    pairs = zip(old, new) if len(old) == len(new) else ((w, shape(w)) for w in old)
    out = {}
    for o, n in pairs:
        key = o.upper()
        if key in STRUCTURE or key in keep or (key in out and out[key].upper() != key):
            continue
        if n.upper() != key:
            out[key] = n
    return out


def mask_value(v, words):
    """Mask strings inside a JSON-like value."""
    if isinstance(v, str):
        return mask_text(v, words)
    if isinstance(v, dict):
        return {k: mask_value(x, words) for k, x in v.items()}
    if isinstance(v, list):
        return [mask_value(x, words) for x in v]
    return v


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


def entry(n, a, mask, anonymizer=None):
    """One answer as a markdown block, with the masked fields' words hidden (or, with an anonymizer, every word replaced)."""
    inp = a.get("input") or {}
    words = masked_words(inp, mask)
    if getattr(mask, "anon", False):
        if anonymizer is None:
            raise ValueError("anon needs the doorplate Python package (pip install doorplate, or maturin develop)")
        words = {w: shape(w) for w in words} | anon_words(inp, anonymizer, mask.keep)
    mk = lambda v: mask_value(v, words)  # noqa: E731
    cl = a.get("cluster") or {}
    head = f"## {n}. {a['verdict']}"
    if a["verdict"] == "right":
        head += f" (warning {a.get('warning') or 'not recorded'})"
    lines = [head, f"- group: {cl.get('size')} row(s), shape `{cl.get('shape')}`, warnings {cl.get('warnings') or '-'}  ·  {a.get('source')} / {a.get('role')}  ·  {(a.get('ts') or '')[:10]}"]
    shown = [f"{k}={mk(inp[k])!r}" for k in FIELDS if inp.get(k)]
    lines.append("- input: " + "; ".join(shown))
    lines.append(f"- parse: {parse_line(mk(a.get('parse')))}")
    if a.get("labels"):
        text = a.get("labeled_text") or ""
        lines.append("- labeled: " + "; ".join(
            f"{l['component']}={mask_text(text[l['start']:l['end']], words)!r}" for l in a["labels"]
            if isinstance(l.get("start"), int) and isinstance(l.get("end"), int)))
    if a.get("compare"):
        c = a["compare"]
        lines.append(f"- comparison ({c.get('class')}): differs {c.get('differs')}")
        lines.append("- usaddress read: " + " ".join(f"{mk(t)}/{l}" for t, l in c.get("usaddress") or []))
    if a["verdict"] in ("corrected", "both_wrong") or (a["verdict"] == "usaddress_right" and a.get("corrected")):
        original = one_line(inp)
        lines.append(f"- corrected: {mk(a.get('corrected'))!r}")
        lines.append(f"- corrected parse: {parse_line(mk(a.get('corrected_parse')))}")
        c, p = a.get("corrected_parse") or {}, a.get("parse") or {}
        clean = bool(c) and not c.get("warnings") and not c.get("unparsed") and "error" not in c
        lines.append(f"- clean: {'yes' if clean else 'no'}; same key as the original parse: {'yes' if p.get('key') and p.get('key') == c.get('key') else 'no'}")
        lines.append("- edit: " + "; ".join(mask_text(s, words) for s in edit_summary(original, a.get("corrected") or "")))
    if a.get("draft"):  # an attempted fix under a verdict that is not a correction
        d = a.get("draft_parse") or {}
        lines.append(f"- draft (an attempt, not saved as a correction): {mk(a['draft'])!r}")
        lines.append(f"- draft parse: {parse_line(mk(d))}")
    if a.get("note"):
        lines.append(f"- note: {mk(a['note'])}")
    return "\n".join(lines)


def build(answers, allowed):
    """(markdown text, {source: count written}, set of sources skipped)."""
    blocks, counts, skipped = [], {}, set()
    anonymizer = None
    if any(getattr(m, "anon", False) for m in allowed.values()):
        import doorplate  # a random seed per export: nobody can recompute the replacements from a guess

        anonymizer = doorplate.Anonymizer()
    for a in answers:
        src = a.get("source")
        if src not in allowed:
            skipped.add(src)
            continue
        counts[src] = counts.get(src, 0) + 1
        blocks.append(entry(len(blocks) + 1, a, allowed[src], anonymizer))
    header = ("# Review answers, full text\n\nPrivate: stays in `local-data/review/`. Masked fields (full-ok.txt) show shapes for "
              "their words; `anon` sources show invented words, numbers and ZIP endings instead. Quote nothing from this file in an issue, pull request or doc; write counts, shapes and "
              "invented examples.\n")
    return header + "\n" + "\n\n".join(blocks) + ("\n" if blocks else ""), counts, skipped
