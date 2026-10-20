"""Tests for tools/netsyms/shapes_report.py on invented rows (no private data).

    pytest tools/netsyms
"""
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("doorplate")
pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import duckdb  # noqa: E402
import shapes_report as sr  # noqa: E402

# line1, line2, city, state, zip. Street names are invented and must never reach the report.
ROWS = [
    ("123 456 QUINCEWOOD ST", None, "MIAMI", "FL", "33101"),
    ("124 457 QUINCEWOOD ST", None, "MIAMI", "FL", "33101"),
    ("7 ZEPHYRMILL AVE", "APT 4", "MIAMI", "FL", "33101"),
    ("88 BAYVIEW DR", None, "PENSACOLA", "FL", "32502"),
    ("5 OAK AVE", None, "SPRINGFIELD", "IL", "62701"),
]


@pytest.fixture
def run_dir(tmp_path):
    recs = tmp_path / "records.parquet"
    con = duckdb.connect()
    con.execute("create table t (record_id varchar, source varchar, role varchar, provider varchar, "
                "line1 varchar, line2 varchar, city varchar, state varchar, zip varchar)")
    con.executemany("insert into t values (?,?,?,?,?,?,?,?,?)",
                    [(str(i), "inv", "site", "p", *r) for i, r in enumerate(ROWS)])
    con.execute(f"copy t to '{recs}' (format parquet)")
    root = tmp_path / "runs"
    res = subprocess.run(
        [sys.executable, str(HERE / "run.py"), "--input", str(recs), "--out-root", str(root), "--run-id", "r",
         "--workers", "1", "--min-free-gb", "0", "--confirm"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    return root / "r"


def test_report_has_counts_and_shapes_never_names(run_dir):
    sr.main([str(run_dir), "--top", "5"])
    text = (run_dir / "shapes.md").read_text()
    assert "## inv / site" in text and "### Warning codes" in text
    assert "5 rows" in text
    for name in ("QUINCEWOOD", "ZEPHYRMILL", "BAYVIEW", "OAK", "MIAMI"):
        assert name not in text
    assert "`9 9 a a`" in text  # the shape of the first two rows


def test_shape_sql_matches_the_python_shape(tmp_path):
    from label_score import shape

    con = duckdb.connect()
    con.execute(sr.MACRO)
    for s in ("123 N OAK ST APT 4", "12B", "1/2", "PO BOX 7", "", "a-1"):
        assert con.execute("select shape(?)", [s]).fetchone()[0] == shape(s)


def test_before_and_after_section(run_dir):
    sr.main([str(run_dir), "--before", str(run_dir)])
    text = (run_dir / "shapes.md").read_text()
    assert "compared with run r" in text and "### inv / site: change" in text
    assert "| rows | 5 | 5 | +0 |" in text


def test_older_schema_is_refused(run_dir):
    import json

    m = json.loads((run_dir / "manifest.json").read_text())
    m["schema_version"] = 2
    (run_dir / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(SystemExit):
        sr.main([str(run_dir)])
