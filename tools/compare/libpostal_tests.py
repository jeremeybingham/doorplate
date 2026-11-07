#!/usr/bin/env python3
"""Score doorplate, usaddress and libpostal on libpostal's own tests and on Senzing's test set (issue 215, step 4).

    python tools/compare/libpostal_tests.py own [--libpostal-home DIR]
    python tools/compare/libpostal_tests.py senzing [--csv FILE] [--libpostal-home DIR]

`own` reads the US cases of libpostal's `test/test_parser.c` (`test_us_parses`: an input string and the labelled components
libpostal is expected to return) from the libpostal clone (`DIR/src`, default `$LIBPOSTAL_HOME` or
`~/projects/libpostal-senzing`); nothing is copied into this repository. They are libpostal's regression tests, so a high score
for libpostal is expected and is not a contest, as with usaddress's own test files. `senzing` reads the US rows
(`country_code` is `us`) of the test set that Senzing publishes with its models (`test_data_v1.2.0.csv`, kept in
`local-data/senzing-libpostal-test/`: it has no license statement, so only these aggregates leave the folder).

All three parsers are scored on the same fields: house number, road, place, state, ZIP, and the unit when the gold has one. A row
is right when **every field present in its gold is right** (a field the parser adds that the gold lacks is ignored). Text is
compared as written, lowercased, without punctuation. A state is compared by its code. A place is right when it equals the gold
city, suburb or city district, or the gold fields joined in the order they appear in the input. For libpostal the place is its
`suburb`, `city_district` and `city` pieces in order, and the road is its `road`; for doorplate and usaddress it is the
`PlaceName` and the street-part tokens of `to_usaddress_tags()` and `usaddress.parse()`. Output is counts and rates, never an
address. This library formats and parses; it does not validate that an address exists or can receive mail.
"""

import argparse
import collections
import csv
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import compare_usaddress as C

DEFAULT_CSV = ROOT / "local-data" / "senzing-libpostal-test" / "test_data_v1.2.0.csv"
FIELDS = ("number", "road", "place", "state", "zip", "unit")
STREET = (
    "StreetNamePreDirectional", "StreetNamePreModifier", "StreetNamePreType", "StreetName", "StreetNamePostType",
    "StreetNamePostDirectional",
)  # fmt: skip
PLACE_LABELS = ("suburb", "city_district", "city")
UNIT_LABELS = ("unit", "level", "staircase", "entrance")


def norm(s):
    """Lowercase, punctuation and hyphens to spaces, runs of spaces collapsed."""
    return " ".join(re.sub(r"[^a-z0-9 ]", "", (s or "").lower().replace("-", " ")).split())


def state_code(s, parse):
    """A state as a code when doorplate reads it as one (`new york` and `n.y.` both become `ny`), else as written."""
    s = norm(s)
    if not s:
        return ""
    try:
        return norm(parse(f"1 A ST, B {s}").state or s)
    except Exception:  # noqa: BLE001
        return s


def zip5(s):
    return norm(s)[:5]


# ---- the gold from libpostal's C test file -------------------------------------------------------------------

CASE = re.compile(r'test_parse_result_equals\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*options\s*,\s*(\d+)\s*,(.*?)\)\s*\)\s*;', re.DOTALL)
COMPONENT = re.compile(r'\(labeled_component_t\)\s*\{\s*"([a-z_]+)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\}')


C_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "'": "'"}


def c_string(s):
    """The text of a C string literal: \\n, \\t, \\r, \\", \\' and \\\\ undone (anything else is kept as written)."""
    return re.sub(r"\\(.)", lambda m: C_ESCAPES.get(m.group(1), m.group(0)), s)


def us_cases(c_source):
    """[(input, [(label, component)])] of the `test_us_parses` function of libpostal's test/test_parser.c."""
    start = c_source.find("TEST test_us_parses")
    if start < 0:
        sys.exit("no test_us_parses in the test file")
    end = c_source.find("\nTEST ", start + 10)
    body = c_source[start : end if end > 0 else len(c_source)]
    body = re.sub(r"(?m)^\s*//.*$", "", body)  # a comment line between a case's arguments
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    n_calls = body.count("test_parse_result_equals(")
    out = []
    for m in CASE.finditer(body):
        comps = [(label, c_string(text)) for label, text in COMPONENT.findall(m.group(3))]
        if len(comps) != int(m.group(2)):
            sys.exit("a test case has a different number of components than it declares")
        out.append((c_string(m.group(1)), comps))
    if len(out) != n_calls:
        sys.exit(f"read {len(out)} of {n_calls} test cases: the test file has a form this reader does not know")
    return out


