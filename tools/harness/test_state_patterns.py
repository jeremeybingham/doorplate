"""Tests for tools/harness/state_patterns.py on invented rows (no private data).

    pytest tools/harness
"""
import csv
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
HERE = Path(__file__).resolve().parent

import duckdb

# source, state, line1. Street names are invented; none may reach the output files.
ROWS = [
    ("inv", "TX", "RR 2 BOX 5"),
    ("inv", "TX", "120 QUINCEWOOD RR 12"),
    ("inv", "TX", "300 FM 1960 RD"),
    ("inv", "TX", "55 PR 4410"),
    ("inv", "AL", "9120 ZEPHYRMILL ROAD 123"),
    ("inv", "AL", "14 COUNTY ROAD 7"),
    ("inv", "AL", "14 CR 7"),
    ("inv", "NY", "41-20 BAYVIEW AVE"),
    ("inv", "NY", "88 OAK AVE"),
    ("inv", "PR", "URB LAS FLORES CALLE 3"),
    ("inv", "FL", "100 SR 60"),
    ("inv", "FL", "100 STATE ROUTE 60"),
    ("inv", "FL", "77 SHORE ROAD 20"),
    ("inv", "FL", "5 PELICAN FOOBAR"),
    ("inv", "FL", "5 PELICAN FOOBAR"),
]


@pytest.fixture
def records(tmp_path):
    recs = tmp_path / "records.parquet"
    con = duckdb.connect()
    con.execute("create table t (source varchar, state varchar, line1 varchar)")
    con.executemany("insert into t values (?,?,?)", ROWS)
    con.execute(f"copy t to '{recs}' (format parquet)")
    return recs


def run(args, tmp_path):
    return subprocess.run([sys.executable, "-I", str(HERE / "state_patterns.py"), *args],
                          capture_output=True, text=True, cwd=tmp_path, check=False)


def counts(out):
    with open(out / "state_patterns.csv") as f:
        return {(r["state"], r["pattern"]): int(r["matches"]) for r in csv.DictReader(f)}


def test_plan_only(records, tmp_path):
    out = tmp_path / "out"
    res = run(["--input", str(records), "--out", str(out)], tmp_path)
    assert res.returncode == 0 and "plan only" in res.stdout
    assert not out.exists()


def test_counts(records, tmp_path, monkeypatch):
    out = tmp_path / "out"
    res = run(["--input", str(records), "--out", str(out), "--confirm"], tmp_path)
    assert res.returncode == 0, res.stderr
    c = counts(out)
    assert c[("TX", "rr_rural_route")] == 1
    assert c[("TX", "rr_street_word")] == 1
    assert c[("TX", "rm_fm_number")] == 1
    assert c[("TX", "pr_number")] == 1
    assert c[("AL", "name_road_number")] == 2  # includes COUNTY ROAD 7
    assert c[("AL", "county_road_word")] == 1
    assert c[("AL", "cr_number")] == 1
    assert c[("NY", "hyphen_house_number")] == 1
    assert c[("PR", "urb")] == 1 and c[("PR", "spanish_words")] == 1
    assert c[("FL", "sr_number")] == 1 and c[("FL", "state_route_words")] == 1
    assert c[("FL", "trailing_number")] == 2  # SHORE ROAD 20 and STATE ROUTE 60 (ROUTE is a suffix)
    assert c[("FL", "unknown_last_word")] == 2  # the two FOOBAR rows
    assert c[("NY", "unknown_last_word")] == 0


def test_no_street_text_in_outputs(records, tmp_path):
    out = tmp_path / "out"
    assert run(["--input", str(records), "--out", str(out), "--confirm"], tmp_path).returncode == 0
    text = "".join(p.read_text() for p in out.iterdir())
    for secret in ("QUINCEWOOD", "ZEPHYRMILL", "BAYVIEW", "PELICAN"):
        assert secret not in text


def test_reader_error_prints_only_the_type(tmp_path):
    bad = tmp_path / "records.parquet"
    bad.write_text("SECRET ROW 123 MAIN ST not parquet")
    res = run(["--input", str(bad), "--out", str(tmp_path / "o"), "--confirm"], tmp_path)
    assert res.returncode != 0
    assert "SECRET" not in res.stdout + res.stderr and "failed:" in res.stderr
