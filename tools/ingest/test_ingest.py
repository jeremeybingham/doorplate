"""Tests for tools/ingest/ingest.py on invented rows: `pytest tools/ingest`."""
import json
import sqlite3
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402

ROWS = [
    # id, number, street, unit, city, state, zip
    ("1", "123", "  OAK HOLLOW DR ", "STE 4", "AUSTIN", "TX", "78701"),
    ("2", "9", "N ELM ST", "", "SPRINGFIELD", "IL", "62701"),
    ("3", None, "PO BOX 12", None, "DOVER", "DE", "19901"),
]


@pytest.fixture
def csv_source(tmp_path):
    path = tmp_path / "src.csv"
    con = duckdb.connect()
    con.execute("CREATE TABLE t (id VARCHAR, number VARCHAR, street VARCHAR, unit VARCHAR, "
                "city VARCHAR, state VARCHAR, zip VARCHAR)")
    con.executemany("INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, ?)", ROWS)
    con.execute(f"COPY t TO '{path}' (HEADER)")
    return path


def write_spec(tmp_path, src, roles):
    spec = tmp_path / "spec.toml"
    body = [f'source = "test"', f'output = "{tmp_path / "records.parquet"}"',
            "[inputs.s]", f'files = ["{src}"]',
            f"sql = \"SELECT * FROM read_csv('{src}', all_varchar = true)\""]
    for role, sql in roles:
        body += ["[[roles]]", f'role = "{role}"', f'sql = """{sql}"""']
    spec.write_text("\n".join(body) + "\n")
    return spec


def read(path):
    return duckdb.connect().execute(f"SELECT * FROM '{path}' ORDER BY role, record_id").fetchall()


def test_plan_writes_nothing(tmp_path, csv_source):
    spec = write_spec(tmp_path, csv_source, [("a", "SELECT id AS record_id, street AS line1 FROM s")])
    assert "Dry run" in ingest.main([str(spec)])
    assert not (tmp_path / "records.parquet").exists()


def test_columns_order_trim_and_nulls(tmp_path, csv_source):
    spec = write_spec(tmp_path, csv_source, [
        ("site", "SELECT id AS record_id, concat_ws(' ', number, street) AS line1, unit AS line2, "
                 "city, state, zip, number AS label_number FROM s"),
        ("other", "SELECT id AS record_id, street AS line1 FROM s WHERE id = '2'"),
    ])
    assert ingest.main([str(spec), "--confirm"]) == 0
    out = tmp_path / "records.parquet"
    con = duckdb.connect()
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{out}'").fetchall()]
    assert cols == ingest.COLUMNS
    rows = {(r[2], r[1]): dict(zip(cols, r)) for r in read(out)}
    site1 = rows[("site", "1")]
    assert site1["source"] == "test"
    assert site1["line1"] == "123   OAK HOLLOW DR"  # trimmed at the ends only: inner spacing kept
    assert site1["label_number"] == "123"
    assert rows[("site", "2")]["line2"] is None  # empty became null
    assert rows[("other", "2")]["city"] is None  # a column the role does not map is null
    meta = json.loads((tmp_path / "records.json").read_text())
    assert meta["rows"] == 4 and meta["roles"]["site"]["rows"] == 3
    assert meta["roles"]["site"]["present"]["line2"] == round(1 / 3, 4)
    assert meta["duplicate_ids"] == 0 and meta["inputs"]["s"][0]["bytes"] > 0


def test_limit(tmp_path, csv_source):
    spec = write_spec(tmp_path, csv_source, [("a", "SELECT id AS record_id, street AS line1 FROM s")])
    assert ingest.main([str(spec), "--limit", "2", "--confirm"]) == 0
    assert len(read(tmp_path / "records.parquet")) == 2


@pytest.mark.parametrize("sql, message", [
    ("SELECT id AS record_id, street AS line1, city AS town FROM s", "not in the record format"),
    ("SELECT id AS record_id, street AS line1, 'x' AS role FROM s", "not in the record format"),
    ("SELECT street AS line1 FROM s", "missing required columns"),
])
def test_bad_columns(tmp_path, csv_source, sql, message):
    spec = write_spec(tmp_path, csv_source, [("a", sql)])
    assert message in ingest.main([str(spec), "--confirm"])


def test_sql_error_names_the_problem(tmp_path, csv_source):
    spec = write_spec(tmp_path, csv_source, [("a", "SELECT id AS record_id, stret AS line1 FROM s")])
    msg = ingest.main([str(spec), "--confirm"])
    assert msg.startswith("SQL error in the spec: BinderException")


def test_data_errors_do_not_echo_rows(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("id,street\n1,SECRET NAME ROW\n2\n")
    spec = write_spec(tmp_path, bad, [("a", "SELECT id AS record_id, street AS line1 FROM s")])
    spec.write_text(spec.read_text().replace("all_varchar = true", "all_varchar = true, strict_mode = true, null_padding = false"))
    msg = ingest.main([str(spec), "--confirm"])
    assert msg != 0 and "SECRET" not in msg


def test_duplicates_counted(tmp_path, csv_source):
    spec = write_spec(tmp_path, csv_source, [("a", "SELECT 'same' AS record_id, street AS line1 FROM s")])
    assert ingest.main([str(spec), "--confirm"]) == 0
    assert json.loads((tmp_path / "records.json").read_text())["duplicate_ids"] == 1


def test_sqlite_input(tmp_path):
    db = tmp_path / "src.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE a (rid INTEGER, street TEXT, country TEXT)")
    con.executemany("INSERT INTO a VALUES (?, ?, ?)", [(1, "1 MAIN ST", "US"), (2, "2 RUE", "CA")])
    con.commit()
    con.close()
    spec = tmp_path / "spec.toml"
    spec.write_text(f'source = "t"\noutput = "{tmp_path / "records.parquet"}"\n'
                    f'[inputs.s]\nsqlite = "{db}"\nquery = "SELECT rid, street FROM a WHERE country = \'US\'"\n'
                    '[[roles]]\nrole = "a"\nsql = "SELECT rid AS record_id, street AS line1 FROM s"\n')
    assert ingest.main([str(spec), "--confirm"]) == 0
    assert [r[1:4] for r in read(tmp_path / "records.parquet")] == [("1", "a", "1 MAIN ST")]
    assert not list(tmp_path.glob(".ingest_tmp_*"))
