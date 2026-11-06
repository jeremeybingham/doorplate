"""Tests for tools/compare/phase_g_check.py on invented rows (no private data).

pytest tools/compare/test_phase_g_check.py
The wasm-native test needs the two built binaries (DOORPLATE_TEST_EXE, DOORPLATE_TEST_WASM) and node; it is skipped without them.
"""

import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
doorplate = pytest.importorskip("doorplate")

import phase_g_check  # noqa: E402


def sources_file(tmp_path):
    rows = [(f"{i} OAK ST", "APT 2" if i % 3 == 0 else "", "MIAMI", "FL", "33101") for i in range(1, 61)]
    rows += [("PO BOX 12", "", "TAMPA", "FL", "33601"), ("", "", "", "", ""), ("1 2 3 FM RD", "SUITE", "", "TX", "")]
    rec = tmp_path / "rec.parquet"
    con = duckdb.connect()
    con.execute("create table r(line1 varchar, line2 varchar, city varchar, state varchar, zip varchar)")
    con.executemany("insert into r values (?, ?, ?, ?, ?)", rows)
    con.execute(f"copy r to '{rec}' (format parquet)")
    src = tmp_path / "sources.txt"
    src.write_text(f"{rec}\n")
    return src


def run(tmp_path, check, *extra):
    return phase_g_check.main([check, "--rows", "50", "--chunk", "20", "--sources", str(sources_file(tmp_path)),
                               "--tmp-root", str(tmp_path / "tmp"), *extra])


def test_threads_agree(tmp_path, capsys):
    assert run(tmp_path, "threads", "--workers", "4") == 0
    out = capsys.readouterr().out
    assert "50 rows, 0 differ" in out and "OAK" not in out


def test_threads_check_sees_a_difference(tmp_path, monkeypatch, capsys):
    # a worker whose answer depends on the thread count must be reported, with the column named and no row text
    worker = phase_g_check.WORKER.replace(
        'cols = {"rn"', 'tc = os.environ["RAYON_NUM_THREADS"]\ncols = {"rn"'
    ).replace('"key": [p.key() if p is not None else None for p in parsed]', '"key": [(p.key() or "") + tc for p in parsed if p is not None] + [None] * (len(parsed) - sum(p is not None for p in parsed))')
    monkeypatch.setattr(phase_g_check, "WORKER", worker)
    assert run(tmp_path, "threads", "--workers", "4") == 1
    assert "key" in capsys.readouterr().out


def test_temp_files_are_removed(tmp_path):
    run(tmp_path, "threads", "--workers", "2")
    assert list((tmp_path / "tmp").iterdir()) == []


@pytest.mark.skipif(not (os.environ.get("DOORPLATE_TEST_EXE") and os.environ.get("DOORPLATE_TEST_WASM")), reason="no built binaries")
def test_wasm_matches_native(tmp_path, capsys):
    rc = run(tmp_path, "wasm-native", "--exe", os.environ["DOORPLATE_TEST_EXE"], "--wasm", os.environ["DOORPLATE_TEST_WASM"])
    assert rc == 0 and "0 differ" in capsys.readouterr().out


def test_missing_binaries_are_not_run(tmp_path):
    assert run(tmp_path, "wasm-native", "--exe", "/nonexistent", "--wasm", "/nonexistent") == 2
