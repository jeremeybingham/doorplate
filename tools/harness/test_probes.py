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
    ],
)
def test_each_shape_is_found(line1, line2, zip_code, expect):
    assert expect in probes.hits(line1, line2, zip_code)


def test_an_ordinary_address_hits_nothing():
    assert probes.hits("812 ASHGROVE ST", "SUITE 4", "33101") == []
    assert probes.hits("123 MAIN ST", None, None) == []


def test_flagged_and_score():
    assert probes.is_flagged(["unparsed_remainder"], "k3:S|1||A|ST||FL|33101")
    assert probes.is_flagged([], "k3n:S|1||A|ST|||")
    assert not probes.is_flagged(["dual_address"], "k3:S|1||A|ST||FL|33101")
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
                    "sut-stu": {"rows": 5, "flagged": 1, "k3n": 0, "compared": 5, "disagree": 4},  # 80%: mostly real
                    "placeholder": {"rows": 50, "flagged": 0, "k3n": 0, "compared": 50, "disagree": 1},  # 2%: below the baseline
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