def gold_from_components(comps):
    """The fields a libpostal expected-parse names, in the shared field set (empty when absent)."""
    g = collections.defaultdict(list)
    for label, text in comps:
        g[label].append(text)
    return {
        "number": [norm(t) for t in g["house_number"]],
        "road": [norm(t) for t in g["road"]],
        "place": [norm(t) for label in PLACE_LABELS for t in g[label]],
        "state": g["state"],
        "zip": g["postcode"],
        "unit": [norm(t) for label in UNIT_LABELS for t in g[label]],
    }


def gold_from_row(r):
    one = lambda *keys: [r[k] for k in keys if r.get(k)]
    return {
        "number": [norm(t) for t in one("house_number")],
        "road": [norm(t) for t in one("road")],
        "place": [norm(t) for t in one("suburb", "city_district", "city")],
        "state": one("state"),
        "zip": one("postcode"),
        "unit": [norm(t) for t in one("unit", "level", "staircase", "entrance")],
    }


# ---- the three parsers, reduced to the shared fields ---------------------------------------------------------


def from_tags(tags):
    """Fields from [(token, usaddress label)] (doorplate's to_usaddress_tags or usaddress.parse)."""

    def g(*labels):
        return norm(" ".join(t for t, label in tags if label in labels))

    return {
        "number": g("AddressNumber"), "road": g(*STREET), "place": g("PlaceName"), "state": g("StateName"),
        "zip": g("ZipCode"), "unit": g("OccupancyType", "OccupancyIdentifier", "SubaddressType", "SubaddressIdentifier"),
    }  # fmt: skip


def from_libpostal(parsed):
    def g(*labels):
        return norm(" ".join(v for v, label in parsed if label in labels))

    return {
        "number": g("house_number"), "road": g("road"), "place": g(*PLACE_LABELS), "state": g("state"),
        "zip": g("postcode"), "unit": g(*UNIT_LABELS),
    }  # fmt: skip


def place_ok(pred, gold_places, text):
    """A place is right when it is one gold place field or the gold fields joined in the order they occur in the input."""
    if pred in gold_places:
        return True
    low = norm(text)
    ordered = sorted((g for g in gold_places if g), key=lambda g: low.find(g) if g in low else len(low))
    return " ".join(ordered) == pred


def score_row(pred, gold, text, parse):
    """The shared fields that are wrong for one row (only the fields the gold has are checked)."""
    bad = []
    for f in FIELDS:
        want = gold[f]
        if not want:
            continue
        p = pred[f]
        if f == "state":
            ok = state_code(p, parse) in {state_code(w, parse) for w in want}
        elif f == "zip":
            ok = zip5(p) in {zip5(w) for w in want}
        elif f == "place":
            ok = place_ok(p, want, text)
        else:
            ok = p == " ".join(want) or p in want
        if not ok:
            bad.append(f)
    return bad


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def cell(k, n):
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% ({100 * lo:.1f} to {100 * hi:.1f})"


