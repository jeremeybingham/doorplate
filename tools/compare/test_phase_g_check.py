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


def native_like_csv(path, apostrophe_rows):
    """A CSV shaped like the native tool's output: 35 columns, `"` quoting, apostrophes in the street text (invented rows)."""
    cols = ["line1", "line2", "city", "state", "zip"] + [f"addr_{c}" for c in phase_g_check.COLUMNS]
    assert len(cols) == 35
    lines = [",".join(cols)]
    for i in range(apostrophe_rows):
        row = [f"{i} AVENUE 'O'", "", "CHICAGO", "IL", "60633"] + [""] * 30
        row[5 + 2] = f"AVENUE 'O' {i}"
        lines.append(",".join(row))
    # a quoted field with a comma and a doubled quote must still be one field
    row = ['"1 ""MAIN"", ST"', "", "X", "IL", "60633"] + [""] * 30
    lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n")


class Recorder:
    """A DuckDB connection that remembers the SQL it was given."""

    def __init__(self, con):
        self.con, self.sql = con, []

    def execute(self, q, *a):
        self.sql.append(q)
        return self.con.execute(q, *a)


def test_native_csv_dialect_is_pinned(tmp_path):
    # #579: left to its sniffer, DuckDB read_csv chose `'` as the escape character on a 500,000-row chunk of the real sources
    # ("escape = ' (Auto-Detected)") and read a row as 34 columns instead of 35. The sniffer's guess depends on the whole file, so
    # no small invented file reproduces it; what the tool must do is never guess: comma, `"` quote and `"` escape (RFC 4180, which
    # is how the native tool writes).
    f = tmp_path / "native.csv"
    native_like_csv(f, 300)
    rec = Recorder(duckdb.connect())
    phase_g_check.read_native_csv(rec, f)
    sql = " ".join(rec.sql)
    assert "delim=','" in sql and "quote='\"'" in sql and "escape='\"'" in sql


def test_native_csv_rows_read_back_whole(tmp_path):
    # apostrophes, a quoted field with a comma and doubled quotes: all 35 columns, one row each
    f = tmp_path / "native.csv"
    native_like_csv(f, 300)
    con = duckdb.connect()
    phase_g_check.read_native_csv(con, f)
    assert con.execute("select count(*), count(distinct i) from nat").fetchone() == (301, 301)
    assert len(con.execute("describe nat").fetchall()) == 36  # i plus 35 columns
    assert con.execute("select line1 from nat where i = 300").fetchone()[0] == '1 "MAIN", ST'
    assert con.execute("select count(*) from nat where line1 like '%''O''%'").fetchone()[0] == 300


@pytest.mark.skipif(not os.environ.get("DOORPLATE_TEST_FAILING_CSV"), reason="no local failing chunk")
def test_the_chunk_that_failed_the_away_run(tmp_path):
    # opt-in, local only: a 500,000-row native CSV on which the sniffed dialect failed (kept in local-data, never committed)
    con = duckdb.connect()
    phase_g_check.read_native_csv(con, os.environ["DOORPLATE_TEST_FAILING_CSV"])
    assert con.execute("select count(*) from nat").fetchone()[0] > 100_000
    assert len(con.execute("describe nat").fetchall()) == 36


def test_error_log_keeps_the_traceback_local(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise ValueError("Original Line: 1 OAK ST")

    monkeypatch.setattr(phase_g_check, "compare_threads", boom)
    log = tmp_path / "err.log"
    assert run(tmp_path, "threads", "--error-log", str(log)) == 2
    captured = capsys.readouterr()
    assert "ValueError" in captured.err and "OAK" not in captured.out + captured.err
    assert "OAK ST" in log.read_text()
