"""tools/harness/run.py and analyze.py on a tiny database of invented rows:
the plan writes nothing, a run is resumable and deterministic, the artifacts
have the documented shape, and the analysis reads them. Skips without DuckDB
and PyArrow."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")

TOOLS = Path(__file__).resolve().parents[3] / "tools" / "harness"

ROWS = [
    ("7", "MAIN STREET", "", "MIAMI", "FL", "33101", "", "US", "t/one"),
    # number, street, street2, city, state, zipcode, plus4, country, source
    ("123", "N MAIN ST", "APT 4", "MIAMI", "FL", "33101", "1234", "US", "t/one"),
    ("88", "BAYVIEW DR", "", "PENSACOLA", "FL", "32502", "", "US", "t/one"),
    ("5", "OAK AVE", "", "SPRINGFIELD", "IL", "62701", "", "US", "t/two"),
    ("0", "ELM ST", "", "SOMEWHERE", "AL", "36301", "", "US", "t/two"),
    ("10", "RUE DE LA PAIX", "", "MONTREAL", "QC", "H2X1Y4", "", "CA", "t/ca"),
]


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "t.sqlite"
    con = sqlite3.connect(path)
    con.execute(
        "create table addresses (number, street, street2, city, state, zipcode, plus4, country, source)"
    )
    con.executemany("insert into addresses values (?,?,?,?,?,?,?,?,?)", ROWS)
    con.commit()
    con.close()
    return path


def run(db, root, *extra):
    res = subprocess.run(
        [sys.executable, str(TOOLS / "run.py"), "--db", str(db), "--out-root", str(root),
         "--chunk-rowids", "2", "--workers", "2", "--min-free-gb", "0", *extra],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    return res


def test_plan_writes_nothing(db, tmp_path):
    out = run(db, tmp_path / "runs")
    assert "Dry run" in out.stdout
    assert not (tmp_path / "runs").exists()


def test_run_resume_and_analysis(db, tmp_path):
    root = tmp_path / "runs"
    run(db, root, "--run-id", "r1", "--confirm")
    r = root / "r1"
    assert (r / "DONE").exists()
    manifest = json.loads((r / "manifest.json").read_text())
    assert manifest["input"]["table"] == "addresses" and manifest["schema_version"] == 7
    totals = json.loads((r / "DONE").read_text())
    assert totals["rows"] == 5  # the Canadian row is out of scope
    for sub in ("agg_state_source", "agg_warnings", "agg_triples", "flagged", "chunk_status"):
        assert list((r / sub).glob("*")), sub
    # No two names may differ only by case: macOS and Windows would treat them as one.
    names = [p.name.lower() for p in r.iterdir()]
    assert len(names) == len(set(names)), names
    # A second run with the same id finds every chunk done and does nothing new.
    again = run(db, root, "--run-id", "r1", "--confirm")
    assert "skipped_resumed" in again.stdout
    out = subprocess.run(
        [sys.executable, str(TOOLS / "analyze.py"), str(r)], capture_output=True, text=True, check=True
    ).stdout
    assert "| rows | 5 |" in out
    # A suffix spelled out in the source is not a street mismatch (schema version 2 and later).
    assert "| street | 0 |" in out
    assert (r / "summary.md").exists() and (r / "place_gaps.parquet").exists()


def test_incomplete_run_is_refused(db, tmp_path):
    root = tmp_path / "runs"
    run(db, root, "--run-id", "r2", "--confirm", "--limit-chunks", "1")
    assert not (root / "r2" / "DONE").exists() and (root / "r2" / "LIMITED").exists()
    res = subprocess.run(
        [sys.executable, str(TOOLS / "analyze.py"), str(root / "r2")], capture_output=True, text=True
    )
    assert res.returncode != 0 and "incomplete" in res.stderr + res.stdout


def test_compare_two_runs(db, tmp_path):
    root = tmp_path / "runs"
    run(db, root, "--run-id", "a", "--confirm")
    run(db, root, "--run-id", "b", "--confirm")
    out = subprocess.run(
        [sys.executable, str(TOOLS / "compare.py"), str(root / "a"), str(root / "b")],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "| rows | 5 | 5 | +0 |" in out
    assert (root / "b" / "compare-a-vs-b.md").exists()
    assert "different input" not in out


def test_records_input_matches_the_sqlite_run(db, tmp_path):
    """`--input` on records built like tools/ingest/specs/netsyms.toml gives the same totals
    as `--db` (#93, step 2)."""
    import duckdb

    recs = tmp_path / "records.parquet"
    con = duckdb.connect()
    con.execute("create table src (rid integer, number varchar, street varchar, street2 varchar, city varchar, state varchar, zipcode varchar, plus4 varchar, country varchar, source varchar)")
    con.executemany("insert into src values (?,?,?,?,?,?,?,?,?,?)",
                    [(i + 1, *r) for i, r in enumerate(ROWS)])
    con.execute(f"""copy (select rid::varchar AS record_id, 'netsyms' AS source, 'address' AS role,
        source AS provider, concat_ws(' ', nullif(trim(number), ''), nullif(trim(street), '')) AS line1,
        nullif(trim(number), '') AS label_number, nullif(street2, '') AS line2, nullif(street2, '') AS label_unit, city, state,
        CASE WHEN nullif(trim(plus4), '') IS NULL THEN zipcode ELSE concat(zipcode, '-', plus4) END AS zip
        from src where country = 'US') to '{recs}' (format parquet)""")
    root = tmp_path / "runs"
    run(db, root, "--run-id", "direct", "--confirm")
    res = subprocess.run(
        [sys.executable, str(TOOLS / "run.py"), "--input", str(recs), "--out-root", str(root),
         "--run-id", "rec", "--chunk-rowids", "2", "--workers", "2", "--min-free-gb", "0", "--confirm"],
        capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    out = subprocess.run(
        [sys.executable, str(TOOLS / "compare.py"), str(root / "direct"), str(root / "rec")],
        capture_output=True, text=True, check=True).stdout
    totals = out.split("## Totals")[1].split("##")[0]
    changes = [ln.split("|")[4].strip() for ln in totals.splitlines() if ln.startswith("| ") and "---" not in ln][1:]
    assert changes and set(changes) == {"+0"}, changes