def run(rows, args, title, selection):
    """rows: [(input text, gold fields, libpostal's expected [(label, text)] or None)]."""
    import doorplate
    import usaddress

    texts = [t for t, _, _ in rows]
    lp = C.libpostal_run(texts, args.libpostal_home)
    pins = C.libpostal_pins(args.libpostal_home)
    wrong = {w: collections.Counter() for w in ("doorplate", "usaddress", "libpostal")}
    ok = collections.Counter()
    right = {w: [] for w in wrong}
    exact = 0
    for (text, gold, expected), parsed in zip(rows, lp["results"]):
        try:
            d = from_tags(doorplate.parse(text).to_usaddress_tags())
        except Exception:  # noqa: BLE001  (an input a library rejects scores as wrong)
            d = from_tags([])
        try:
            u = from_tags(list(usaddress.parse(text)))
        except Exception:  # noqa: BLE001
            u = from_tags([])
        preds = {"doorplate": d, "usaddress": u, "libpostal": from_libpostal(parsed)}
        for who, pred in preds.items():
            bad = score_row(pred, gold, text, doorplate.parse)
            right[who].append(not bad)
            ok[who] += not bad
            wrong[who].update(bad)
        if expected is not None:
            exact += [(label, norm(v)) for v, label in parsed] == [(label, norm(v)) for label, v in expected]
    n = len(rows)
    out = [
        f"## {title}", "",
        selection, "",
        f"libpostal commit {pins['commit']}, parser model {pins['parser_model']}, data checksum {pins['data_checksum'][:12]}. "
        f"doorplate {doorplate.__version__}.", "",
        "A row is right when every field present in its gold is right (house number, road, place, state, ZIP and unit); "
        "intervals are 95% Wilson.", "",
        "| Rows | doorplate | usaddress | libpostal |", "|---|---|---|---|",
        f"| {n:,} | " + " | ".join(cell(ok[w], n) for w in ("doorplate", "usaddress", "libpostal")) + " |", "",
        "Rows with a wrong field, by field:", "", "| Field | doorplate | usaddress | libpostal |", "|---|---|---|---|",
    ]  # fmt: skip
    for f in FIELDS:
        out.append(f"| {f} | " + " | ".join(str(wrong[w][f]) for w in ("doorplate", "usaddress", "libpostal")) + " |")
    both = sum(a and b for a, b in zip(right["doorplate"], right["libpostal"]))
    only_d = sum(a and not b for a, b in zip(right["doorplate"], right["libpostal"]))
    only_l = sum(b and not a for a, b in zip(right["doorplate"], right["libpostal"]))
    out += ["", "| Both right | Only doorplate | Only libpostal | Both wrong |", "|---|---|---|---|",
            f"| {both:,} | {only_d:,} | {only_l:,} | {n - both - only_d - only_l:,} |", ""]  # fmt: skip
    if any(e is not None for _, _, e in rows):
        out += [f"libpostal returned exactly the expected labelled components (all labels, lowercase compared without "
                f"punctuation) for {exact:,} of {n:,} cases.", ""]
    return out


def own_cmd(args):
    home = C.libpostal_home(args.libpostal_home)
    path = Path(home) / "src" / "test" / "test_parser.c"
    if not path.exists():
        sys.exit(f"no {path} (the libpostal clone; set --libpostal-home)")
    cases = us_cases(path.read_text(encoding="utf-8"))
    rows = [(text, gold_from_components(comps), comps) for text, comps in cases]
    return run(
        rows, args, "libpostal's own US parser tests",
        f"The {len(rows)} cases of `test_us_parses` in libpostal's `test/test_parser.c` (its regression tests, read from the clone). "
        "libpostal is expected to score near 100%; read the gap for the other two as where they differ from libpostal, not as a contest.",
    )  # fmt: skip


def senzing_cmd(args):
    path = Path(args.csv)
    if not path.exists():
        sys.exit(f"no {path} (Senzing's test set; see docs/data-policy.md)")
    with path.open(encoding="utf-8", newline="") as fh:
        us = [r for r in csv.DictReader(fh) if r["country_code"] == "us"]
    rows = [(r["full_address"], gold_from_row(r), None) for r in us]
    return run(
        rows, args, "Senzing's test set, US rows",
        f"The {len(rows):,} rows of `{path.name}` whose `country_code` is `us` (nearly all are OpenStreetMap address tags written out as one "
        "line: clean, uniform input). It is the test set Senzing scores its libpostal models on; its figures use a definition of failure "
        "that is not stated, so these are not comparable with them.",
    )  # fmt: skip


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["own", "senzing"])
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--libpostal-home", help="the libpostal build folder (default: $LIBPOSTAL_HOME or ~/projects/libpostal-senzing)")
    ap.add_argument("--out", help="write the Markdown here as well")
    args = ap.parse_args(argv)
    text = "\n".join({"own": own_cmd, "senzing": senzing_cmd}[args.cmd](args)) + "\n"
    sys.stdout.write(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
