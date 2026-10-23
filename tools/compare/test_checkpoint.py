"""The checkpoint script's plan mode on tiny invented records (pytest tools/compare)."""
import subprocess
import sys
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

SCRIPT = Path(__file__).with_name("checkpoint.py")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def records(tmp_path):
    path = tmp_path / "records.parquet"
    duckdb.sql(
        f"copy (select 'demo' as source, 'a' as role, '1' as record_id, '1 MAIN ST' as line1) to '{path}' (format parquet)"
    )
    return path


def test_the_plan_names_the_sources_and_changes_nothing(tmp_path):
    sources = tmp_path / "sources.txt"
    sources.write_text(f"# a comment\n{records(tmp_path)}\n")
    out = tmp_path / "out"
    r = run("--baseline-python", sys.executable, "--sources", str(sources), "--baseline", str(tmp_path / "base"),
            "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert "1 records files, 1 rows" in r.stdout
    assert "plan only" in r.stdout
    assert not out.exists()


def test_a_missing_sources_file_is_an_error(tmp_path):
    r = run("--baseline-python", sys.executable, "--sources", str(tmp_path / "nope.txt"))
    assert r.returncode != 0
    assert "not found" in r.stderr


def test_confirm_refuses_to_run_when_not_ready(tmp_path):
    sources = tmp_path / "sources.txt"
    sources.write_text(f"{tmp_path / 'missing.parquet'}\n")
    r = run("--baseline-python", sys.executable, "--sources", str(sources), "--out", str(tmp_path / "out"), "--confirm")
    assert r.returncode != 0
    assert not (tmp_path / "out").exists()
