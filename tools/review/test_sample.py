"""Tests for tools/review/sample.py and shape.py on invented rows (no private data).

    pytest tools/review
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("doorplate")
pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness"))

import duckdb  # noqa: E402
import sample  # noqa: E402
from shape import clip, shape  # noqa: E402

# line1, line2, city, state, zip. Three rows share one failing shape (a `9 9 a a` street).
ROWS = [
    ("123 456 QUINCEWOOD ST", None, "MIAMI", "FL", "33101"),
    ("124 457 QUINCEWOOD ST", None, "MIAMI", "FL", "33101"),
    ("125 458 QUINCEWOOD ST", None, "MIAMI", "FL", "33101"),
    ("5 OAK AVE", "BLDG", "SPRINGFIELD", "IL", "62701"),
    ("5 OAK AVE", None, "SPRINGFIELD", "IL", "62701"),
    ("88 BAYVIEW DR", None, "PENSACOLA", "FL", "32502"),
]


def make_run(tmp_path, input_dir="inputs"):
    d = tmp_path / input_dir
    d.mkdir()
    recs = d / "records.parquet"
    con = duckdb.connect()
    con.execute("create table t (record_id varchar, source varchar, role varchar, provider varchar, "
                "line1 varchar, line2 varchar, city varchar, state varchar, zip varchar)")
    con.executemany("insert into t values (?,?,?,?,?,?,?,?,?)",
                    [(str(i), "inv", "site", "p", *r) for i, r in enumerate(ROWS)])
    con.execute(f"copy t to '{recs}' (format parquet)")
    root = tmp_path / "runs"
    res = subprocess.run(
        [sys.executable, str(HERE.parent / "harness" / "run.py"), "--input", str(recs), "--out-root", str(root),
         "--run-id", "r", "--workers", "1", "--min-free-gb", "0", "--confirm"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    return root / "r"


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_shape():
    assert shape("123 N OAK ST APT 4") == "9 a a a a 9"
    assert shape("% JOHN SMITH") == "% a a"
    assert shape("ZÜRICH 8001") == "a 9"
    assert shape(None) == ""
    assert clip("a" * 60).endswith("…") and len(clip("a" * 60)) == 48


def test_plan_without_confirm_writes_nothing(tmp_path, capsys):
    run = make_run(tmp_path)
    out = tmp_path / "q.jsonl"
    assert sample.main([str(run), "--out", str(out)]) == 0
    assert not out.exists()
    assert "plan only" in capsys.readouterr().out


def test_queue_has_one_row_per_group_first_biggest_group_first(tmp_path):
    run = make_run(tmp_path)
    out = tmp_path / "q.jsonl"
    assert sample.main([str(run), "--out", str(out), "--confirm", "--per-shape", "2"]) == 0
    q = read(out)
    assert [e["seq"] for e in q] == [1, 2, 3]
    # one row of each group first (the three-row group, then the one-row group), then a
    # second row of the big group; the one-row group has no second row
    assert [e["cluster"]["size"] for e in q] == [3, 1, 3]
    assert q[0]["cluster"]["shape"] == q[2]["cluster"]["shape"] != q[1]["cluster"]["shape"]
    assert q[0]["record_id"] != q[2]["record_id"]
    # every queue line carries the input lines and an id that names the record
    for e in q:
        assert e["id"] == f"inv|site|{e['record_id']}"
        assert e["line1"] and e["source"] == "inv" and e["cluster"]["warnings"]
        assert e["state"] in ("FL", "IL") and e["zip"] and e["city"]


def test_seed_is_repeatable_and_limit_applies(tmp_path):
    run = make_run(tmp_path)
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    sample.main([str(run), "--out", str(a), "--confirm", "--seed", "3", "--limit", "2"])
    sample.main([str(run), "--out", str(b), "--confirm", "--seed", "3", "--limit", "2"])
    assert a.read_text() == b.read_text()
    assert len(read(a)) == 2


def test_a_benchmark_input_is_refused(tmp_path):
    run = make_run(tmp_path, input_dir="benchsuite")
    with pytest.raises(SystemExit) as e:
        sample.main([str(run), "--out", str(tmp_path / "q.jsonl"), "--confirm"])
    assert "not a work list" in str(e.value)
    assert not (tmp_path / "q.jsonl").exists()
