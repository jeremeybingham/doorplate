#!/usr/bin/env python3
"""Probes: how common is each open problem? (the backlog review, #298)

    python tools/harness/probes.py RECORDS.parquet [RECORDS.parquet ...] [--sample 10] [--compare 300]
                                   [--out report.md] [--queue FILE --queue-top 10 --queue-n 50] [--confirm]

A probe is one entry per open issue: a text pattern over the address (line 1 and line 2) and nothing else.
Run over the ingested records files it counts, per probe and source, the rows whose text has the shape, how
many of those the current parser flags (a warning, or a key without state and ZIP), and, with `--compare`,
how many of a sample of them usaddress reads differently (the review's disagreement test: a shape that
usaddress reads the same way is probably not a problem). Counts only, never a row (docs/data-policy.md).

The patterns are an upper bound: a text shape also matches correct rows (a real `FM 1960`, a valid box after
a street). `--compare` and the review queue (`--queue`: a comparison queue of `--queue-n` random matches of
each of the `--queue-top` probes with the most flagged rows, for `tools/review/server.py`) turn "has the shape"
into "is wrong". The score, `rows x harm / effort`, is how `docs/backlog.md` orders the issues.

The same registry is used by `tools/harness/run.py`, which adds `agg_probes` to a run's aggregates, so a full
Netsyms run counts every probe over all its rows without keeping any text.

Without `--confirm` it prints the plan and exits. This library formats and parses; it does not validate that an
address exists or can receive mail.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

SUF = r"(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|BLVD|HWY|PKWY|WAY|CT|PL|CIR|TRL)"
UN = r"(?:SUITE|STE|APT|UNIT|FL|FLOOR|RM|ROOM|BLDG)"
BOX = r"(?:P ?O\.? ?)?BOX"

# key, issue, name, pattern over T = upper(line1 | line2) ("|" separates the lines), size (S/M/L/D), harm (1 a component or
# warning only, 2 a wrong key with a warning, 3 a wrong key with no warning).
# The issue numbers are the ones of the 0.5.0 milestone after the backlog review (#298).
PROBES = [
    (
        "box-after-street",
        "299,300,301",
        "a box after a street number",
        rf"^[0-9]+ .*\b{BOX} [0-9]+",
        "M",
        3,
    ),
    (
        "box-first",
        "302",
        "a box first, then a street",
        rf"^{BOX} [0-9]+ [0-9A-Z ]+ {SUF}\b",
        "S",
        2,
    ),
    (
        "box-line1-street-line2",
        "303",
        "a PO box on line 1, a street on line 2 (a house number, or a name ending in a street suffix)",
        rf"^{BOX} [0-9]+ \| (?:[0-9]+ [A-Z]|[A-Z0-9 ]+ {SUF}\b)",
        "S",
        2,
    ),
    (
        "glued-box-route",
        "304",
        "box and route words glued to their number",
        r"\bPOBOX ?[0-9]|\bHCR ?[0-9]+ ?BOX|\bRR ?[0-9]+BOX|\bP O BOX[0-9]",
        "M",
        2,
    ),
    (
        "po-no-box",
        "305",
        "PO with no BOX",
        r"\bPO [0-9]{2,}|\bP\.? ?O\.? [0-9]{2,}",
        "S",
        2,
    ),
    ("rur-rte-hrc", "306", "RUR RTE, HRC", r"\bRUR(?:AL)? RTE\b|\bHRC [0-9]", "S", 2),
    (
        "route-after-street",
        "307",
        "a route after a street",
        rf"\b{SUF} (?:RR|RT|HC) ?[0-9]+",
        "S",
        2,
    ),
    (
        "campus-box",
        "131",
        "campus boxes (CPO, CPU, UNX BOX)",
        r"\b(?:CPO|CPU|CAMPUS BOX|CAMPUS MAIL)\b|\bUN[A-Z] BOX\b",
        "S",
        2,
    ),
    (
        "recipient-after-suffix",
        "131",
        "recipient text after the suffix",
        rf"\b{SUF} (?:C O|C/O|CO|ATTN|ATT) [A-Z]",
        "S",
        3,
    ),
    (
        "pr-urb-after-street",
        "318",
        "Puerto Rico URB after the street",
        r"[A-Z0-9] URB\.? [A-Z]",
        "S",
        2,
    ),
    (
        "pr-street-first",
        "319",
        "Puerto Rico street-first (CALLE ... 210), EDIF",
        r"^CALLE |\bEDIF\.? ",
        "M",
        2,
    ),
    (
        "hyphen-after-suffix",
        "308,341",
        "a spaced hyphen or slash after a suffix",
        rf"\b{SUF} [-/] [A-Z0-9]",
        "M",
        3,
    ),
    (
        "hyphen-in-unit",
        "309",
        "APT - 1, SUITE 12 - 340",
        rf"\b(?:APT|UNIT|STE|SUITE)\.? ?- ?[0-9]|\b{UN} [0-9]+ - [0-9]+",
        "S",
        2,
    ),
    (
        "grid-number",
        "311",
        "grid numbers (N45 W2210)",
        r"^[NSEW][0-9]{2,} [NSEW][0-9]{3,} ",
        "S",
        3,
    ),
    (
        "letter-before-number",
        "312",
        "a single letter before the house number",
        r"^[A-Z] [0-9]{3,} [A-Z]|^[NSEW] ?[0-9]{3,} [A-Z]",
        "D",
        3,
    ),
    (
        "queens-space",
        "313",
        "Queens and Hawaii numbers with a space",
        r"^[0-9]{2,3} [0-9]{2,3} [0-9]+(?:ST|ND|RD|TH) ",
        "S",
        3,
    ),
    (
        "tx-pr-fm",
        "314",
        "Texas PR / FM / RM / RR + number",
        r"\b(?:FM|RM|RR|PR) ?[0-9]{2,4}\b",
        "S",
        2,
    ),
    (
        "fm-before-type",
        "316",
        "the FM number written before the road type",
        r"^[0-9]+ [0-9]{3,4} (?:FM|RM) (?:RD|ROAD)\b",
        "S",
        3,
    ),
    (
        "and-between-highways",
        "317",
        "AND between two highways",
        r"\b(?:HWY|HIGHWAY|LOOP|IH|US|SH) [0-9A-Z]+ AND (?:HWY|HIGHWAY|LOOP|IH|US|SH) ",
        "S",
        3,
    ),
    ("repeated-line", "236", "street line written twice (halves equal)", None, "D", 2),
    (
        "building-before-number",
        "281",
        "a building name before the house number",
        rf"^[A-Z ]{{4,30}} [0-9]{{2,5}} (?:HWY|HIGHWAY|[A-Z]+ {SUF})",
        "S",
        2,
    ),
    (
        "spelled-number",
        "221",
        "ONE / TWO .. as a house number",
        r"^(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE) [A-Z]+",
        "S",
        3,
    ),
    ("so-for-south", "269", "SO for SOUTH after a street", rf"\b{SUF} SO\b", "S", 3),
    (
        "unit-is-suffix-code",
        "272",
        "a unit value that is a suffix code",
        r"\b(?:SUITE|STE|APT|UNIT) (?:LA|LN|DR|CT|RD|PL|ST|AVE|CIR|WAY|BLVD)(?: |$|,)",
        "S",
        2,
    ),
    (
        "ampersand-numbers",
        "274",
        "two house numbers joined by &",
        r"^[0-9]+ ?& ?[0-9]+ ",
        "S",
        3,
    ),
    (
        "two-suffix-then-unit",
        "243",
        "two suffix words then a unit (and ST for suite)",
        rf"\b{SUF} {SUF} (?:{UN}|[A-Z]+) [A-Z0-9-]+|\b(?:RD|BLVD|AVE|DR|LN|HWY|PKWY|WAY|CT|ROAD|AVENUE|DRIVE) ST [A-Z]?[0-9]",
        "M",
        3,
    ),
    (
        "sut-stu",
        "289",
        "SUT / STU / SIUTE misspelled designators",
        r"\b(?:SUT|STU|SIUTE) ?[A-Z]?[0-9]",
        "S",
        3,
    ),
    (
        "hash-before-designator",
        "340",
        "a # before a unit designator (# APT-4, #APT-18, # APT 4)",
        r"#\s*(?:APT|UNIT|STE|SUITE|RM|ROOM|LOT|TRLR|BLDG|FL)[ .]*-?\s*[0-9A-Z]",
        "S",
        1,
    ),
    (
        "units-ampersand",
        "290",
        "SUITE 2&3",
        rf"\b{UN} ?#?[A-Z0-9]+ ?& ?[A-Z0-9]+\b",
        "S",
        3,
    ),
    (
        "floor-in-parentheses",
        "291",
        "a floor in parentheses",
        r"\(.{0,6}(?:FL|FLOOR)\)",
        "S",
        2,
    ),
    (
        "level-words",
        "292",
        "level and floor words (LL, LOWER LEVEL, GROUND, ATC, GARAGE)",
        r"\b(?:LOWER LEVEL|GARDEN LEVEL|GROUND FL|GROUND FLOOR|ATTIC|BASEMENT LEVEL)\b|\| (?:LL|ATC|GROUND)$|\bGARAGE [0-9]",
        "M",
        2,
    ),
    (
        "no-as-unit",
        "293",
        "NO. as a unit word",
        rf"\| NO\.? ?[0-9]|\b{SUF} NO\.? ?[0-9]+",
        "D",
        1,
    ),
    (
        "unit-two-parts",
        "294",
        "a unit value of two parts (and two bare numbers on line 2)",
        rf"\b{UN} [A-Z] [A-Z]\b|\b{UN} [A-Z][0-9] [0-9]+\b|\| [0-9] [A-Z]$|\| [0-9]+ [0-9]+$",
        "S",
        3,
    ),
    (
        "bldg-after-route",
        "295",
        "BLDG after a route",
        r"\b(?:ROUTE|RT|RTE) [0-9]+ (?:BLDG|BUILDING) ",
        "S",
        2,
    ),
    (
        "unit-before-street",
        "296",
        "a unit between the house number and the street",
        rf"^[0-9]+(?:-[0-9]+)? {UN} [A-Z0-9]+ [A-Z]+",
        "S",
        3,
    ),
    ("bare-bay", "193", "a bare BAY", r"(?: |\| )BAY(?: \||$)", "S", 1),
    ("po-box-equals-zip", "260", "PO BOX on line 2 equal to the ZIP", None, "S", 2),
    (
        "placeholder",
        "273",
        "placeholder text (NO ADDRESS, N/A, NONE)",
        r"^(?:NO ADDRESS|NONE|N/?A|UNKNOWN|NOT AVAILABLE|NO STREET|ADDRESS UNKNOWN)\b",
        "S",
        1,
    ),
    (
        "no-suffix-then-bare-unit",
        "324",
        "a street with no suffix word, then a bare unit, on one line",
        rf"^[0-9]+ (?![^|]*\b(?:{SUF[3:-1]}|HWY|HIGHWAY|ROUTE|RT|RTE|COUNTY|CO|STATE|SR|US|FM|RM|RR|BOX|PO)\b)(?:[A-Z]+ ){{1,3}}(?:[0-9]{{1,4}}|[ABCDFGHIJKLMOPQRTUVXYZ]|[0-9]{{1,3}}[A-Z]|[0-9]+-[0-9]+)(?: \||$)",
        "M",
        3,
    ),
    (
        "letter-before-hyphen",
        "326",
        "a letter before the hyphen in a house number (53A-53)",
        r"^[0-9]+[A-Z]-[0-9]+ [A-Z]",
        "S",
        3,
    ),
    (
        "pier-last-word",
        "327",
        "PIER as the last word of a street name, or a pier number ahead of the street",
        r"\bPIER(?: \||$)|^PIER [0-9]+ [A-Z]",
        "S",
        2,
    ),
    (
        "spaced-hyphen-building",
        "310",
        "a spaced hyphen between a building name and a street",
        r"^[A-Z][A-Z .&']{3,30} - [0-9]+ [A-Z]",
        "S",
        3,
    ),
    (
        "bare-unit-line2",
        "320",
        "unit text with no designator on line 2 (4 REAR, B12, 12 14)",
        r"\| (?:[0-9]{1,4} [A-Z]{3,}|[A-Z][0-9]{1,4}|[0-9]{1,4} [0-9]{1,4})$",
        "M",
        2,
    ),
    (
        "unlisted-unit-words",
        "321",
        "words Pub 28 does not list (COND, SITE, CAMPSITE, UNIT NORTH, FLOOR 2 LEFT)",
        r"\b(?:CND|COND|CONDO|SITE|CAMPSITE)\.? ?#?[0-9A-Z]+|\b(?:UNIT|APARTMENT) (?:NORTH|SOUTH|EAST|WEST|REAR|FRONT|UPPER|LOWER|LEFT|RIGHT)\b|\bFLOOR [0-9]+ (?:LEFT|RIGHT)\b",
        "M",
        1,
    ),
    (
        "name-road-number",
        "315",
        "<NAME> ROAD <number> county roads (LEE ROAD 2004)",
        r"^[0-9]+ [A-Z]+ (?:ROAD|RD) [0-9]{1,4}(?: \||$)",
        "D",
        2,
    ),
    (
        "care-of-no-separator",
        "259",
        "care-of text at the front with no separator",
        rf"^[A-Z ,.&']{{3,40}}\b(?:LLC|INC|CORP|LTD|CO|LP|LLP)\b[ ,.]+[0-9]+ [A-Z0-9 ]+ {SUF}\b",
        "M",
        3,
    ),
    # Probes for the issues filed after the first registry (2026-10-31): patterns over line 1 and line 2, as above.
    (
        "single-letter-name-initial",
        "360",
        "a single letter after the house number before a name and suffix (77 B BEAL RD, 9311 J W CLAY BLVD)",
        rf"^[0-9]+ [ABCDFGHIJKLMOPQRTUVXYZ] (?:[A-Z] )?[A-Z]{{3,}}[A-Z ]* {SUF}\b",
        "M",
        3,
    ),
    (
        "unit-copies-street-word",
        "362",
        "a unit that copies the street's suffix or direction (VEGA LOOP #LN, US HWY 13 N # NORTH, ORANGE ST # 1/2)",
        rf"\b(?:{SUF}|LOOP|N|S|E|W) ?# ?(?:RD|DR|LN|CT|ST|AVE|PL|LOOP|NORTH|SOUTH|EAST|WEST|N|S|E|W|1/2)(?: \||$)",
        "M",
        2,
    ),
    (
        "name-and-floor-line1",
        "351",
        "a name and a floor on line 1 with the street on line 2",
        rf"^[A-Z][A-Z .&']+ (?:[0-9]+(?:ST|ND|RD|TH) )?(?:FL|FLOOR)\b[^|]*\| [0-9]+ [A-Z0-9 ]+ {SUF}\b",
        "S",
        3,
    ),
    (
        "po-box-placeholder-line2",
        "358",
        "PO BOX with a placeholder word or no number on line 2 (PO BOX NA, PO BOX None, P. O. BOX)",
        rf"\| {BOX}(?: (?:NA|N/A|NONE|NO|NULL|UNKNOWN|0+|X+))? ?$",
        "S",
        2,
    ),
    (
        "box-then-street-words",
        "366",
        "a box followed by street words (P O BOX 2856 MEADOW RD)",
        rf"^{BOX} [0-9]+ [A-Z]+(?: [A-Z]+){{0,2}} {SUF}\b(?! ?[0-9])",
        "S",
        2,
    ),
    (
        "co-prefix-fuller-name-line2",
        "367",
        "a CO prefix on line 1 and a % name on line 2 (CO HARBOR 2100 OAK ST over % HARBOR HOLDINGS)",
        rf"^CO [A-Z0-9&' ]+ [0-9]+ [A-Z0-9 ]+ {SUF}\b[^|]*\| ?%",
        "S",
        3,
    ),
    (
        "word-number-after-suffix",
        "375",
        "a designator-like word and a number after a street suffix (1900 OAK AVE MSC 518)",
        rf"^[0-9]+ [A-Z0-9 ]+ {SUF} (?!(?:{UN}|BOX|PO|PMB|NO|NUM|LOT|SPC|SP|TRLR|APT|STE|UNIT|DEPT|RM|BLDG|FL)\b)[A-Z]{{2,5}}(?: BOX)? [0-9]+[A-Z]?(?: \||$)",
        "S",
        2,
    ),
    (
        "half-without-slash",
        "247",
        "a half written without its slash (31 1 2 ELM PLACE)",
        r"^[0-9]+ (?:[0-9]+ )?(?:1 2|1 4|3 4) [A-Z]{2}",
        "S",
        2,
    ),
    # Needs the city field (hits(): city and state), so no pattern.
    ("city-is-state", "357", "the city field holds the state and the real city is on line 2", None, "S", 3),
    ("unit-or-box-in-city", "244", "a unit or a box in the city field", None, "S", 2),
]
# Open rule issues that have no probe, and why. Every other open issue with the label `area:rules` has a probe in PROBES; the
# issues about docs, tooling, the API or the architecture, and the trackers, are not text shapes and need none.
NO_PROBE = {
    11: "research: which state data to add; no text shape, a gap in the tables",
    92: "research: the uncited parts of Pub 28; reading work, not a shape",
    213: "research: whether more state data is needed; measured by the label comparisons, not a text shape",
    238: "a family of unit misses in NAD, split into #320 and #321, which have probes",
    345: "research: a bare number after a street is a unit in some sources and a name in others; no text shape tells them apart",
}
NOT_A_SHAPE_LABELS = ("tracker", "area:docs", "area:tooling", "area:api", "area:architecture")


def coverage(issues):
    """Which open issues are proved by a probe. `issues` is the list of open issues (dicts with `number` and `labels`, as
    `gh issue list --json number,labels` gives them). Returns ({number: [probe keys]}, {number: reason}, [numbers with neither]).
    Counts of issue numbers only."""
    by_issue = {}
    for key, issue, *_ in PROBES:
        for i in str(issue).split(","):
            if i.strip().isdigit():
                by_issue.setdefault(int(i), []).append(key)
    covered, excused, missing = {}, {}, []
    for it in issues:
        n = it["number"]
        labels = {lab["name"] if isinstance(lab, dict) else lab for lab in it.get("labels", [])}
        if labels & set(NOT_A_SHAPE_LABELS):
            continue
        if n in by_issue:
            covered[n] = by_issue[n]
        elif n in NO_PROBE:
            excused[n] = NO_PROBE[n]
        elif "area:rules" in labels:
            missing.append(n)
    return covered, excused, sorted(missing)


EFFORT = {"S": 1, "M": 2, "L": 4, "D": 2}
FLAGGED = (
    "unparsed_remainder",
    "missing_street_number",
    "possibly_truncated",
    "missing_unit_number",
    "invalid_zip",
)

_COMPILED = {}


def text_of(line1, line2):
    """The text a pattern sees: both lines, upper-cased, `|` between them."""
    return f"{(line1 or '').upper()} | {(line2 or '').upper()}"


def regexes():
    """{key: compiled pattern} for the probes that are a pattern (Python `re`; the DuckDB runner uses the same text)."""
    if not _COMPILED:
        for key, _issue, _name, rx, _size, _harm in PROBES:
            if rx:
                _COMPILED[key] = re.compile(rx)
    return _COMPILED


CITY_UNIT = re.compile(rf"^(?:{UN}|BOX|{BOX}|#)\b")


def repeated_line(line1):
    """Line 1 is the same words twice (`812 ASHGROVE ST 812 ASHGROVE ST`): four or more words, the halves equal."""
    w = re.sub(r"[^A-Z0-9 ]", " ", (line1 or "").upper()).split()
    return len(w) >= 4 and len(w) % 2 == 0 and w[: len(w) // 2] == w[len(w) // 2 :]


def hits(line1, line2, zip_code=None, city=None, state=None):
    """Probe keys whose pattern matches this address. `city` and `state` are for the two probes on the city field;
    `repeated-line` needs no pattern (the halves of line 1 are equal)."""
    t = text_of(line1, line2)
    out = [k for k, rx in regexes().items() if rx.search(t)]
    c = (city or "").upper().strip()
    # The city field holds the state (NY, or the state's name) and line 2 is plain words: the real city is there (#357).
    if c and state and (c == str(state).upper().strip()) and re.fullmatch(r"[A-Z][A-Z .'-]+", (line2 or "").upper().strip()):
        out.append("city-is-state")
    # A unit designator or a box in the city field (#244).
    if c and CITY_UNIT.match(c):
        out.append("unit-or-box-in-city")
    # The street line written twice (#236).
    if repeated_line(line1):
        out.append("repeated-line")
    # PO BOX on line 2 whose number is the ZIP.
    m = re.match(rf"^{BOX} ([0-9]{{5}})$", (line2 or "").upper().strip())
    if m and zip_code and m.group(1) == str(zip_code)[:5]:
        out.append("po-box-equals-zip")
    return out


PR_WORDS = re.compile(r"\b(?:URB|URBANIZACION|CALLE|EDIF|EDIFICIO|CARR|CARRETERA|BARRIO|RESIDENCIAL|PUERTO RICO)\b")


def is_puerto_rico(row):
    """Whether a record looks like a Puerto Rico address: state PR, a ZIP of 006, 007 or 009, or a Spanish street word.
    A superset on purpose: the review queue leaves these out until the Puerto Rico epic has its own queue."""
    z = str(row.get("zip") or "")[:3]
    st = str(row.get("state") or "").upper().strip()
    return st in ("PR", "PUERTO RICO") or z in ("006", "007", "009") or bool(PR_WORDS.search(text_of(row.get("line1"), row.get("line2"))))


PARTIAL_KEY = re.compile(r"^k[0-9]+n:")


def is_partial_key(key):
    """A key without state and ZIP (`k4n:`, `k4n:`: the prefix of any version)."""
    return bool(PARTIAL_KEY.match(str(key)))


def is_flagged(warnings, key):
    """A warning from the list, or a key without state and ZIP."""
    return bool(set(warnings) & set(FLAGGED)) or is_partial_key(key)


def score(rows, harm, size, precision=1.0):
    return rows * precision * harm / EFFORT[size]


BASELINE_DISAGREE = 0.03  # usaddress disagrees with the parser on about 3% of ordinary rows (the #132 queues: 2.6% to 3.3%)


def summarize(report, baseline=BASELINE_DISAGREE):
    """Rows, share, flagged, precision, score and the priority the score suggests, per probe, from a report.

    Precision is the excess usaddress disagreement among the matches: how far above the ordinary 3% the rate is. It is a
    proxy (usaddress can be wrong too, and a rate below the baseline means the shape is probably fine), not a review
    verdict; a person's marks on the review queue replace it. Priority: P1 above 0.1% of the rows, P2 above 0.01%, else P3,
    on the precision-corrected rows (docs/backlog.md, "Ordering by how common")."""
    sample = report["sample"]
    total = sum(s["rows_seen"] for s in report["sources"].values()) * sample
    meta = {p[0]: p for p in PROBES}
    agg = {}
    for src in report["sources"].values():
        for k, v in src["probes"].items():
            a = agg.setdefault(k, {"rows": 0, "flagged": 0, "compared": 0, "disagree": 0})
            for f in a:
                a[f] += v[f]
    out = []
    for k, a in agg.items():
        _key, issue, name, _rx, size, harm = meta[k]
        rows, flagged = a["rows"] * sample, a["flagged"] * sample
        rate = a["disagree"] / a["compared"] if a["compared"] else None
        prec = 1.0 if rate is None else max(0.0, min(1.0, rate - baseline))
        real = rows * prec
        share = real / total
        pr = "P1" if share > 0.001 else "P2" if share > 0.0001 else "P3"
        out.append(
            {"probe": k, "issue": issue, "name": name, "size": size, "harm": harm, "rows": rows, "flagged": flagged, "rate": rate,
             "precision": prec, "real_rows": real, "share": share, "score": score(rows, harm, size, prec), "priority": pr}
        )
    out.sort(key=lambda r: -r["score"])
    return out, total


def run_source(path, sample, seed, compare, con, keep=0):
    """({key: {"rows", "flagged", "partial_key", "compared", "disagree"}}, rows seen, {key: up to `keep` matching rows})
    for one records file."""
    import doorplate

    cols = {r[0] for r in con.execute("describe select * from read_parquet(?)", [str(path)]).fetchall()}
    names = (
        "line1",
        "line2",
        "city",
        "state",
        "zip",
        "last_line",
        "source",
        "role",
        "record_id",
    )
    sel = ", ".join(c if c in cols else f"NULL AS {c}" for c in names)
    where = f"where hash(rn + {int(seed)}) % {int(sample)} = 0" if sample > 1 else ""
    rows = con.execute(
        f"select {', '.join(names)} from (select row_number() over () as rn, {sel} from read_parquet(?)) {where}",
        [str(path)],
    ).fetchall()
    found = {}
    samples = {}
    matched = {}
    for i, (l1, l2, c, s, z, ll, *_rest) in enumerate(rows):
        for k in hits(l1, l2, z, c, s):
            matched.setdefault(k, []).append(i)
    seen = len(rows)
    usaddress = cmp_string = None
    if compare:
        try:
            import usaddress

            sys.path.insert(0, str(ROOT / "tools" / "review"))
            from compare_sample import compare_string as cmp_string
        except ImportError:
            usaddress = None
    for k, idx in matched.items():
        recs = [rows[i] for i in idx]
        out = {"rows": len(idx), "flagged": 0, "partial_key": 0, "compared": 0, "disagree": 0}
        res = doorplate.parse_fields_many(
            line1=[r[0] for r in recs],
            line2=[r[1] for r in recs],
            city=[r[2] for r in recs],
            state=[r[3] for r in recs],
            zip=[r[4] for r in recs],
        )
        for r, a in zip(recs, res):
            if a is None:
                continue
            key = a.key()
            out["flagged"] += int(is_flagged(a.warnings, key))
            out["partial_key"] += int(is_partial_key(key))
        if usaddress is not None and cmp_string is not None:
            step = max(1, len(recs) // compare)
            for r in recs[::step][:compare]:
                s = ", ".join(" ".join(p.split()) for p in (r[0], r[1], r[2], " ".join(x for x in (r[3], r[4]) if x)) if p and p.strip())
                out["compared"] += 1
                out["disagree"] += int(cmp_string(s, doorplate, usaddress) is not None)
        found[k] = out
        # A random pick of the matches (seeded), not the first `keep` in file order: a file is often sorted, so the head holds
        # one provider or one county, and a review of it is a review of that corner (queue-probes3 came from 200 consecutive rows).
        picked = recs if len(recs) <= keep else random.Random(f"{seed}-{k}").sample(recs, keep)
        samples[k] = [dict(zip(names, r)) for r in picked]
    return found, seen, samples


def queue(args, report, pool):
    """A comparison review queue (tools/review/compare_sample.py format) of matches where usaddress disagrees."""
    import random

    import doorplate
    import usaddress

    sys.path.insert(0, str(ROOT / "tools" / "review"))
    import compare_sample as cs

    out = args.queue.resolve()
    if "local-data" not in out.parts:
        sys.exit(f"{out} is outside local-data/")
    flagged = {}
    for src in report["sources"].values():
        for k, v in src["probes"].items():
            flagged[k] = flagged.get(k, 0) + v["flagged"]
    skip = {k for k in args.exclude_probes.split(",") if k}
    top = [k for k, _ in sorted(flagged.items(), key=lambda kv: -kv[1]) if k not in skip][: args.queue_top]
    rng = random.Random(args.seed)
    entries = []
    for k in top:
        rows_ = pool.get(k, [])
        if args.exclude_pr:
            rows_ = [r for r in rows_ if not is_puerto_rico(r)]
        rng.shuffle(rows_)
        n = 0
        for r in rows_:
            if n >= args.queue_n:
                break
            s = cs.one_line(r)
            res = cs.compare_string(s, doorplate, usaddress)
            if res is None:
                continue
            n += 1
            f = {
                "row": r,
                "sig": f"probe {k}",
                "result": res,
                "class": res["class"],
                "size": len(rows_),
            }
            entries.append(cs.entry(len(entries) + 1, f))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(e) + "\n" for e in entries))
    print(f"wrote {len(entries)} review rows for {len(top)} probes to {out.name}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("records", nargs="*", type=Path, help="records.parquet files (tools/ingest/)")
    ap.add_argument("--summary", type=Path, help="print the table (rows, precision, score, priority) from a report written by --out")
    ap.add_argument(
        "--sample",
        type=int,
        default=10,
        help="keep 1 row in N (default 10; 1 = every row)",
    )
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument(
        "--compare",
        type=int,
        default=300,
        help="rows per probe and source compared with usaddress (0 = none)",
    )
    ap.add_argument("--out", type=Path, help="write the counts as JSON here (under local-data/)")
    ap.add_argument(
        "--queue",
        type=Path,
        help="write a comparison review queue of matches here (under local-data/review/)",
    )
    ap.add_argument(
        "--queue-top",
        type=int,
        default=10,
        help="probes with the most flagged rows to put in the queue",
    )
    ap.add_argument("--queue-n", type=int, default=50, help="matches per probe")
    ap.add_argument("--exclude-probes", default="", help="comma-separated probe keys to leave out of the queue (already reviewed, or held back)")
    ap.add_argument("--exclude-pr", action="store_true", help="leave Puerto Rico rows out of the queue (is_puerto_rico)")
    ap.add_argument("--coverage", action="store_true", help="check that every open rule issue has a probe or a reason (needs `gh`); numbers only")
    ap.add_argument("--confirm", action="store_true", help="run (without it: the plan only)")
    args = ap.parse_args(argv)
    if args.coverage:
        import subprocess

        raw = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--limit", "500", "--json", "number,labels"],
            capture_output=True, text=True, check=True,
        ).stdout
        covered, excused, missing = coverage(json.loads(raw))
        print(f"open rule issues with a probe: {len(covered)}; with a reason and no probe: {len(excused)}; with neither: {len(missing)}")
        for n, why in sorted(excused.items()):
            print(f"  #{n}: no probe, {why}")
        for n in missing:
            print(f"  #{n}: NO PROBE and no reason")
        closed = sorted({k for k, issue, *_ in PROBES for i in str(issue).split(",") if i.strip().isdigit() and int(i) not in covered} )
        print(f"{len(closed)} of {len(PROBES)} probes belong to issues that are not open (the closed half of the proof)")
        return 1 if missing else 0
    if args.summary:
        table, total = summarize(json.loads(args.summary.read_text()))
        print(f"{total:,} rows represented")
        print("score  priority  issue(s)  rows  share-real  precision  flagged  probe")
        for r in table:
            print(
                f"{r['score']:>9,.0f}  {r['priority']}  #{r['issue']:<12} {r['rows']:>9,.0f}  {100 * r['share']:6.3f}%  "
                f"{r['precision']:4.0%}  {r['flagged']:>8,.0f}  {r['probe']}"
            )
        return 0
    if not args.records:
        ap.error("give records files, or --summary REPORT")
    print(
        f"plan: {len(PROBES)} probes over {len(args.records)} records file(s), 1 row in {args.sample}, "
        f"usaddress comparison on up to {args.compare} matches per probe and source"
    )
    if not args.confirm:
        return 0
    import duckdb

    con = duckdb.connect()
    report = {"sample": args.sample, "sources": {}}
    pool = {}
    for p in args.records:
        try:
            found, seen, samples = run_source(
                p,
                args.sample,
                args.seed,
                args.compare,
                con,
                keep=args.queue_n * 4 if args.queue else 0,
            )
            for k, rows_ in samples.items():
                pool.setdefault(k, []).extend(rows_)
        except Exception as e:  # noqa: BLE001 (DuckDB errors can quote rows)
            sys.exit(f"{p.name}: failed: {type(e).__name__}")
        report["sources"][str(p)] = {"rows_seen": seen, "probes": found}
        print(f"{p.name}: {seen} rows seen, {sum(v['rows'] for v in found.values())} probe hits")
    if args.queue:
        queue(args, report, pool)
    if args.out:
        out = args.out.resolve()
        if "local-data" not in out.parts:
            sys.exit(f"{out} is outside local-data/")
        out.write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
