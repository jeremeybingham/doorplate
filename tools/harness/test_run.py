"""Tests for tools/harness/run.py on invented rows (no private data).

    pytest tools/harness
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("doorplate")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import duckdb  # noqa: E402
import run  # noqa: E402
from doorplate import parse_fields_many, parse_many  # noqa: E402


def row(rid, line1, line2=None, city=None, state=None, zipc=None, last_line=None, number=None,
        role="site"):
    return (rid, "t", role, "p", line1, line2, city, state, zipc, last_line, number)


def count(rows, present):
    by_key, *_ = run.process_chunk(rows, {"site": present}, parse_fields_many, parse_many)
    total = run.Counter()
    for c in by_key.values():
        total.update(c)
    return total


def test_split_row_agrees():
    t = count([row("1", "123 OAK HOLLOW DR", "STE 4", "AUSTIN", "TX", "78701", number="123")],
              ["city", "label_number", "line2", "state", "zip"])
    assert t["rows"] == 1 and t["flagged"] == 0


def test_checks_run_only_on_present_fields():
    # No state column in the role: a missing state is not a `state` mismatch.
    t = count([row("1", "123 OAK HOLLOW DR", city="AUSTIN")], ["city"])
    assert t["m_state"] == 0 and t["m_zip5"] == 0 and t["m_unit"] == 0


def test_last_line_joined_and_counted():
    t = count([row("1", "123 OAK HOLLOW DR", "STE 4", last_line="AUSTIN, TX 78701")],
              ["last_line", "line2"])
    assert t["last_line_rows"] == 1 and t["last_line_crossed"] == 0 and t["flagged"] == 0


def test_last_line_boundary_crossing():
    # No city in the last line: joining lets the unit line become the city.
    t = count([row("1", "123 OAK HOLLOW DR", "STE 4", last_line="TX 78701")], ["last_line", "line2"])
    assert t["last_line_rows"] == 1 and t["last_line_crossed"] == 1 and t["m_boundary"] == 1


def test_state_spelled_out_is_not_a_crossing():
    t = count([row("1", "123 OAK HOLLOW DR", last_line="AUSTIN, TEXAS 78701")], ["last_line"])
    assert t["last_line_crossed"] == 0


def test_records_chunks_by_row_offset(tmp_path):
    f = tmp_path / "r.parquet"
    duckdb.sql(f"""copy (select i::varchar AS record_id, 't' AS source, 'site' AS role, i::varchar AS line1
        from range(10) as t(i)) to '{f}' (format parquet)""")

    class A:
        input = f

    con = duckdb.connect()
    got = run.fetch_records(con, A, 3, 7)
    assert sorted(r[0] for r in got) == ["3", "4", "5", "6"]


def test_street_check_accepts_po_boxes_and_rural_routes():
    from doorplate import parse_fields

    for text in ("PO BOX 123", "P.O. BOX 77B", "RR 2 BOX 45", "HC 63 BOX 4", "GENERAL DELIVERY",
                 "PSC 1234 BOX 5"):
        a = parse_fields(line1=text, city="MIAMI", state="FL", zip="33101")
        assert run.street_ok(text, None, "", a), text
    # A real street change is still caught: the street words the parse dropped.
    a = parse_fields(line1="123 OAK ST", city="MIAMI", state="FL", zip="33101")
    assert not run.street_ok("123 ELM ST", None, "123", a)
