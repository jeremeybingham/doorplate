"""doorplate and usaddress on the geocode benchmark, scored the way its paper (Yin, Li and Goldberg, arXiv:2310.14360, Table 4)
reports: F1 per label, the overall F1 and the weighted Parsing Score (weights from Texas A&M's geocoder).

    python benchmarks/geocode_paper_compare.py [test] [dev] [train]

Needs the extension, `usaddress` and the splits in `local-data/geocode-benchmark/` (see `docs/running-benchmarks.md`).
Entity level (an exact span with its B/I tags) and token level are both printed; the paper does not say which it used.
A leading road word such as `COUNTY ROAD` counts as street, as the benchmark labels it. Prints scores only.
"""
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "compare"))
import compare_usaddress as C
import doorplate
import usaddress

SPLITS = ROOT / "local-data" / "geocode-benchmark"
LAB = ["HOUSENUM", "PREDIRECTIONAL", "STREET", "ROADTYPE", "POSTDIRECTIONAL", "CITY", "STATE", "POSTAL"]
W = dict(zip(LAB, [20, 7, 45, 10, 4, 17, 1, 45]))
UA2B = {"AddressNumber": "HOUSENUM", "StreetNamePreDirectional": "PREDIRECTIONAL", "StreetName": "STREET", "StreetNamePreType": "STREET", "StreetNamePreModifier": "STREET", "StreetNamePostType": "ROADTYPE",
        "StreetNamePostDirectional": "POSTDIRECTIONAL", "PlaceName": "CITY", "StateName": "STATE", "ZipCode": "POSTAL"}

def read(path):
    cur = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("-END-"):
                if cur:
                    yield cur
                cur = []
                continue
            tok, tag = line.rsplit(" ", 1)
            cur.append((tok, tag))
    if cur:
        yield cur


def entities(tags):
    """tags: list of 'B-X'/'I-X'/'O' -> set of (label, start, end)."""
    out, cur = set(), None
    for i, t in enumerate(tags):
        if t == "O" or t is None:
            if cur: out.add(cur); cur = None
            continue
        bi, lab = t.split("-", 1)
        if bi == "B" or cur is None or cur[0] != lab:
            if cur: out.add(cur)
            cur = (lab, i, i + 1)
        else:
            cur = (lab, cur[1], i + 1)
    if cur: out.add(cur)
    return out

def predict_tags(lib, toks):
    s = " ".join(toks)
    try:
        pred = list(doorplate.parse_tokens(s)) if lib == "dp" else list(usaddress.parse(s))
    except Exception:  # noqa: BLE001  (an input a library rejects scores as wrong, not as a crash)
        pred = []
    spans = [(a[0], a[1], lab) for a, (_, lab) in zip(C.byte_spans(s, [t for t, _ in pred]), pred) if a]
    gold_sp = C.byte_spans(s, toks)
    labs = []
    for sp in gold_sp:
        l = C.norm(C.overlap_label(sp, spans)) if sp else None
        labs.append(UA2B.get(l))
    tags, prev = [], None
    for l in labs:
        if l is None: tags.append("O"); prev = None
        else: tags.append(("I-" if l == prev else "B-") + l); prev = l
    return tags

def run(split, libs=("dp", "ua"), limit=None):
    res = {lib: {"ent": collections.defaultdict(lambda: [0, 0, 0]), "tok": collections.defaultdict(lambda: [0, 0, 0]), "addr": 0, "n": 0} for lib in libs}
    for k, rec in enumerate(read(SPLITS / f"{split}.txt")):
        if limit and k >= limit: break
        toks = [t for t, _ in rec]; gold = [g if g != "O" else "O" for _, g in rec]
        ge = entities(gold)
        for lib in libs:
            ptags = predict_tags(lib, toks); pe = entities(ptags)
            r = res[lib]
            r["n"] += 1
            strip = lambda tags: [t.split("-")[-1] for t in tags]
            r["addr"] += strip(gold) == strip(ptags)
            for lab in LAB:
                g = {e for e in ge if e[0] == lab}; p = {e for e in pe if e[0] == lab}
                tp = len(g & p); r["ent"][lab][0] += tp; r["ent"][lab][1] += len(p) - tp; r["ent"][lab][2] += len(g) - tp
                for gt, pt in zip(gold, ptags):
                    gl = gt.split("-", 1)[1] if gt != "O" else None; pl = pt.split("-", 1)[1] if pt != "O" else None
                    if gl == lab and pl == lab: r["tok"][lab][0] += 1
                    elif pl == lab: r["tok"][lab][1] += 1
                    elif gl == lab: r["tok"][lab][2] += 1
    return res

def f1(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0; r = tp / (tp + fn) if tp + fn else 0
    return 2 * p * r / (p + r) if p + r else 0

def show(split, res):
    print(f"\n### {split}")
    for lib, nm in (("dp", "doorplate"), ("ua", "usaddress")):
        if lib not in res: continue
        r = res[lib]
        for kind in ("ent", "tok"):
            fs = {lab: f1(*r[kind][lab]) for lab in LAB}
            tp = sum(r[kind][l][0] for l in LAB); fp = sum(r[kind][l][1] for l in LAB); fn = sum(r[kind][l][2] for l in LAB)
            ps = sum(W[l] * fs[l] for l in LAB)
            print(f"{nm:10} {kind}: " + " ".join(f"{l[:5]}={fs[l]:.5f}" for l in LAB) + f" | overall micro F1={f1(tp,fp,fn):.5f} | parsing score={ps:.3f}")
        print(f"{nm:10} whole address (all 8 labels' tokens right): {r['addr']}/{r['n']} = {100*r['addr']/r['n']:.2f}%")

if __name__ == "__main__":
    for split in sys.argv[1:] or ["test"]:
        show(split, run(split))
