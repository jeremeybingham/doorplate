"""Tests for tools/harness/probes.py on invented rows (no private data).

pytest tools/harness
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probes


def test_keys_are_unique_and_every_pattern_compiles():
    keys = [p[0] for p in probes.PROBES]
    assert len(keys) == len(set(keys))
    assert set(probes.regexes()) == {p[0] for p in probes.PROBES if p[3]}
    for key, issue, name, rx, size, harm in probes.PROBES:
        assert size in probes.EFFORT and harm in (1, 2, 3) and issue and name


@pytest.mark.parametrize(
    "line1, line2, zip_code, expect",
    [
        ("640 PINEWOOD BOX 18", None, None, "box-after-street"),
        ("BOX 3310 FERNLEAF RD", None, None, "box-first"),
        ("PO BOX 12", "ELDER RD.", None, "box-line1-street-line2"),
        ("POBOX481", None, None, "glued-box-route"),
        ("PO 5530", None, None, "po-no-box"),
        ("RUR RTE 3 BOX 84", None, None, "rur-rte-hrc"),
        ("7410 NW 52ND ST - 2210", None, None, "hyphen-after-suffix"),
        ("N45 W2210 OAK AVE", None, None, "grid-number"),
        ("W 4502 MILL RD", None, None, "letter-before-number"),
        ("31 14 90TH AVE", None, None, "queens-space"),
        ("6449 PR 462", None, None, "tx-pr-fm"),
        ("2210 3315 FM RD", None, None, "fm-before-type"),
        ("HWY 77 AND LOOP 410", None, None, "and-between-highways"),
        ("66 ELM ST", "SUITE LA", None, "unit-is-suffix-code"),
        ("3 & 5 E 41ST ST", None, None, "ampersand-numbers"),
        ("40 ELM ST SUT 300", None, None, "sut-stu"),
        ("12 ELM ST SIUTE 4", None, None, "sut-stu"),
        ("60 LARKMOOR W 1A", None, None, "no-suffix-then-bare-unit"),
        ("330 HARBORGATE 7", None, None, "no-suffix-then-bare-unit"),
        ("53A-53 HOLLIS AVE", None, None, "letter-before-hyphen"),
        ("40 HARBOR FISH PIER", None, None, "pier-last-word"),
        ("PIER 4 EIGHTH ST", None, None, "pier-last-word"),
        ("ONE MARLOW PLAZA - 99 ELM AVE.", "SUITE 8", None, "spaced-hyphen-building"),
        ("1921 NW", "4 REAR", None, "bare-unit-line2"),
        ("77 OAK ST", "B12", None, "bare-unit-line2"),
        ("100 EXAMPLE ST, SPRINGTOWN, CA 90001-12AB", None, None, "zip-plus4-letters"),
        ("331 5659 PRIVATE ROAD", None, None, "number-before-road-type"),
        ("2210 3315 FM RD", None, None, "number-before-road-type"),
        ("4212 S UNITED STATES HIGHWAY 27", None, None, "united-states-highway"),
        ("5300 5301 EXAMPLE RD", None, None, "two-numbers-before-street"),
        ("1865,1867 E THIESEN RD", None, None, "two-numbers-before-street"),
        ("816 SLADE ST", "PRIMARY", None, "line2-word-description"),
        ("816 SLADE ST", "LEFT", None, "line2-word-position"),
        ("816 SLADE ST", "GREENHOUSES", None, "line2-word-other"),
        ("100 EXAMPLE AVE, BRONX, NEW YORK, NY 10451", None, None, "nyc-city-repeat"),
        ("100 EXAMPLE ST, MURRAY HILL NY NY 10016", None, None, "nyc-city-repeat"),
        ("3100 EXAMPLE DR STE 710", "AMI", None, "unit-then-stray-word-line2"),
        ("212 W EXAMPLE ST", "ONE", None, "spelled-unit-line2"),
        ("20,000 EXAMPLE ROAD", None, None, "thousands-comma-number"),
        ("STAR RT BOX 12", None, None, "star-route"),
        ("STAR ROUTE 2 BOX 45", None, None, "star-route"),
        ("100 EXAMPLE ST, TOWN FL 33000 1234", None, None, "zip-plus4-with-space"),
        ("242 APT B ESPLANADE", None, None, "unit-before-street-residual"),
        ("2900 APT S OLD 63", "2 8-203", None, "unit-before-street-residual"),
        ("2652 US HIGHWAY 60 W", "1 STORY", None, "digit-word-line2-highway"),
        ("1990 STATE ROUTE 144 WEST", "1 STORY", None, "digit-word-line2-highway"),
        ("1780 S 100 W", "4 BARNS", None, "digit-word-line2-nosuffix"),
        ("11322 S AVE 12 E", "124 SECONDARY", None, "digit-word-line2-nosuffix"),
        ("782 AIRPORT", "1 DOCTOR", None, "digit-word-line2-nosuffix"),
        ("77 OAK ST COND 12", None, None, "unlisted-unit-words"),
        ("77 OAK ST", "UNIT NORTH", None, "unlisted-unit-words"),
        ("1234 LEE ROAD 2004", None, None, "name-road-number"),
        ("410 ELM ST # APT-4", None, None, "hash-before-designator"),
        ("410 ELM ST", "#APT-18", None, "hash-before-designator"),
        ("410 ELM ST # APT 4", None, None, "hash-before-designator"),
        ("120 NW 14 ST SUITE 2&3", None, None, "units-ampersand"),
        ("12 ELM ST (3RD FL)", None, None, "floor-in-parentheses"),
        ("100 OAK ST", "5 123", None, "unit-two-parts"),
        ("12-40 SUITE 9 DELMAR BLVD", None, None, "unit-before-street"),
        ("NO ADDRESS ON FILE", None, None, "placeholder"),
        ("100 OAK ST", "PO BOX 33101", "33101-1234", "po-box-equals-zip"),
        ("ONE MARLOW TOWER", None, None, "spelled-number"),
        ("77 B BEAL RD", None, None, "single-letter-name-initial"),
        ("9311 J W CLAY BLVD", None, None, "single-letter-name-initial"),
        ("146 VEGA LOOP #LN", None, None, "unit-copies-street-word"),
        ("US HWY 13 N # NORTH", None, None, "unit-copies-street-word"),
        ("12 ORANGE ST # 1/2", None, None, "unit-copies-street-word"),
        ("HUB WORKS 2ND FL", "300 ELM CT", None, "name-and-floor-line1"),
        ("100 OAK ST", "PO BOX NA", None, "po-box-placeholder-line2"),
        ("100 OAK ST", "P O BOX", None, "po-box-placeholder-line2"),
        ("P O BOX 2856 MEADOW RD", None, None, "box-then-street-words"),
        ("CO HARBOR 2100 OAK ST 16", "% HARBOR HOLDINGS LLP", None, "co-prefix-fuller-name-line2"),
        ("1900 OAK AVE MSC 518", None, None, "word-number-after-suffix"),
        ("5500 WABASH AVE RHIT BOX 507", None, None, "word-number-after-suffix"),
        ("31 1 2 ELM PLACE", None, None, "half-without-slash"),
        ("123 ELM CIR, ELM CREEK CONDOMINIUMS", None, None, "building-name-after-street"),
        ("4704 APT CLARK LN", "1 100", None, "stray-designator-before-name"),
        ("4390 PATTERSON DR SPC 249", "# 249", None, "unit-repeated-as-hash"),
        ("12 345 ELM ST", None, None, "space-split-long-number"),
        ("C/O ACME TIRE", None, None, "careof-name-only"),
        ("C O ACME CORP", None, None, "careof-name-only"),
        ("123 104 11TH STREET", None, None, "bare-unit-number-after-house-number"),
        ("123 OAK ST", "OAK VALLEY VI CONDOMINIUMS", None, "building-name-after-street"),
    ],
)
def test_each_shape_is_found(line1, line2, zip_code, expect):
    assert expect in probes.hits(line1, line2, zip_code)


def test_the_digit_word_line2_probes_leave_a_street_with_a_suffix_alone():
    for line1, line2 in [("816 SLADE ST", "3 RIGHT"), ("1700 OAK PKWY", "12 STORY"), ("123 OAK ST E", "40 SECONDARY")]:
        hits = probes.hits(line1, line2, None)
        assert "digit-word-line2-nosuffix" not in hits and "digit-word-line2-highway" not in hits
    assert "digit-word-line2-nosuffix" not in probes.hits("2652 US HIGHWAY 60 W", "ROOM 4", None)


def test_the_541_to_543_probes_leave_ordinary_rows_alone():
    assert "number-before-road-type" not in probes.hits("331 PRIVATE ROAD 5659", None, None)
    assert "number-before-road-type" not in probes.hits("331 OAK ROAD", None, None)
    assert "united-states-highway" not in probes.hits("UNITED STATES POSTAL SERVICE", None, None)
    assert "zip-plus4-letters" not in probes.hits("100 OAK ST", None, "90001-1234", "SPRINGTOWN", "CA")
    assert "zip-plus4-letters" in probes.hits("100 OAK ST", None, "93313-97ND", "BAKERSFIELD", "CA")


def test_line2_word_probes_keep_to_their_group():
    assert "line2-word-other" not in probes.hits("816 SLADE ST", "PRIMARY", None)
    assert "line2-word-other" not in probes.hits("816 SLADE ST", "LEFT", None)
    assert "line2-word-other" not in probes.hits("816 SLADE ST", "REAR", None)
    assert "line2-word-other" not in probes.hits("816 SLADE ST", "APT 4", None)
    assert "two-numbers-before-street" not in probes.hits("816 SLADE ST", None, None)


def test_nyc_city_repeat_needs_a_place_name_and_a_new_york_zip():
    assert "nyc-city-repeat" not in probes.hits("100 EXAMPLE AVE", None, "10451", "NEW YORK", "NY")
    assert "nyc-city-repeat" not in probes.hits("100 EXAMPLE AVE", None, "10451", "BRONX", "NY")
    assert "nyc-city-repeat" in probes.hits("100 EXAMPLE AVE", None, "10451", "BRONX, NEW YORK", "NY")
    assert "nyc-city-repeat" not in probes.hits("100 EXAMPLE AVE", None, "90001", "BRONX, NEW YORK", "CA")


def test_558_to_560_probes_leave_ordinary_rows_alone():
    assert "unit-then-stray-word-line2" not in probes.hits("3100 EXAMPLE DR STE 710", None, None)
    assert "unit-then-stray-word-line2" not in probes.hits("3100 EXAMPLE DR", "STE 710", None)
    assert "spelled-unit-line2" not in probes.hits("212 W EXAMPLE ST", "SUITE ONE", None)
    assert "thousands-comma-number" not in probes.hits("6204,1730 EXAMPLE AVE PKWY", None, None)
    assert "thousands-comma-number" not in probes.hits("12 OAK ST, SPRINGTOWN", None, None)


def test_star_route_leaves_star_roads_alone():
    assert "star-route" not in probes.hits("100 FIVE STAR RD", None, None)
    assert "star-route" not in probes.hits("100 STAR ROAD", None, None)


def test_the_city_field_probes_need_the_city_and_state():
    assert "city-is-state" in probes.hits("100 OAK ST", "BRONX", "10451", "NY", "NY")
    assert "city-is-state" not in probes.hits("100 OAK ST", "BRONX", "10451", "BRONX", "NY")
    assert "city-is-state" not in probes.hits("100 OAK ST", "SUITE 4", "10451", "NY", "NY")
    assert "city-is-state" not in probes.hits("100 OAK ST", "BRONX", "10451")
    assert "unit-or-box-in-city" in probes.hits("88 FERN ST", None, "27713", "APT C", "NC")
    assert "unit-or-box-in-city" in probes.hits("500 E MILL BLVD", None, "27713", "BOX 1204", "NC")
    assert "unit-or-box-in-city" not in probes.hits("88 FERN ST", None, "27713", "DURHAM", "NC")


def test_the_new_probes_leave_ordinary_addresses_alone():
    for line1, line2 in [
        ("123 N MAIN ST", None),
        ("77 OAK ST APT 4", None),
        ("1900 OAK AVE SUITE 518", None),
        ("100 OAK ST", "PO BOX 12"),
        ("PO BOX 2856", None),
        ("12 1/2 ELM ST", None),
        ("146 VEGA LOOP APT 4", None),
        ("123 ELM CIR", "UNIT 4"),
        ("CONDOMINIUMS OF ELM CREEK", None),
        ("4390 PATTERSON DR SPC 249", "# 250"),
        ("300 300 5TH AVE", None),
        ("C/O ACME TIRE", "100 ELM ST"),
        ("C/O ACME TIRE 100 ELM ST", None),
        ("12345 ELM ST", None),
    ]:
        got = set(probes.hits(line1, line2, None)) & {
            "single-letter-name-initial", "unit-copies-street-word", "po-box-placeholder-line2",
            "box-then-street-words", "word-number-after-suffix", "half-without-slash", "name-and-floor-line1",
            "building-name-after-street", "stray-designator-before-name", "unit-repeated-as-hash",
            "space-split-long-number",
            "bare-unit-number-after-house-number", "careof-name-only",
        }
        assert not got, (line1, line2, got)


def test_an_ordinary_address_hits_nothing():
    assert probes.hits("812 ASHGROVE ST", "SUITE 4", "33101") == []
    assert probes.hits("123 MAIN ST", None, None) == []


def test_flagged_and_score():
    assert probes.is_flagged(["unparsed_remainder"], "k4:S|1||A|ST||FL|33101")
    assert probes.is_flagged([], "k4n:S|1||A|ST|||")
    assert not probes.is_flagged(["dual_address"], "k4:S|1||A|ST||FL|33101")
    assert probes.score(100, 3, "S") == 300
    assert probes.score(100, 3, "M", precision=0.5) == 75


def test_the_runner_counts_matches_and_prints_counts_only(tmp_path, capsys):
    duckdb = pytest.importorskip("duckdb")
    pytest.importorskip("doorplate")
    p = tmp_path / "records.parquet"
    duckdb.sql(
        "copy (select * from (values "
        "('s','a','1','640 PINEWOOD BOX 18',NULL,'MIAMI','FL','33101'),"
        "('s','a','2','812 ASHGROVE ST',NULL,'MIAMI','FL','33101'),"
        "('s','a','3','40 ELM ST SUT 300',NULL,'MIAMI','FL','33101')) "
        "t(source, role, record_id, line1, line2, city, state, zip)) "
        f"to '{p}' (format parquet)"
    )
    out = tmp_path / "local-data" / "report.json"
    out.parent.mkdir()
    assert probes.main([str(p), "--sample", "1", "--compare", "0", "--out", str(out), "--confirm"]) == 0
    rep = json.loads(out.read_text())
    found = rep["sources"][str(p)]["probes"]
    assert found["box-after-street"]["rows"] == 1 and found["sut-stu"]["rows"] == 1
    assert "PINEWOOD" not in capsys.readouterr().out and "PINEWOOD" not in out.read_text()
    with pytest.raises(SystemExit):
        probes.main(
            [
                str(p),
                "--sample",
                "1",
                "--out",
                str(tmp_path / "elsewhere.json"),
                "--confirm",
            ]
        )


def test_summary_corrects_rows_by_the_excess_disagreement_and_suggests_a_priority():
    report = {
        "sample": 10,
        "sources": {
            "a": {
                "rows_seen": 100000,
                "probes": {
                    "sut-stu": {"rows": 5, "flagged": 1, "partial_key": 0, "compared": 5, "disagree": 4},  # 80%: mostly real
                    "placeholder": {"rows": 50, "flagged": 0, "partial_key": 0, "compared": 50, "disagree": 1},  # 2%: below the baseline
                },
            }
        },
    }
    table, total = probes.summarize(report)
    assert total == 1_000_000
    by = {r["probe"]: r for r in table}
    assert by["sut-stu"]["rows"] == 50 and round(by["sut-stu"]["precision"], 2) == 0.77
    assert by["placeholder"]["precision"] == 0 and by["placeholder"]["priority"] == "P3"
    assert table[0]["probe"] == "sut-stu"


@pytest.mark.parametrize(
    "row, expect",
    [
        ({"line1": "27 CALLE LUNA", "state": "PR", "zip": "00901"}, True),
        ({"line1": "12 OAK ST", "state": "", "zip": "00612"}, True),
        ({"line1": "12 OAK ST URB LAS PALMAS", "state": "", "zip": ""}, True),
        ({"line1": "EDIF 4 APT 2", "state": "", "zip": ""}, True),
        ({"line1": "6449 PR 462", "state": "TX", "zip": "78701"}, False),
        ({"line1": "640 PINEWOOD BOX 18", "state": "IL", "zip": "62701"}, False),
    ],
)
def test_is_puerto_rico(row, expect):
    assert probes.is_puerto_rico(row) is expect


def test_a_hash_before_a_plain_unit_value_is_not_the_340_shape():
    assert "hash-before-designator" not in probes.hits("410 ELM ST #4", None, None)
    assert "hash-before-designator" not in probes.hits("410 ELM ST APT #4", None, None)
    assert "hash-before-designator" not in probes.hits("PO BOX #12", None, None)


def test_the_no_suffix_unit_probe_leaves_streets_with_a_suffix_and_a_unit_on_line_2():
    assert "no-suffix-then-bare-unit" not in probes.hits("60 LARKMOOR W", "1A", None)
    assert "no-suffix-then-bare-unit" not in probes.hits("60 LARKMOOR ST 1A", None, None)
    assert "no-suffix-then-bare-unit" not in probes.hits("12 STATE ROUTE 9", None, None)
    assert "pier-last-word" not in probes.hits("40 PIER ST", None, None)


def test_the_queue_pool_is_a_random_pick_not_the_head_of_the_file(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    pytest.importorskip("doorplate")
    p = tmp_path / "records.parquet"
    values = ",".join(f"('s','a','{i}','640 PINEWOOD BOX {i}',NULL,'MIAMI','FL','33101')" for i in range(1, 401))
    duckdb.sql(
        f"copy (select * from (values {values}) t(source, role, record_id, line1, line2, city, state, zip)) to '{p}' (format parquet)"
    )
    con = duckdb.connect()
    _found, _seen, samples = probes.run_source(p, 1, 7, 0, con, keep=20)
    ids = sorted(int(r["record_id"]) for r in samples["box-after-street"])
    assert len(ids) == 20
    assert ids[-1] > 200  # the first 20 in file order would end at 20
    again = probes.run_source(p, 1, 7, 0, con, keep=20)[2]["box-after-street"]
    assert [r["record_id"] for r in again] == [r["record_id"] for r in samples["box-after-street"]]  # repeatable


def test_a_street_line_written_twice_is_found_and_a_repeated_word_is_not():
    assert "repeated-line" in probes.hits("812 ASHGROVE ST 812 ASHGROVE ST", None)
    assert "repeated-line" in probes.hits("12 ELM ST. 12 ELM ST", None)
    assert "repeated-line" not in probes.hits("812 ASHGROVE ST", None)
    assert "repeated-line" not in probes.hits("100 100 MAIN ST", None)
    assert "repeated-line" not in probes.hits("1 1", None)


def test_a_partial_key_is_recognised_for_any_key_version():
    assert probes.is_partial_key("k4n:S|1||A|ST|||")
    assert probes.is_partial_key("k4n:S|1||A|ST|||")
    assert not probes.is_partial_key("k4:S|1||A|ST||FL|33101")
    assert probes.is_flagged([], "k4n:S|1||A|ST|||")


def test_coverage_names_the_rule_issues_with_no_probe_and_no_reason():
    issues = [
        {"number": 247, "labels": [{"name": "area:rules"}]},       # a probe
        {"number": 345, "labels": [{"name": "area:rules"}]},       # a reason
        {"number": 9999, "labels": [{"name": "area:rules"}]},      # neither
        {"number": 201, "labels": [{"name": "area:rules"}, {"name": "tracker"}]},  # a tracker
        {"number": 233, "labels": [{"name": "area:docs"}]},        # not a text shape
    ]
    covered, excused, missing = probes.coverage(issues)
    assert covered == {247: ["half-without-slash"]}
    assert list(excused) == [345]
    assert missing == [9999]


def test_every_no_probe_reason_is_for_an_issue_without_a_probe():
    with_probe = {int(i) for _k, issue, *_ in probes.PROBES for i in str(issue).split(",") if i.strip().isdigit()}
    assert not set(probes.NO_PROBE) & with_probe


def test_the_box_then_line2_probe_wants_a_street_on_line_2_not_any_words():
    assert "box-line1-street-line2" in probes.hits("PO BOX 123", "45 OAK ST")
    assert "box-line1-street-line2" in probes.hits("PO BOX 123", "OAK ST")
    assert "box-line1-street-line2" not in probes.hits("PO BOX 123", "SPRINGFIELD VALLEY")
    assert "box-line1-street-line2" not in probes.hits("PO BOX 123", "ACME HOLDINGS")


@pytest.mark.parametrize(
    "line1, line2, zip_code, city, state, expect",
    [
        ("ELM HALL BOX 3310", None, None, None, None, "campus-box-two-words"),
        ("10 1 2 N MAIN ST", None, None, None, None, "half-before-lone-letter"),
        ("1234 EAST TR 56", None, None, None, None, "compass-ky-tr-number"),
        ("12 OAK ST SPRINGFIELD IL 62704 SPRINGFIELD IL 62704", None, None, None, None, "city-state-zip-twice"),
        ("12 ELM ST", None, "NaN", "SPRINGFIELD", "IL", "null-word-field"),
        ("12 ELM ST", None, "62704", "NULL", "IL", "null-word-field"),
        ("12 ELM ST, SPRINGFIELD, IL NAN", None, None, None, None, "null-word-field"),
        ("12 ELM ST, SPRINGFIELD, ILLINOIS IL 62704", None, None, None, None, "repeated-state-or-county"),
        ("12 ELM ST, SPRINGFIELD, IL IL 62704", None, None, None, None, "repeated-state-or-county"),
        ("12 ELM ST, SPRINGFIELD, IL USA 62704", None, None, None, None, "repeated-state-or-county"),
        ("12 ELM ST, ORANGE COUNTY, SPRINGFIELD, IL 62704", None, None, None, None, "repeated-state-or-county"),
        ("120 A AND M LN", None, None, None, None, "letter-and-initials"),
        ("301 A S MAIN ST", None, None, None, None, "letter-then-direction"),
        ("12 ELM ST", None, "62704", "NOT STATED", "MA", "city-placeholder"),
        ("3450 NW 91ST AVE, DORAL, Майами, FL 33172", None, None, None, None, "non-latin-text"),
        ("464 NO MAPLE AVE", None, None, None, None, "no-for-north"),
        ("233 OAK AVE BX 5649", None, None, None, None, "unit-marker-after-suffix"),
        ("1725 4TH AVE SUITE I-5B", None, None, None, None, "unit-marker-after-suffix"),
        ("12 ELM ST", "DBA OAKWOOD APTS", None, None, None, "name-or-business-line2"),
        ("12 ELM ST", "JOHN SMITH DDS", None, None, None, "name-or-business-line2"),
        ("C/O JANE DOE 1504 EAST M", None, None, None, None, "co-name-street-one-line"),
        ("12 HARBOR WAY, VIRGINIA BEACH 99999", None, None, None, None, "state-word-city-no-state"),
        ("12 HARBOR WAY, LA MESA 99999-0001", None, None, None, None, "state-word-city-no-state"),
        ("811 COUNTY ROAD 130, TRENT, WEST TEXAS 79561", None, None, None, None, "region-phrase-as-state"),
        ("123 B MAIN ST", None, None, None, None, "letter-after-number"),
        ("45 A OAK HOLLOW AVE", None, None, None, None, "letter-after-number"),
        ("A 708 ITS SUCCESSORS ANDOR ASSIGNS, 123 OAK ST", None, None, None, None, "successors-assigns-line1"),
    ],
)
def test_the_coverage_probes_match_invented_rows(line1, line2, zip_code, city, state, expect):
    assert expect in probes.hits(line1, line2, zip_code, city, state)


@pytest.mark.parametrize(
    "line1, line2, zip_code, city, state",
    [
        ("PO BOX 3310", None, None, None, None),
        ("12 1/2 N MAIN ST", None, None, None, None),
        ("10 1 2 NORTH MAIN ST", None, None, None, None),
        ("1234 EAST ST 56", None, None, None, None),
        ("12 ELM ST, SPRINGFIELD, IL 62704", None, "62704", "SPRINGFIELD", "IL"),
        ("50 OAK ST, NEW YORK, NY 10001", None, "10001", "NEW YORK", "NY"),
        ("12 ELM ST, SPRINGFIELD, IL 62704 USA", None, None, None, None),
        ("45 NO 2 RD", None, None, None, None),
        ("120 A ST", None, None, None, None),
        ("12 ELM ST", "SMITH AND SON REALTY", None, None, None),
        ("12 ELM ST", "SUITE 4", None, None, None),
        ("12 ELM ST", None, "62704", "SPRINGFIELD", "IL"),
        ("5 MUNOZ ST", None, None, None, None),
        ("12 HARBOR WAY, VIRGINIA BEACH, VA 99999", None, None, None, None),
        ("12 HARBOR WAY, SPRINGFIELD, VIRGINIA 99999", None, None, None, None),
        ("12 HARBOR WAY, VIRGINIA BEACH", None, None, None, None),
        ("811 COUNTY ROAD 130, TRENT, WEST VIRGINIA 25301", None, None, None, None),
        ("811 COUNTY ROAD 130, TRENT, TX 79561", None, None, None, None),
        ("12 ELM ST", "SUCCESS PLAZA", None, None, None),
        ("123 A ST", None, None, None, None),
        ("100 J K DAVIS RD", None, None, None, None),
        ("123B MAIN ST", None, None, None, None),
        ("12 E MAIN ST", None, None, None, None),
    ],
)
def test_the_coverage_probes_pass_near_misses(line1, line2, zip_code, city, state):
    new = {
        "campus-box-two-words", "half-before-lone-letter", "compass-ky-tr-number", "city-state-zip-twice", "null-word-field",
        "repeated-state-or-county", "letter-and-initials", "letter-then-direction", "city-placeholder", "non-latin-text",
        "no-for-north", "unit-marker-after-suffix", "name-or-business-line2", "co-name-street-one-line", "state-word-city-no-state", "region-phrase-as-state", "successors-assigns-line1", "letter-after-number",
    }
    assert not set(probes.hits(line1, line2, zip_code, city, state)) & new


@pytest.mark.parametrize(
    "line1, line2, zip_code, expect, hit",
    [
        ("12 OAK ST", None, "0", "zip-zero", True),
        ("12 OAK ST", None, "0000", "zip-zero", True),
        ("12 OAK ST", None, "00000", "zip-zero", False),
        ("12 OAK ST", None, "62704", "zip-zero", False),
        ("12 OAK ST", None, "7500112", "zip-cut-no-hyphen", True),
        ("12 OAK ST", None, "75001123", "zip-cut-no-hyphen", True),
        ("12 OAK ST", None, "750011234", "zip-cut-no-hyphen", False),
        ("12 OAK ST", None, "750011", "zip-cut-no-hyphen", False),
        ("4212 OAK DRIVE", "5 APT 12", None, "number-before-designator-line2", True),
        ("4212 OAK DRIVE", "3 # 305", None, "number-before-designator-line2", True),
        ("4212 OAK DRIVE", "2B UNIT 14", None, "number-before-designator-line2", True),
        ("4212 OAK DRIVE", "FL 5 APT 12", None, "number-before-designator-line2", False),
        ("4212 OAK DRIVE", "APT 12", None, "number-before-designator-line2", False),
        ("4212 OAK DRIVE", "5 APARTMENT", None, "number-before-designator-line2", False),
        ("4212 OLD UNITED STATES HIGHWAY 27", None, None, "united-states-highway-gap", True),
        ("4212 UNITED STATES HIGHWAY 41-45", None, None, "united-states-highway-gap", True),
        ("4212 UNITED STATES HIGHWAY 41/45", None, None, "united-states-highway-gap", True),
        ("4212 S UNITED STATES HIGHWAY 27", None, None, "united-states-highway-gap", False),
        ("4212 EAST UNITED STATES HIGHWAY 27", None, None, "united-states-highway-gap", False),
        ("4212 UNITED STATES HIGHWAY 27", None, None, "united-states-highway-gap", False),
        ("4212 UNITED STATES HIGHWAY 41 / 45", None, None, "united-states-highway-gap", False),
    ],
)
def test_the_b2_probes(line1, line2, zip_code, expect, hit):
    """#586 B2 (#605 to #608): invented rows."""
    assert (expect in probes.hits(line1, line2, zip_code, "SPRINGTOWN", "IN")) is hit
