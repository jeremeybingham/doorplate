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
# A state's name, or LA (La Mesa), as the first word of a city written with no state (#480).
STATE_FIRST = (r"(?:ALABAMA|ALASKA|ARIZONA|ARKANSAS|CALIFORNIA|COLORADO|CONNECTICUT|DELAWARE|FLORIDA|GEORGIA|HAWAII|IDAHO|ILLINOIS|INDIANA|IOWA|"
               r"KANSAS|KENTUCKY|LOUISIANA|MAINE|MARYLAND|MASSACHUSETTS|MICHIGAN|MINNESOTA|MISSISSIPPI|MISSOURI|MONTANA|NEBRASKA|NEVADA|"
               r"OHIO|OKLAHOMA|OREGON|PENNSYLVANIA|TENNESSEE|TEXAS|UTAH|VERMONT|VIRGINIA|WASHINGTON|WISCONSIN|WYOMING|LA)")

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
        "space-split-long-number",
        "501",
        "a five-digit house number written as two parts (2 + 3 digits)",
        r"^[0-9]{2} [0-9]{3} (?:[0-9]+(?:ST|ND|RD|TH)|[A-Z]+) ",
        "S",
        3,
    ),
    (
        "bare-unit-number-after-house-number",
        "502",
        "a bare number between the house number and an ordinal street",
        r"^([0-9]+) (?!\1 )[0-9]{1,4} [0-9]+(?:ST|ND|RD|TH) ",
        "S",
        1,
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
        "paren-group-at-edge",
        "291",
        "a parenthesized group that ends a line or stands alone, not a floor (9 OAK RD (J SMITH), (BOX 14))",
        r"\([^()|]*\)\s*(?:\||$)|^\([^()|]*\)",
        "M",
        1,
    ),
    (
        "unclosed-paren",
        "516",
        "an opening parenthesis with no closing one before the end of the line",
        r"\([^)|]*(?:\||$)",
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
    (
        "unit-repeated-as-hash",
        "499",
        "a unit repeated as # N on line 2",
        r"\b(?:SPC|SP|LOT|TRLR|APT|UNIT|STE|SUITE) ([A-Z0-9-]+)(?:,| \|) ?# ?\1\b",
        "S",
        1,
    ),
    (
        "stray-designator-before-name",
        "498",
        "a unit designator with no value between the house number and the street name",
        rf"^[0-9]+(?:-[0-9]+)? {UN} [A-Z]{{3,}}(?: [A-Z]+)* {SUF}\b",
        "S",
        3,
    ),
    (
        "building-name-after-street",
        "495",
        "a building or complex name (CONDOMINIUMS) after the street",
        r"^[0-9]+ [A-Z0-9 ]+?(?:,| \|) ?(?:[A-Z]+ ){1,4}CONDOMINIUMS?(?:,| \||$)",
        "S",
        1,
    ),
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
        "two-numbers-before-street",
        "544",
        "two numbers before the street (5300 5301 EXAMPLE RD): a house-number range or a leftover",
        rf"^[0-9]{{1,5}}[ ,]+[0-9]{{1,5}} (?:[A-Z0-9]+ ){{0,3}}{SUF}\b",
        "M",
        2,
    ),
    (
        "line2-word-description",
        "545",
        "a building description alone on line 2 (PRIMARY, DUPL)",
        r"\| (?:PRIMARY|DUPL|DUPLEX)$",
        "M",
        1,
    ),
    (
        "line2-word-position",
        "545",
        "a position word alone on line 2 (LEFT, RIGHT, SECONDARY, UPPER, LOWER, FRONT, BACK)",
        r"\| (?:LEFT|RIGHT|SECONDARY|UPPER|LOWER|FRONT|BACK|TOP|BOTTOM|MIDDLE|EAST|WEST|NORTH|SOUTH)$",
        "M",
        1,
    ),
    (
        "line2-word-other",
        "545",
        "any other single word alone on line 2 (the flagged ones are the question)",
        r"\| (?!(?:PRIMARY|DUPL|DUPLEX|LEFT|RIGHT|SECONDARY|UPPER|LOWER|FRONT|BACK|TOP|BOTTOM|MIDDLE|EAST|WEST|NORTH|SOUTH|REAR|BASEMENT|LOBBY|OFFICE|PENTHOUSE|SIDE|LOWR|UPPR)$)[A-Z]{3,12}$",
        "M",
        1,
    ),
    (
        "unit-then-stray-word-line2",
        "558",
        "a unit ending line 1 and one unknown word on line 2 (STE 710 over AMI)",
        r"^[0-9]+ .*\b(?:STE|SUITE|APT|UNIT|BLDG|FL|RM) [0-9A-Z-]+ \| [A-Z]{3,12}$",
        "S",
        3,
    ),
    (
        "spelled-unit-line2",
        "559",
        "a spelled-out number alone on line 2 (ONE, THREE)",
        r"\| (?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE)$",
        "S",
        2,
    ),
    (
        "thousands-comma-number",
        "560",
        "a house number with a thousands comma (20,000 EXAMPLE ROAD)",
        r"^[0-9]{1,3},[0-9]{3} [A-Z]",
        "S",
        3,
    ),
    (
        "nyc-city-repeat",
        "553",
        "a place or neighborhood plus a repeated NEW YORK / NY before the ZIP (BRONX, NEW YORK, NY 10451; MURRAY HILL NY NY 10016)",
        r"\b(?:BRONX|BROOKLYN|QUEENS|MANHATTAN|STATEN ISLAND|HARLEM|MURRAY HILL|CHELSEA|SOHO|TRIBECA|MIDTOWN)[ ,]+(?:NEW YORK|NY)[ ,]+(?:NEW YORK|NY)[ ,]+(?:1[01][0-9]{3})\b",
        "S",
        1,
    ),
    (
        "zip-plus4-letters",
        "541",
        "a ZIP+4 whose last part has letters (CA 90001-12AB)",
        r"\b[A-Z]{2},? [0-9]{5}-[0-9]{0,3}[A-Z][A-Z0-9]*(?: \||$)",
        "S",
        3,
    ),
    (
        "number-before-road-type",
        "542",
        "a road number written before the road type (331 5659 PRIVATE ROAD, 2210 3315 FM RD)",
        r"^[0-9]+ [0-9]{1,5} (?:PRIVATE|COUNTY|STATE|FARM TO MARKET|FM|PR) (?:ROAD|RD)\b",
        "M",
        3,
    ),
    (
        "united-states-highway",
        "543",
        "UNITED STATES HIGHWAY n spelled out (4212 S UNITED STATES HIGHWAY 27)",
        r"\bUNITED STATES (?:HIGHWAY|HWY) [0-9]",
        "S",
        3,
    ),
    (
        "star-route",
        "538",
        "a Star Route (STAR RT BOX 12, STAR ROUTE 2) read as a street and a unit",
        r"\bSTAR (?:RT|RTE|ROUTE)\b\.?",
        "S",
        2,
    ),
    (
        "zip-plus4-with-space",
        "519",
        "a ZIP+4 written with a space (TOWN FL 33000 1234)",
        r"\b[A-Z]{2},? [0-9]{5} [0-9]{4}(?: \||$)",
        "S",
        2,
    ),
    (
        "unit-before-street-residual",
        "529",
        "a designator and its value between the house number and the street name (242 APT B ESPLANADE, 2900 APT S OLD 63)",
        rf"^[0-9]+ {UN} (?:[A-Z]|[0-9]+[A-Z]?|[A-Z][0-9]+) [A-Z]{{3,}}",
        "M",
        3,
    ),
    (
        "digit-word-line2-highway",
        "531",
        "a number and a word on line 2 under a highway or route (1 STORY under STATE ROUTE 144 WEST)",
        r"^[0-9]+ [^|]*\b(?:HWY|HIGHWAY|ROUTE|RTE|STATE ROAD|COUNTY ROAD|CO RD|SR|CR|FM|RR|US|IH) [^|]*\| [0-9]{1,4} [A-Z]{3,12}$",
        "S",
        2,
    ),
    (
        "digit-word-line2-nosuffix",
        "531",
        "a number and a word on line 2 under a street with no suffix word (S 100 W, AVENUE 9 EAST, AIRPORT)",
        rf"^[0-9]+ (?:[^|]*? )?(?:[0-9/]+|(?!(?:{SUF}|ST|TER|TERR|PKY|EXPY|PLZ|SQ|LOOP|RUN|PATH|ROW|BND|(?:N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST))\b)[A-Z]+)(?: (?:N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST))? \| [0-9]{{1,4}} [A-Z]{{3,12}}$",
        "S",
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
    (
        "campus-box-two-words",
        "384",
        "a campus box with two plain words before BOX (ELM HALL BOX 3310)",
        r"^[A-Z]{2,} [A-Z]{2,} BOX [0-9]+",
        "S",
        2,
    ),
    (
        "half-before-lone-letter",
        "387",
        "a half written without its slash before a lone letter (10 1 2 N MAIN ST)",
        r"^[0-9]+ (?:[0-9]+ )?(?:1 2|1 4|3 4) [A-Z] ",
        "S",
        2,
    ),
    (
        "compass-ky-tr-number",
        "388",
        "a compass word, KY or TR and a number (1234 EAST TR 56)",
        r"^[0-9]+ (?:NORTH|SOUTH|EAST|WEST) (?:KY|TR) [0-9]+",
        "S",
        3,
    ),
    # Needs a repeat of the state and ZIP (a back-reference), so no pattern: see csz_twice().
    ("city-state-zip-twice", "397", "the state and ZIP written twice in the text (12 OAK ST SPRINGFIELD IL 62704 SPRINGFIELD IL 62704)", None, "M", 2),
    # Fields and last-line words (hits(): zip, city and state), so no single pattern.
    ("null-word-field", "419", "NaN, null, none or undefined as the city, state or ZIP, or as a word of the text", None, "M", 2),
    ("repeated-state-or-county", "435", "a state written twice, USA before the ZIP, or a county segment", None, "M", 2),
    (
        "letter-and-initials",
        "466",
        "a lone letter A to D followed by AND (120 A AND M LN)",
        r"^[0-9]+ [A-D] AND ",
        "S",
        3,
    ),
    (
        "letter-then-direction",
        "467",
        "a lone letter A to D followed by a direction word (301 A S MAIN ST)",
        r"^[0-9]+ [A-D] (?:N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST) ",
        "S",
        1,
    ),
    ("city-placeholder", "468", "a placeholder in the city field (NOT STATED, UNKNOWN)", None, "S", 1),
    (
        "non-latin-text",
        "469",
        "a run of non-Latin script (Cyrillic, Greek, Arabic, Hebrew, Indic, Kana, Han or Hangul) in the address",
        r"[\u0370-\u03ff\u0400-\u052f\u0590-\u06ff\u0900-\u097f\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]",
        "M",
        2,
    ),
    (
        "no-for-north",
        "470",
        "NO for north before a street name (464 NO MAPLE AVE)",
        r"^[0-9]+(?: [0-9]/[0-9])? NO (?![0-9])[A-Z]",
        "S",
        3,
    ),
    (
        "unit-marker-after-suffix",
        "471",
        "BX, SP, SPC, FL or ST and a number after a street suffix, or a SUITE with a letter-hyphen-number",
        rf"^[0-9]+ [A-Z0-9 ]+ {SUF} (?:(?:BX|SPC?|FL|ST) [A-Z]?[0-9]+[A-Z]?|(?:SUITE|STE) [A-Z]-[0-9]+[A-Z]?)(?: \||$)",
        "M",
        3,
    ),
    (
        "name-or-business-line2",
        "472",
        "a street on line 1 and DBA, C O, ATTN or a name ending in DDS, MD, ESQ, LLC or INC on line 2",
        rf"^[0-9]+ [A-Z0-9 ]+ {SUF}\b[^|]*\| (?:(?:DBA|C O|C/O|ATTN:?) |[A-Z .'-]+ (?:DDS|DMD|DVM|MD|ESQ|CPA|LLC|INC)\b)",
        "M",
        2,
    ),
    (
        "co-name-street-one-line",
        "473",
        "C/O, a name and then a house number and street on line 1 (C/O JANE DOE 1504 EAST M)",
        r"^(?:C/O|C O) [^|0-9]+ [0-9]+ [A-Z0-9 ]+(?: \||$)",
        "S",
        3,
    ),
    (
        "careof-name-only",
        "509",
        "a care-of or attention line with a name and no street (C/O ACME TIRE)",
        r"^(?:C/O|C O|ATTN:?) [A-Z &.'-]+ \| ?$",
        "D",
        1,
    ),
    (
        "state-word-city-no-state",
        "480",
        "a city that starts with a state name or LA, with no state, and a ZIP (VIRGINIA BEACH 23451, LA MESA 91941)",
        rf"(?:^|[ ,|]){STATE_FIRST} [A-Z]{{3,}}(?: [A-Z]+)?,? [0-9]{{5}}(?:-[0-9]{{4}})?(?: \||$)",
        "S",
        3,
    ),
    (
        "region-phrase-as-state",
        "482",
        "a compass word and a state's name, no state code, then a ZIP (TRENT, WEST TEXAS 79561)",
        rf"(?:^|[ ,|])(?:WEST|EAST|NORTH|SOUTH|CENTRAL|NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST) (?!VIRGINIA\b){STATE_FIRST},? [0-9]{{5}}(?:-[0-9]{{4}})?(?: \||$)",
        "S",
        2,
    ),
    (
        "successors-assigns-line1",
        "483",
        "SUCCESSORS AND/OR ASSIGNS written in the address (ITS SUCCESSORS ANDOR ASSIGNS before the street)",
        r"\bSUCCESSORS (?:AND/OR |ANDOR |AND |OR )?ASS",
        "S",
        2,
    ),
    (
        "letter-after-number",
        "487",
        "a letter A to D after a plain house number and before a name (123 B MAIN ST), read as the number's suffix",
        rf"^[0-9]+ [A-D] (?![A-Z]\b)[A-Z]{{3,}}[A-Z ]* {SUF}\b",
        "M",
        2,
    ),
    # Needs the city field (hits(): city and state), so no pattern.
    ("city-is-state", "357", "the city field holds the state and the real city is on line 2", None, "S", 3),
    ("unit-or-box-in-city", "244", "a unit or a box in the city field", None, "S", 2),
    # R8 of #586 (decided in R7): one probe per rule or shape. Counts over the records files; key-affecting ones are k5.
    ("route-letter-road", "589", "a lettered county or state route road after a street (STATE RD QQ)", r"\b(?:COUNTY|STATE|CTY|ST) (?:ROAD|RD) [A-Z]{2,3}\b", "S", 3),
    ("ocean-gulf-name", "589", "a street name that ends in OCEAN or GULF (12 5TH ST OCEAN)", rf"^[0-9]+ .*\b{SUF} (?:OCEAN|GULF)\b", "S", 3),
    ("suffix-building-unit", "589", "a building or unit word after a street suffix (PKWY LWR, AVE BLDG)", rf"\b{SUF} (?:LWR|UPR|BLDG|BUILDING)\b", "S", 2),
    ("range-second-number", "590", "a second number 1 to 20 above the first, with the same parity (read as a unit); hits()", None, "M", 3),
    ("five-digit-join", "591", "two digits plus three digits outside NYC, Hawaii and Massachusetts (one five-digit number); hits()", None, "M", 3),
    ("line2-digit-run", "592", "line 2 is only a run of one digit, seven or more long", r"\|\s*(?:0{7,}|1{7,}|2{7,}|3{7,}|4{7,}|5{7,}|6{7,}|7{7,}|8{7,}|9{7,})\b", "S", 1),
    ("name-road-number-unit", "593", "a road word and a number after a name, read as a unit (HOLLOW ROAD 412)", r"\b[A-Z]+ ROAD [0-9]+\b", "M", 3),
    ("letter-street-two-suffix", "594", "a one-letter street before its own suffix (9 C ST RD)", rf"^[0-9]+ [A-Z] {SUF} {SUF}\b", "S", 2),
    ("old-digit-letter", "595", "OLD and a digit-letter after it (18 OLD 25A)", r"\bOLD [0-9]+[A-Z]\b", "S", 2),
    ("po-drawer-letter", "598", "a lettered PO drawer (PO DRAWER C)", r"\bDRAWER [A-Z]\b", "S", 2),
    ("zip4-star", "599", "a ZIP+4 written with a star (75000*1234)", r"\b[0-9]{5}\*[0-9]{0,4}\b", "S", 2),
    ("road-letter", "600", "ROAD followed by one letter before the city (ROAD B, ELMTOWN)", r"\bROAD [A-Z]\b", "S", 2),
    ("spelled-number-commas", "601", "a line that starts with a spelled number and has a comma", r"^(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|TWELVE|TWENTY|THIRTY|FORTY|FIFTY|HUNDRED|THOUSAND)\b[A-Z ]*,", "S", 2),
    ("hash-apt-after-street", "602", "# APT written after the street", rf"\b{SUF} # ?APT\b", "S", 1),
    # #586 B2: one probe per rule issue filed from the NAD leftover shapes.
    ("zip-zero", "605", "a ZIP field of only zeros, shorter than five digits (0, 0000); hits()", None, "S", 1),
    ("zip-cut-no-hyphen", "606", "a ZIP field of seven or eight digits: a ZIP+4 cut short with no hyphen (7500112); hits()", None, "S", 3),
    (
        "number-before-designator-line2",
        "607",
        "line 2 is a bare number before a designated unit (5 APT 12, 3 # 305: NAD's floor or building)",
        r"\| [0-9]+[A-Z]? (?:APT|APARTMENT|UNIT|STE|SUITE|#|RM|ROOM|LOT|TRLR|SPC) ?[0-9A-Z][0-9A-Z-]*$",
        "M",
        2,
    ),
    (
        "united-states-highway-gap",
        "608",
        "UNITED STATES HIGHWAY after a word that is not a direction (OLD), or with a route pair (41-45, 41/45)",
        (
            r"\b(?!(?:N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST|NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST)\b)[A-Z]+ UNITED STATES (?:HIGHWAY|HWY) [0-9]"
            r"|\bUNITED STATES (?:HIGHWAY|HWY) [0-9]+[-/][0-9]"
        ),
        "S",
        3,
    ),
    # #586 B3: the hyphen beside the second number after the house number (#584 closed into #612).
    (
        "hyphen-before-second-number",
        "612",
        "a hyphen with a space beside it between the house number and a second number (1900 -938 ST, 1900 - 938 ST, 1900- 938 ST)",
        r"^[0-9]+[A-Z]? +- ?[0-9]+[A-Z]?(?: |$)|^[0-9]+[A-Z]? +-[0-9]+[A-Z]?(?: |$)|^[0-9]+- +[0-9]+[A-Z]?(?: |$)",
        "M",
        2,
    ),
    # #586 B4: the last line inside line 1 (#585 closed into #614); a field probe in hits().
    ("last-line-in-line1", "614", "line 1 ends with the row's own state and a five-digit ZIP (214 N PARK AVE OAKLAND NE 68045); hits()", None, "M", 3),
]
# Open rule issues that have no probe, and why. Every other open issue with the label `area:rules` has a probe in PROBES; the
# issues about docs, tooling, the API or the architecture, and the trackers, are not text shapes and need none.
NO_PROBE = {
    11: "research: which state data to add; no text shape, a gap in the tables",
    92: "research: the uncited parts of Pub 28; reading work, not a shape",
    213: "research: whether more state data is needed; measured by the label comparisons, not a text shape",
    238: "a family of unit misses in NAD, split into #320 and #321, which have probes",
    345: "research: a bare number after a street is a unit in some sources and a name in others; no text shape tells them apart",
    534: "research: the line-2 rules do not run on a comma-separated segment of a one-line string; measured on labeled one-line corpora (2 of 1,702 strings), not a text shape of the scan's field-form rows",
    549: "a suffix-word street name with a direction (55 BOULEVARD EAST): counted by the USPS round-trip scan (shape_scan.py --mode roundtrip), not a scan text shape",
    550: "the same unit written on both lines: counted by the USPS round-trip scan (shape_scan.py --mode roundtrip); the shape needs both lines compared, not one pattern",
    486: "a curated list of neighborhood city names: counted by city values in the sources (#485), not a text shape",
    410: "research: naming the known-word chains and where the tokenizer and tagger differ; a reading task, not a shape",
    596: "one-line input (a pre-direction, a suffix-word name, an unlisted city): sized on one-line data by tools/compare/oneline_fl.py, not a field-form text shape (#586 R7 row 11)",
    597: "one-line input (a listed city ending in a suffix word, no comma before it): sized on one-line data, not a field-form text shape (#586 R7 row 11)",
    583: "a before and after count of the warnings PR 494 changed, by code (#586 B1); not a text shape",
    578: "a convention question, not a text shape: the letter after a house number is documented in docs/usaddress-compat.md and docs/benchmarks.md (#586 R8, #603)",
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


STATE_ABBR = dict(
    zip(
        ["ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO", "CONNECTICUT", "DELAWARE", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO", "ILLINOIS", "INDIANA", "IOWA", "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN", "MINNESOTA", "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA", "NEW HAMPSHIRE", "NEW JERSEY", "NEW MEXICO", "NEW YORK", "NORTH CAROLINA", "NORTH DAKOTA", "OHIO", "OKLAHOMA", "OREGON", "PENNSYLVANIA", "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA", "TENNESSEE", "TEXAS", "UTAH", "VERMONT", "VIRGINIA", "WASHINGTON", "WEST VIRGINIA", "WISCONSIN", "WYOMING"],
        ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"],
    )
)
STATE_NAMES = "|".join(sorted(STATE_ABBR, key=len, reverse=True))
NAME_AND_ABBR = re.compile(rf"\b({STATE_NAMES}),? ([A-Z]{{2}}),? [0-9]{{5}}\b|\b([A-Z]{{2}}),? ({STATE_NAMES}),? [0-9]{{5}}\b")
NULL_WORDS = {"NAN", "NULL", "NONE", "UNDEFINED", "N/A"}
NULL_TEXT = re.compile(r"\b(?:NAN|NULL|UNDEFINED)\b")
CSZ = re.compile(r"\b([A-Z]{2}),? ([0-9]{5})\b")
REPEATED_STATE = re.compile(
    r"\b([A-Z]{2}),? \1,? [0-9]{5}\b"
    r"|\b[A-Z]{2},? (?:USA|US|UNITED STATES(?: OF AMERICA)?),? [0-9]{5}\b"
    r"|, [A-Z .'-]+ COUNTY(?:,| \||$)"
)
CITY_PLACEHOLDER = {"NOT STATED", "UNKNOWN"}
NYC_REPEAT = re.compile(r"^(?!NEW YORK$)(?!NEW YORK CITY$)(.+?)[ ,]+(?:NEW YORK CITY|NEW YORK,? NY|NEW YORK|NY,? NY|NY)$")
ZIP_LETTERS = re.compile(r"^[0-9]{5}-[0-9]{0,3}[A-Z][A-Z0-9]*$")


def state_name_repeated(t):
    """A state name next to its own abbreviation before the ZIP (`ILLINOIS IL 62704`, #435). `NEW YORK NY` is a city and its state."""
    for m in NAME_AND_ABBR.finditer(t):
        name, ab = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        if STATE_ABBR[name] == ab and name != "NEW YORK":
            return True
    return False


def csz_twice(t):
    """The same state and ZIP written twice in the text (`SPRINGFIELD IL 62704 SPRINGFIELD IL 62704`, #397)."""
    found = CSZ.findall(t)
    return len(found) != len(set(found))


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
    if csz_twice(t):
        out.append("city-state-zip-twice")
    # A null-like word as the city, state or ZIP field, or as a word of the text (#419).
    fields = {c, (str(state) if state else "").upper().strip(), (str(zip_code) if zip_code else "").upper().strip()}
    if (fields & NULL_WORDS) or NULL_TEXT.search(t):
        out.append("null-word-field")
    if REPEATED_STATE.search(t) or state_name_repeated(t):
        out.append("repeated-state-or-county")
    # A ZIP field with a ZIP+4 that has letters (#541; Netsyms writes some as 93313-97ND).
    if zip_code and ZIP_LETTERS.match(str(zip_code).upper().strip()):
        out.append("zip-plus4-letters")
    # A place name plus a repeated NEW YORK or NY in the city field of a New York City ZIP (#553).
    if state and str(state).upper().strip() in ("NY", "NEW YORK") and zip_code and NYC_REPEAT.match(c) and re.match(r"^(10[0-4]|11[0-4]|116)", str(zip_code)):
        out.append("nyc-city-repeat")
    # A placeholder city (#468).
    if c in CITY_PLACEHOLDER:
        out.append("city-placeholder")
    z = (str(zip_code) if zip_code else "").strip()
    # A ZIP field of only zeros, shorter than five digits: NAD's stand-in for no ZIP (#605).
    if re.fullmatch(r"0{1,4}", z):
        out.append("zip-zero")
    # A ZIP+4 cut short with no hyphen: seven or eight digits (#606).
    if re.fullmatch(r"[0-9]{7,8}", z):
        out.append("zip-cut-no-hyphen")
    # The street line written twice (#236).
    if repeated_line(line1):
        out.append("repeated-line")
    # PO BOX on line 2 whose number is the ZIP.
    m = re.match(rf"^{BOX} ([0-9]{{5}})$", (line2 or "").upper().strip())
    if m and zip_code and m.group(1) == str(zip_code)[:5]:
        out.append("po-box-equals-zip")
    # Line 1 ends with the row's own state and a five-digit ZIP: the last line is inside line 1 (#614, from #585).
    m = re.search(r" ([A-Z]{2}) [0-9]{5}$", (line1 or "").upper().strip())
    if m and state and m.group(1) == str(state).upper().strip() and re.match(r"^[0-9]+ [A-Z0-9]", (line1 or "").upper().strip()):
        out.append("last-line-in-line1")
    # A second number 1 to 20 above the first, with the same parity, is a range (#563, #523; the R8 probe range-second-number).
    m = re.match(r"^([0-9]+) ([0-9]+) [A-Z]", (line1 or "").upper().strip())
    if m and 2 <= int(m.group(2)) - int(m.group(1)) <= 20 and (int(m.group(2)) - int(m.group(1))) % 2 == 0:
        out.append("range-second-number")
    # Two digits plus three digits, outside NYC, Hawaii and Massachusetts (#523, the R8 probe five-digit-join).
    m = re.match(r"^[0-9]{2} [0-9]{3} [A-Z]", (line1 or "").upper().strip())
    if m and str(state or "").upper().strip() not in ("NY", "NEW YORK", "HI", "HAWAII", "MA", "MASSACHUSETTS"):
        out.append("five-digit-join")
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
