"""Tests for tools/harness/probe_scan.py on invented rows (no private data).

pytest tools/harness
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_scan

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
doorplate = pytest.importorskip("doorplate")

ROWS = [
    # record_id, source, role, line1, line2, city, state, zip, last_line
    ("1", "s", "a", "640 PINEWOOD BOX 18", None, "MIAMI", "FL", "33101", None),
    ("2", "s", "a", "812 ASHGROVE ST", None, "MIAMI", "FL", "33101", None),
    ("3", "s", "a", "40 ELM ST SUT 300", None, "MIAMI", "fl", "33101", None),
    ("4", "s", "a", "464 NO MAPLE AVE", None, None, None, None, None),
]


def scan(rows, cap=1000):
    return probe_scan.scan_rows(rows, doorplate.parse_fields_many, doorplate.parse_many, cap, 1)


def test_counts_all_rows_and_the_matches_by_state():
    counts, hits = scan(ROWS)
    assert counts[("s", "a", "FL", "__rows__", "rows")] == 3
    assert counts[("s", "a", "", "__rows__", "rows")] == 1
    assert counts[("s", "a", "FL", "box-after-street", "rows")] == 1
    assert counts[("s", "a", "FL", "sut-stu", "rows")] == 1
    assert counts[("s", "a", "", "no-for-north", "rows")] == 1
    assert {h[4] for h in hits} >= {"box-after-street", "sut-stu", "no-for-north"}


def test_hits_hold_identity_and_a_hash_but_no_text():
    _counts, hits = scan(ROWS)
    for source, role, rid, state, probe, flagged, text_hash, rk in hits:
        assert rid in {"1", "3", "4"}
        assert len(text_hash) == 16 and 0 <= rk < 1
        assert isinstance(flagged, bool)
        assert not any("PINEWOOD" in str(x) or "ELM" in str(x) for x in (source, role, rid, state, probe, text_hash))


def test_the_cap_keeps_the_lowest_rk_and_the_count_stays_exact():
    rows = [(str(i), "s", "a", f"{i} NO MAPLE AVE", None, None, "FL", None, None) for i in range(1, 51)]
    counts, hits = scan(rows, cap=5)
    assert counts[("s", "a", "FL", "no-for-north", "rows")] == 50
    kept = [h for h in hits if h[4] == "no-for-north"]
    assert len(kept) == 5
    every = sorted(probe_scan.rk_of(1, "s", str(i), "no-for-north") for i in range(1, 51))
    assert [h[7] for h in kept] == every[:5]
    assert scan(rows, cap=0)[1] == []


def test_a_last_line_row_is_parsed_joined():
    rows = [("9", "s", "a", "12 OAK ST", None, None, None, None, "SPRINGFIELD IL 62704")]
    counts, _hits = scan(rows)
    assert counts[("s", "a", "", "__rows__", "rows")] == 1


def make_records(path, n):
    duckdb.sql(
        "copy (select cast(i as varchar) as record_id, 's' as source, 'a' as role, "
        "case when i % 2 = 0 then i::varchar || ' NO MAPLE AVE' else i::varchar || ' ASHGROVE ST' end as line1, "
        "NULL as line2, 'MIAMI' as city, 'FL' as state, '33101' as zip "
        f"from range(1, {n + 1}) t(i)) to '{path}' (format parquet)"
    )


def test_a_run_writes_counts_hits_status_and_done(tmp_path):
    rec = tmp_path / "records.parquet"
    make_records(rec, 25)
    lst = tmp_path / "inputs.txt"
    lst.write_text(f"{rec}  # a records file\n\n")
    out = tmp_path / "out"
    argv = [str(lst), "--out-root", str(out), "--run-id", "r1", "--chunk-rows", "10", "--workers", "2",
            "--skip-coverage", "--min-free-gb", "0", "--confirm"]
    assert probe_scan.main(argv) == 0
    run = out / "r1"
    assert (run / "DONE").exists() and (run / "summary.json").exists()
    assert len(list((run / "chunk_status").glob("*.json"))) == 3
    summary = json.loads((run / "summary.json").read_text())
    assert summary["total_rows"] == 25
    assert summary["probe_rows"]["no-for-north"] == 12
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["probes_sha256"] == probe_scan.registry_hash()
    hits = duckdb.sql(f"select count(*), count(distinct record_id) from '{run}/hits/*.parquet' where probe = 'no-for-north'").fetchall()
    assert hits == [(12, 12)]


def test_a_second_start_resumes_and_skips_done_chunks(tmp_path, capsys):
    rec = tmp_path / "records.parquet"
    make_records(rec, 25)
    lst = tmp_path / "inputs.txt"
    lst.write_text(f"{rec}\n")
    argv = [str(lst), "--out-root", str(tmp_path), "--run-id", "r", "--chunk-rows", "10", "--workers", "1",
            "--skip-coverage", "--min-free-gb", "0", "--confirm"]
    assert probe_scan.main(argv) == 0
    (tmp_path / "r" / "chunk_status" / "00-00001.json").unlink()
    (tmp_path / "r" / "DONE").unlink()
    capsys.readouterr()
    assert probe_scan.main(argv) == 0
    assert "start 1 chunk(s) to do, 2 done already" in capsys.readouterr().out


def test_limit_chunks_and_a_dry_run(tmp_path, capsys):
    rec = tmp_path / "records.parquet"
    make_records(rec, 25)
    lst = tmp_path / "inputs.txt"
    lst.write_text(f"{rec}\n")
    assert probe_scan.main([str(lst), "--out-root", str(tmp_path / "o"), "--chunk-rows", "10", "--skip-coverage"]) == 0
    assert "Dry run" in capsys.readouterr().out
    assert not (tmp_path / "o").exists() or not list((tmp_path / "o").iterdir())
    argv = [str(lst), "--out-root", str(tmp_path / "o"), "--run-id", "x", "--chunk-rows", "10", "--limit-chunks", "1",
            "--workers", "1", "--skip-coverage", "--min-free-gb", "0", "--confirm"]
    assert probe_scan.main(argv) == 0
    assert json.loads((tmp_path / "o" / "x" / "summary.json").read_text())["total_rows"] == 10


def test_a_changed_registry_refuses_to_resume(tmp_path):
    rec = tmp_path / "records.parquet"
    make_records(rec, 5)
    lst = tmp_path / "inputs.txt"
    lst.write_text(f"{rec}\n")
    argv = [str(lst), "--out-root", str(tmp_path), "--run-id", "r", "--workers", "1", "--skip-coverage",
            "--min-free-gb", "0", "--confirm"]
    assert probe_scan.main(argv) == 0
    m = tmp_path / "r" / "manifest.json"
    d = json.loads(m.read_text())
    d["probes_sha256"] = "0" * 64
    m.write_text(json.dumps(d))
    with pytest.raises(SystemExit):
        probe_scan.main(argv)


def test_the_raw_nad_and_netsyms_inputs_are_mapped(tmp_path):
    nad = tmp_path / "nad.parquet"
    duckdb.sql(
        "copy (select * from (values ('FL','12','ELM ST','Miami','33101','Apt 4','x'),"
        "('FL','464','NO MAPLE AVE','Not stated','33101',NULL,'x')) "
        "t(State, AddNo_Full, StNam_Full, Post_City, Zip_Code, SubAddress, NAD_Source)) "
        f"to '{nad}' (format parquet)"
    )
    inp = {"path": str(nad), "table": "addresses", "country": "US"}
    assert probe_scan.kind_of(inp) == "nad"
    inp["kind"] = "nad"
    rows = probe_scan.fetch(duckdb.connect(), inp, 0, 10)
    assert rows[0][3] == "12 ELM ST" and rows[0][4] == "Apt 4" and rows[0][1] == "nad-raw"
    counts, _hits = scan(rows)
    assert counts[("nad-raw", "address", "FL", "city-placeholder", "rows")] == 1

    db = tmp_path / "n.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table addresses (number, street, street2, city, state, zipcode, plus4, country, source)")
    con.execute("insert into addresses values ('12','ELM ST',NULL,'MIAMI','FL','33101','1234','US','x')")
    con.execute("insert into addresses values ('9','ELM ST',NULL,'LONDON','XX','1','','GB','x')")
    con.commit()
    inp = {"path": str(db), "table": "addresses", "country": "US", "kind": "netsyms"}
    assert probe_scan.kind_of(inp) == "netsyms"
    assert probe_scan.count_rows(inp) == (1, 3)
    got = probe_scan.fetch(con, inp, 1, 3)
    assert got == [("1", "netsyms", "address", "12 ELM ST", None, "MIAMI", "FL", "33101-1234", None)]
